# Cloud Assessor appliance on Azure (REFACTOR_APP.md section 12): one Consumption Container App running the published
# appliance image by digest under a user-assigned managed identity with Reader and Cost Management Reader on the
# allow-listed scopes, Log Analytics (30 days), a resource-group budget with 80/100 percent notifications, and an
# optional custom domain. No VNet, no database, no Entra application, no secrets: the identity is the only credential.
#
# Pattern copied from HCW-AzMigrateOrchestrator_App/infrastructure/terraform/appliance-azure and reduced. Planned and
# validated in CI; `apply` is an owner step after human review (section 20). [REVIEW REQUIRED] role assignments,
# region and prefix before the first apply.
terraform {
  required_version = ">= 1.9.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

provider "azurerm" {
  features {}
}

locals {
  name = "${var.prefix}-${var.environment}-${var.location_short}"
  tags = merge({ application = "cloud-assessor", component = "appliance", environment = var.environment }, var.tags)
  # Normalised once: role assignment scopes and CA_SCOPES compare case-insensitively, and toset() does not.
  scope_ids = toset([for s in var.scope_ids : lower(s)])
}

resource "azurerm_resource_group" "app" {
  name     = "rg-${local.name}-01"
  location = var.location
  tags     = local.tags
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.name}-01"
  location            = var.location
  resource_group_name = azurerm_resource_group.app.name
  tags                = local.tags
}

# Reader on each assessment scope: Resource Graph reads (T-011, T-025). [REVIEW REQUIRED]
resource "azurerm_role_assignment" "reader" {
  for_each             = local.scope_ids
  scope                = each.value
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

# Cost Management Reader on each scope: Reader does not include cost data (T-011, T-026). [REVIEW REQUIRED]
resource "azurerm_role_assignment" "cost_reader" {
  for_each             = local.scope_ids
  scope                = each.value
  role_definition_name = "Cost Management Reader"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_log_analytics_workspace" "app" {
  name                = "log-${local.name}-01"
  location            = var.location
  resource_group_name = azurerm_resource_group.app.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

# Consumption environment: no infrastructure subnet, no workload profile (CONTRACT-DECISIONS item 21).
resource "azurerm_container_app_environment" "app" {
  name                       = "cae-${local.name}-01"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.app.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.app.id
  tags                       = local.tags
}

resource "azurerm_container_app" "api" {
  name                         = "ca-${local.name}-01"
  container_app_environment_id = azurerm_container_app_environment.app.id
  resource_group_name          = azurerm_resource_group.app.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  # TLS is terminated by the platform; the container listens on plain HTTP 8080 behind it.
  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # min_replicas 0 is the documented owner option: it saves the idle cost but drops the in-memory snapshot, so the
    # first visitor after idle waits for a cold collection (section 12).
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "appliance"
      image  = var.image_ref
      cpu    = 0.5
      memory = "1Gi"

      # Container Apps ignores the Dockerfile HEALTHCHECK; the probes below carry it.
      liveness_probe {
        transport        = "HTTP"
        path             = "/api/health"
        port             = 8080
        interval_seconds = 30
      }
      readiness_probe {
        transport = "HTTP"
        path      = "/api/health"
        port      = 8080
      }

      env {
        name  = "CA_SCOPES"
        value = join(",", sort(local.scope_ids))
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.app.client_id
      }
      env {
        name  = "CA_REFRESH_MINUTES"
        value = tostring(var.refresh_minutes)
      }
      env {
        name  = "CA_PUBLIC_RESULTS"
        value = tostring(var.public_results)
      }
      env {
        name  = "CA_FRAME_ANCESTORS"
        value = "'none'"
      }
      env {
        name  = "PORT"
        value = "8080"
      }
    }
  }
}

# Spend guard on the appliance's own resource group: 80 and 100 percent of the monthly amount, actual spend.
resource "azurerm_consumption_budget_resource_group" "app" {
  name              = "budget-${local.name}-01"
  resource_group_id = azurerm_resource_group.app.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = length(var.alert_emails) > 0 ? [80, 100] : []
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = var.alert_emails
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

# Optional custom domain with a platform-managed certificate. The managed certificate is bound outside Terraform
# (az containerapp hostname bind --validation-method CNAME), which is why the binding attributes are ignored.
# [VERIFY] provider support for the managed-certificate flow in the pinned azurerm release.
resource "azurerm_container_app_custom_domain" "app" {
  count            = var.custom_domain != "" ? 1 : 0
  name             = var.custom_domain
  container_app_id = azurerm_container_app.api.id

  lifecycle {
    ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]
  }
}
