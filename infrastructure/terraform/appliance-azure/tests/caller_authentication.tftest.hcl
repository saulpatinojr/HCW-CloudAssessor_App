# Caller authentication guard and plumbing (ticket CA-3). Plan-only, with mock providers: no credential, no network, no
# tenant and no subscription is touched, so `terraform test` is safe to run anywhere (CI runs it without any login).
# What these runs prove is what the configuration does at plan time. They do not prove how Entra or the appliance behave
# in a real tenant (README.md, "Sign-in", has the real-tenant runbook for that).

mock_provider "azurerm" {}

mock_provider "azuread" {
  mock_data "azuread_client_config" {
    defaults = {
      tenant_id = "00000000-0000-4000-8000-000000000001"
      object_id = "00000000-0000-4000-8000-000000000002"
    }
  }
}

variables {
  image_ref         = "docker.io/hybridcloudworks/img-ca-appliance-app@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  scope_ids         = ["/subscriptions/00000000-0000-0000-0000-000000000001"]
  budget_start_date = "2026-11-01T00:00:00Z"
  # alert_emails is deliberately not set here: every run below uses its default (empty), which is what a deployer who
  # sets nothing gets. The budget runs at the end of this file set it explicitly.
}

# The safe default: with nothing set, the ingress is external and there is no sign-in, so the plan must fail.
run "default_external_ingress_without_auth_is_refused" {
  command         = plan
  expect_failures = [azurerm_container_app.api]
}

run "explicit_external_ingress_without_auth_is_refused" {
  command = plan
  variables {
    external_enabled = true
    auth_enabled     = false
  }
  expect_failures = [azurerm_container_app.api]
}

# The override must be set on purpose, and it says so in the output.
run "override_allows_external_ingress_without_auth_and_says_so" {
  command = plan
  variables {
    dangerously_allow_unauthenticated_external_ingress = true
  }
  assert {
    condition     = startswith(output.caller_authentication, "NONE")
    error_message = "the override must be loud in the output"
  }
  assert {
    condition     = output.appliance_auth_settings == { CA_AUTH_ENABLED = "false" }
    error_message = "with sign-in off only CA_AUTH_ENABLED=false is set"
  }
}

# The override only relaxes the ingress rule; it does not let public results through without sign-in.
run "override_does_not_allow_public_results_without_auth" {
  command = plan
  variables {
    dangerously_allow_unauthenticated_external_ingress = true
    public_results                                     = true
  }
  expect_failures = [azurerm_container_app.api]
}

# The other supported posture: a private ingress needs no sign-in to plan.
run "private_ingress_plans_without_auth" {
  command = plan
  variables {
    external_enabled = false
  }
  assert {
    condition     = azurerm_container_app.api.ingress[0].external_enabled == false
    error_message = "external_enabled must reach the ingress"
  }
  assert {
    condition     = startswith(output.caller_authentication, "none")
    error_message = "a private ingress is reported as such"
  }
  assert {
    condition     = length(azuread_application.api) == 0
    error_message = "no Entra application without auth_enabled"
  }
}

# Sign-in on, registration created here: external ingress is allowed and every CA_AUTH_* value is wired.
run "auth_enabled_creates_the_registration_and_wires_the_settings" {
  command = plan
  variables {
    auth_enabled                  = true
    auth_assigned_object_ids      = ["00000000-0000-4000-8000-000000000006"]
    auth_preauthorized_client_ids = ["04b07795-8ddb-461a-bbee-02f9e1bf7b46"]
  }
  # A computed value is unknown at plan time; the override stands in for what Entra would return after an apply.
  override_resource {
    target          = azuread_application.api[0]
    override_during = plan
    values = {
      id        = "/applications/00000000-0000-4000-8000-000000000003"
      client_id = "00000000-0000-4000-8000-000000000004"
    }
  }
  override_resource {
    target          = azuread_service_principal.api[0]
    override_during = plan
    values = {
      object_id = "00000000-0000-4000-8000-000000000005"
    }
  }
  assert {
    condition     = output.caller_authentication == "entra"
    error_message = "sign-in on is reported as entra"
  }
  assert {
    condition = output.appliance_auth_settings == {
      CA_AUTH_ENABLED            = "true"
      CA_AUTH_TENANT_ID          = "00000000-0000-4000-8000-000000000001"
      CA_AUTH_AUDIENCE           = "00000000-0000-4000-8000-000000000004 api://00000000-0000-4000-8000-000000000004"
      CA_AUTH_AUTHORITY_HOST     = "login.microsoftonline.com"
      CA_AUTH_CLOCK_SKEW_SECONDS = "60"
      CA_AUTH_REQUIRED_ROLES     = "Assessment.Read"
      CA_AUTH_REQUIRED_SCOPES    = "Assessment.Read"
    }
    error_message = "the CA_AUTH_* settings must match what entra.py validates"
  }
  assert {
    condition     = azuread_service_principal.api[0].app_role_assignment_required == true
    error_message = "assignment must be required, so only assigned callers can obtain a token"
  }
  assert {
    condition     = one([for a in azuread_application.api[0].api : a.requested_access_token_version]) == 2
    error_message = "v2 tokens, whose issuer and audience the code expects"
  }
  assert {
    condition     = azuread_application.api[0].sign_in_audience == "AzureADMyOrg"
    error_message = "single tenant only"
  }
  assert {
    condition     = one([for r in azuread_application.api[0].app_role : r.value]) == "Assessment.Read"
    error_message = "the app role the code requires"
  }
  assert {
    condition     = one([for a in azuread_application.api[0].api : one([for s in a.oauth2_permission_scope : s.value])]) == "Assessment.Read"
    error_message = "the delegated scope the code requires"
  }
  assert {
    condition     = length(azuread_app_role_assignment.assigned) == 1 && length(azuread_application_pre_authorized.client) == 1
    error_message = "the assignment and the pre-authorized client are planned"
  }
  assert {
    condition     = output.auth_scope == "api://00000000-0000-4000-8000-000000000004/Assessment.Read"
    error_message = "the scope to request a token with"
  }
}

