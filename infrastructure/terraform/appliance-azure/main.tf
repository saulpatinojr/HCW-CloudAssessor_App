# Cloud Assessor appliance on Azure (REFACTOR_APP.md section 12): one Consumption Container App running the published
# appliance image by digest under a user-assigned managed identity with Reader and Cost Management Reader on the
# allow-listed scopes, Log Analytics (30 days), a resource-group budget with 80/100 percent notifications, and an
# optional custom domain. No VNet, no database, no secrets: the identity is the only credential. Caller authentication
# (auth.tf) adds an Entra application registration only when auth_enabled is set; it never holds a client secret.
#
# Pattern copied from HCW-AzMigrateOrchestrator_App/infrastructure/terraform/appliance-azure and reduced. Planned and
# validated in CI; `apply` is an owner step after human review (section 20). [REVIEW REQUIRED] role assignments,
# region and prefix before the first apply.
terraform {
  required_version = ">= 1.9.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    azuread = { source = "hashicorp/azuread", version = "~> 3.0" }
  }
}

provider "azurerm" {
  features {}
}

# Used only by auth.tf, and only when auth_enabled and auth_create_app_registration are both true.
provider "azuread" {}

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

  lifecycle {
    # Safe default (ticket CA-3): the plan itself refuses to publish an appliance that does not check who calls it.
    precondition {
      condition     = !var.external_enabled || var.auth_enabled || var.dangerously_allow_unauthenticated_external_ingress
      error_message = "Refusing to plan an externally reachable appliance without caller authentication. Set auth_enabled = true (README.md, Sign-in), or external_enabled = false for a private ingress. dangerously_allow_unauthenticated_external_ingress = true overrides this and publishes an appliance that does not check who calls it; it is an owner decision (REVIEW.md R-009), not a default."
    }
    precondition {
      condition     = !var.public_results || var.auth_enabled
      error_message = "public_results = true needs auth_enabled = true: the appliance refuses to start with CA_PUBLIC_RESULTS=true and no sign-in (REVIEW.md R-009)."
    }
    precondition {
      condition     = !var.auth_enabled || var.auth_create_app_registration || (var.auth_tenant_id != "" && length(var.auth_audiences) > 0)
      error_message = "auth_enabled with auth_create_app_registration = false needs auth_tenant_id and at least one auth_audiences entry: the appliance refuses to start without them."
    }
    precondition {
      condition     = local.auth_create_registration || (length(var.auth_assigned_object_ids) == 0 && length(var.auth_preauthorized_client_ids) == 0)
      error_message = "auth_assigned_object_ids and auth_preauthorized_client_ids only apply when auth_enabled and auth_create_app_registration are both true."
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  # TLS is terminated by the platform; the container listens on plain HTTP 8080 behind it.
  ingress {
    external_enabled = var.external_enabled
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
      # CA_AUTH_*: the names config.py reads; values come from auth.tf.
      dynamic "env" {
        for_each = local.auth_env
        content {
          name  = env.key
          value = env.value
        }
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
# The azurerm resource requires at least one notification and every notification needs a recipient, and a budget that
# tells nobody guards nothing, so the budget exists only when alert_emails has an entry. An empty list (the default) is
# the documented opt-out: no budget, and the budget_notifications output says so (ticket #60; tests/budget_notifications.tftest.hcl).
resource "azurerm_consumption_budget_resource_group" "app" {
  count             = length(var.alert_emails) > 0 ? 1 : 0
  name              = "budget-${local.name}-01"
  resource_group_id = azurerm_resource_group.app.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = [80, 100]
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
