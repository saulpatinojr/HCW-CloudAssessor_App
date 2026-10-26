output "app_fqdn" {
  value = azurerm_container_app.api.ingress[0].fqdn
}
output "identity_client_id" {
  value = azurerm_user_assigned_identity.app.client_id
}
output "identity_principal_id" {
  value = azurerm_user_assigned_identity.app.principal_id
}
output "resource_group_name" {
  value = azurerm_resource_group.app.name
}
output "budget_notifications" {
  description = "Plain-words state of the spend guard: who is told at 80 and 100 percent, or that no budget exists because alert_emails is empty."
  value = length(var.alert_emails) > 0 ? "80 and 100 percent of ${var.monthly_budget} (actual spend) notify ${length(var.alert_emails)} recipient(s)" : (
    "none: alert_emails is empty, so no budget is created (set alert_emails to create one)"
  )
}
output "caller_authentication" {
  description = "Plain-words posture of the deployment: entra, none (private ingress), or the loud NONE when the override is set."
  value = var.auth_enabled ? "entra" : (
    var.external_enabled ? "NONE: externally reachable WITHOUT caller authentication (dangerously_allow_unauthenticated_external_ingress)" : "none: ingress is private (external_enabled = false)"
  )
}
output "appliance_auth_settings" {
  description = "The CA_AUTH_* settings the Container App receives. Identifiers only; there is no secret here."
  value       = local.auth_env
}
output "auth_application_client_id" {
  description = "Client id of the API registration this module created; null when it did not create one."
  value       = one(azuread_application.api[*].client_id)
}
output "auth_scope" {
  description = "The scope to request a delegated token with (az account get-access-token --scope ...); null unless the registration was created here."
  value       = local.auth_create_registration ? "api://${azuread_application.api[0].client_id}/${var.auth_scope_value}" : null
}
