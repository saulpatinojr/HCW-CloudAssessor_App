# Caller authentication for the appliance (ticket CA-3, REVIEW.md R-009 option b, TODO.md T-032).
#
# The appliance validates Microsoft Entra ID access tokens itself (src/cloud_assessor_appliance/security/entra.py) with
# the tenant's PUBLIC signing keys. So this file creates no client secret, no certificate and no password: a token is
# only ever checked here, never requested. What the code checks, and where each value comes from below:
#   tid   = CA_AUTH_TENANT_ID                       <- the tenant of the registration (or auth_tenant_id)
#   aud   = one of CA_AUTH_AUDIENCE                 <- the application (client) id and its api:// URI (or auth_audiences)
#   iss   = v2.0 or v1.0 form for the tenant        <- built by the code from CA_AUTH_AUTHORITY_HOST
#   roles = CA_AUTH_REQUIRED_ROLES, or scp = CA_AUTH_REQUIRED_SCOPES  <- the Assessment.Read app role and scope below
# The registration is optional (auth_create_app_registration = false describes one that already exists).

locals {
  auth_create_registration = var.auth_enabled && var.auth_create_app_registration
  # Deterministic ids, so a re-created registration keeps the same role and scope ids (the same trick the AzMigrate
  # appliance uses), and a plan never shows them as new.
  auth_role_id  = uuidv5("url", "https://github.com/saulpatinojr/HCW-CloudAssessor_App/app-role/${var.auth_permission}")
  auth_scope_id = uuidv5("url", "https://github.com/saulpatinojr/HCW-CloudAssessor_App/oauth2-permission-scope/${var.auth_permission}")

  auth_tenant_id = local.auth_create_registration ? data.azuread_client_config.current[0].tenant_id : var.auth_tenant_id
  # A v2 token (requested_access_token_version = 2 below) carries the client id as aud; a v1 token carries the api:// URI.
  auth_audiences = local.auth_create_registration ? [
    azuread_application.api[0].client_id,
    "api://${azuread_application.api[0].client_id}",
  ] : var.auth_audiences

  # Every CA_AUTH_* name the code reads (config.py). Only CA_AUTH_ENABLED is set while sign-in is off; CA_AUTH_JWKS_URL
  # is left unset on purpose, so the code builds the address from the authority host and the tenant.
  auth_env = merge(
    { CA_AUTH_ENABLED = tostring(var.auth_enabled) },
    var.auth_enabled ? {
      CA_AUTH_TENANT_ID          = local.auth_tenant_id
      CA_AUTH_AUDIENCE           = join(" ", local.auth_audiences)
      CA_AUTH_AUTHORITY_HOST     = var.auth_authority_host
      CA_AUTH_CLOCK_SKEW_SECONDS = tostring(var.auth_clock_skew_seconds)
      CA_AUTH_REQUIRED_ROLES     = var.auth_permission
      CA_AUTH_REQUIRED_SCOPES    = var.auth_permission
    } : {},
  )
}

data "azuread_client_config" "current" {
  count = local.auth_create_registration ? 1 : 0
}

# The API registration: one tenant only, v2 access tokens, one app role (for applications, managed identities and users)
# and one delegated scope (for a signed-in user's token), both named by var.auth_permission.
resource "azuread_application" "api" {
  count                   = local.auth_create_registration ? 1 : 0
  display_name            = "Cloud Assessor appliance (${var.environment})"
  description             = "Caller authentication for the Cloud Assessor appliance. Managed by Terraform."
  sign_in_audience        = "AzureADMyOrg"
  prevent_duplicate_names = true
  owners                  = [data.azuread_client_config.current[0].object_id]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = local.auth_scope_id
      value                      = var.auth_permission
      type                       = "User"
      enabled                    = true
      admin_consent_display_name = "Read Cloud Assessor assessment results"
      admin_consent_description  = "Allows the app to read the Cloud Assessor assessment results on behalf of the signed-in user."
      user_consent_display_name  = "Read Cloud Assessor assessment results"
      user_consent_description   = "Allows the app to read the Cloud Assessor assessment results on your behalf."
    }
  }

  app_role {
    id                   = local.auth_role_id
    value                = var.auth_permission
    display_name         = var.auth_permission
    description          = "Read the Cloud Assessor assessment results."
    allowed_member_types = ["User", "Application"]
    enabled              = true
  }

  lifecycle {
    # azuread_application_identifier_uri owns the URI: it can only be set after the client id exists.
    ignore_changes = [identifier_uris]
  }
}

resource "azuread_application_identifier_uri" "api" {
  count          = local.auth_create_registration ? 1 : 0
  application_id = azuread_application.api[0].id
  identifier_uri = "api://${azuread_application.api[0].client_id}"
}

# app_role_assignment_required = true: Entra refuses to issue a token for this API to any user or application that has
# not been assigned to it, so a stranger in the tenant cannot even obtain a token the appliance would then have to turn
# away. Assignment is a second lock in front of the appliance's own token checks, not a replacement for them.
resource "azuread_service_principal" "api" {
  count                        = local.auth_create_registration ? 1 : 0
  client_id                    = azuread_application.api[0].client_id
  app_role_assignment_required = true
  owners                       = [data.azuread_client_config.current[0].object_id]
}

resource "azuread_app_role_assignment" "assigned" {
  for_each            = local.auth_create_registration ? toset(var.auth_assigned_object_ids) : toset([])
  app_role_id         = local.auth_role_id
  principal_object_id = each.value
  resource_object_id  = azuread_service_principal.api[0].object_id
}

resource "azuread_application_pre_authorized" "client" {
  for_each             = local.auth_create_registration ? toset(var.auth_preauthorized_client_ids) : toset([])
  application_id       = azuread_application.api[0].id
  authorized_client_id = each.value
  permission_ids       = [local.auth_scope_id]
}