# An existing registration: nothing is created in Entra, the inputs are passed through.
run "existing_registration_passes_its_values_through" {
  command = plan
  variables {
    auth_enabled                 = true
    auth_create_app_registration = false
    auth_tenant_id               = "00000000-0000-4000-8000-0000000000aa"
    auth_audiences               = ["api://hcw-sample-assessor", "00000000-0000-4000-8000-0000000000bb"]
    auth_authority_host          = "login.example.test"
    auth_permission              = "Assessment.Read"
    auth_clock_skew_seconds      = 30
  }
  assert {
    condition     = length(azuread_application.api) == 0 && length(azuread_service_principal.api) == 0
    error_message = "nothing is created in Entra for an existing registration"
  }
  assert {
    condition = output.appliance_auth_settings == {
      CA_AUTH_ENABLED            = "true"
      CA_AUTH_TENANT_ID          = "00000000-0000-4000-8000-0000000000aa"
      CA_AUTH_AUDIENCE           = "api://hcw-sample-assessor 00000000-0000-4000-8000-0000000000bb"
      CA_AUTH_AUTHORITY_HOST     = "login.example.test"
      CA_AUTH_CLOCK_SKEW_SECONDS = "30"
      CA_AUTH_REQUIRED_ROLES     = "Assessment.Read"
      CA_AUTH_REQUIRED_SCOPES    = "Assessment.Read"
    }
    error_message = "the CA_AUTH_* settings are the inputs"
  }
}

# The appliance refuses to start without a tenant and an audience, so the plan refuses first.
run "existing_registration_without_tenant_or_audience_is_refused" {
  command = plan
  variables {
    auth_enabled                 = true
    auth_create_app_registration = false
  }
  expect_failures = [azurerm_container_app.api]
}

run "assignments_without_a_created_registration_are_refused" {
  command = plan
  variables {
    auth_enabled                 = true
    auth_create_app_registration = false
    auth_tenant_id               = "00000000-0000-4000-8000-0000000000aa"
    auth_audiences               = ["api://hcw-sample-assessor"]
    auth_assigned_object_ids     = ["00000000-0000-4000-8000-000000000006"]
  }
  expect_failures = [azurerm_container_app.api]
}

# Public results need sign-in, as in the appliance's own startup check.
run "public_results_with_auth_plans" {
  command = plan
  variables {
    auth_enabled   = true
    public_results = true
  }
  assert {
    condition     = output.caller_authentication == "entra"
    error_message = "public results with sign-in plan"
  }
}

run "public_results_without_auth_is_refused" {
  command = plan
  variables {
    external_enabled = false
    public_results   = true
  }
  expect_failures = [azurerm_container_app.api]
}

# Input validation.
run "authority_host_must_be_a_bare_host_name" {
  command = plan
  variables {
    auth_enabled        = true
    auth_authority_host = "https://login.microsoftonline.com/"
  }
  expect_failures = [var.auth_authority_host]
}

run "tenant_id_must_be_a_guid" {
  command = plan
  variables {
    auth_enabled                 = true
    auth_create_app_registration = false
    auth_tenant_id               = "not-a-guid"
  }
  expect_failures = [var.auth_tenant_id]
}

run "clock_skew_is_bounded" {
  command = plan
  variables {
    auth_enabled            = true
    auth_clock_skew_seconds = 301
  }
  expect_failures = [var.auth_clock_skew_seconds]
}

run "audience_entries_must_not_hold_spaces" {
  command = plan
  variables {
    auth_enabled                 = true
    auth_create_app_registration = false
    auth_tenant_id               = "00000000-0000-4000-8000-0000000000aa"
    auth_audiences               = ["two words"]
  }
  expect_failures = [var.auth_audiences]
}

# Budget (ticket CA-12). The provider needs at least one notification, and a notification needs a recipient, so the
# budget exists only when at least one alert e-mail is given. The default plan (empty list) must succeed without it.
run "default_alert_emails_plans_without_a_budget" {
  command = plan
  variables {
    auth_enabled = true
  }
  assert {
    condition     = length(azurerm_consumption_budget_resource_group.app) == 0
    error_message = "with no alert e-mail there is no budget, because the provider cannot create one without a recipient"
  }
  assert {
    condition     = startswith(output.budget, "none")
    error_message = "the output must say plainly that no budget is created"
  }
}

run "one_alert_email_creates_the_budget_with_both_notifications" {
  command = plan
  variables {
    auth_enabled = true
    alert_emails = ["owner@example.test"]
  }
  assert {
    condition     = length(azurerm_consumption_budget_resource_group.app) == 1
    error_message = "one recipient creates the budget"
  }
  assert {
    condition     = toset([for n in azurerm_consumption_budget_resource_group.app[0].notification : n.threshold]) == toset([80, 100])
    error_message = "the budget notifies at 80 and 100 percent"
  }
  assert {
    condition     = alltrue([for n in azurerm_consumption_budget_resource_group.app[0].notification : join(",", n.contact_emails) == "owner@example.test"])
    error_message = "every notification goes to the given recipient"
  }
  assert {
    condition     = startswith(output.budget, "created")
    error_message = "the output says the budget is created"
  }
}

run "alert_email_must_be_an_address" {
  command = plan
  variables {
    auth_enabled = true
    alert_emails = [""]
  }
  expect_failures = [var.alert_emails]
}
