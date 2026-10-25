# Budget notifications (ticket #60). Plan-only, with mock providers: no credential, no network, no tenant and no
# subscription is touched, so `terraform test` is safe to run anywhere. Why the budget is conditional: azurerm requires
# at least one `notification` block, each with a recipient, on azurerm_consumption_budget_resource_group, so a budget
# with no recipient cannot be planned, and a budget nobody is told about is not a spend guard. An empty alert_emails
# therefore means "no budget" (an opt-out the output states), never a failed plan.

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
  # A private ingress needs no sign-in to plan, which keeps these runs about the budget only.
  external_enabled = false
}

# The documented default: no recipients, so no budget, and the plan succeeds (it used to fail on the real provider).
run "empty_alert_emails_plans_without_a_budget" {
  command = plan
  variables {
    alert_emails = []
  }
  assert {
    condition     = length(azurerm_consumption_budget_resource_group.app) == 0
    error_message = "no recipient, no budget"
  }
  assert {
    condition     = startswith(output.budget_notifications, "none")
    error_message = "the opt-out must be stated in the output"
  }
}

# Leaving alert_emails unset is the same thing as the empty list.
run "default_alert_emails_is_the_opt_out" {
  command = plan
  assert {
    condition     = length(azurerm_consumption_budget_resource_group.app) == 0
    error_message = "the default must plan, without a budget"
  }
}

run "one_recipient_creates_the_budget_with_both_notifications" {
  command = plan
  variables {
    alert_emails = ["owner@example.test"]
  }
  assert {
    condition     = length(azurerm_consumption_budget_resource_group.app) == 1
    error_message = "one recipient creates the budget"
  }
  assert {
    condition     = join(",", sort([for n in azurerm_consumption_budget_resource_group.app[0].notification : tostring(n.threshold)])) == "100,80"
    error_message = "notifications at 80 and 100 percent"
  }
  assert {
    condition     = alltrue([for n in azurerm_consumption_budget_resource_group.app[0].notification : join(",", n.contact_emails) == "owner@example.test" && n.threshold_type == "Actual"])
    error_message = "every notification reaches the recipient and watches actual spend"
  }
  assert {
    condition     = startswith(output.budget_notifications, "80 and 100 percent")
    error_message = "the output states who is told"
  }
}

run "several_recipients_all_receive_the_notifications" {
  command = plan
  variables {
    alert_emails = ["owner@example.test", "finance@example.test"]
  }
  assert {
    condition     = alltrue([for n in azurerm_consumption_budget_resource_group.app[0].notification : length(n.contact_emails) == 2])
    error_message = "all recipients are on every notification"
  }
}

# Validation: an entry that is not an address, a blank entry and a repeated entry are refused with a clear message.
run "an_entry_that_is_not_an_email_address_is_refused" {
  command = plan
  variables {
    alert_emails = ["not-an-address"]
  }
  expect_failures = [var.alert_emails]
}

run "a_blank_entry_is_refused" {
  command = plan
  variables {
    alert_emails = ["owner@example.test", ""]
  }
  expect_failures = [var.alert_emails]
}

run "a_repeated_entry_is_refused" {
  command = plan
  variables {
    alert_emails = ["owner@example.test", "owner@example.test"]
  }
  expect_failures = [var.alert_emails]
}
