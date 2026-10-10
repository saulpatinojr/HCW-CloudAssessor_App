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
