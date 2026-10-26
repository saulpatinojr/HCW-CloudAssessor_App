"""Terraform side of caller authentication (ticket CA-3): the plan refuses an externally reachable appliance without
sign-in, every CA_AUTH_* setting the code reads is wired, and the Entra registration holds no secret.

These are static checks on the HCL text, so they run everywhere (the boundary job has no Terraform). The behaviour of
the guard at plan time is proved by `terraform test` (infrastructure/terraform/appliance-azure/tests, run in the CI
`terraform` job); a plan against a real tenant is not run by any test."""

import re

import pytest

from cloud_assessor_appliance.config import DEFAULT_AUTH_ROLE, DEFAULT_AUTH_SCOPE

from ..conftest import ROOT

TF_DIR = ROOT / "infrastructure" / "terraform" / "appliance-azure"
CONFIG = ROOT / "src" / "cloud_assessor_appliance" / "config.py"
GUARD = "!var.external_enabled || var.auth_enabled || var.dangerously_allow_unauthenticated_external_ingress"


def _read(name: str) -> str:
    return (TF_DIR / name).read_text(encoding="utf-8")


def _block(text: str, header: str) -> str:
    """The body of the first HCL block that starts with `header`, found by matching braces."""
    start = text.index(header)
    depth = 0
    for i in range(text.index("{", start), len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start : i + 1]
    raise AssertionError(f"unbalanced braces after {header!r}")


def _variable(name: str) -> str:
    return _block(_read("variables.tf"), f'variable "{name}"')


def _blocks(text: str, header: str) -> list[str]:
    """Every HCL block that starts with `header` (a registration can declare several roles or scopes)."""
    found, at = [], 0
    while (start := text.find(header, at)) != -1:
        found.append(_block(text[start:], header))
        at = start + len(header)
    return found


def _resolve_value(expression: str, variables_tf: str) -> str:
    """The string a `value = ...` line stands for: a literal, or the default of the variable it names."""
    expression = expression.strip()
    if literal := re.fullmatch(r'"([^"$]*)"', expression):
        return literal.group(1)
    if named := re.fullmatch(r"var\.(\w+)", expression):
        default = re.search(r'default\s*=\s*"([^"]*)"', _block(variables_tf, f'variable "{named.group(1)}"'))
        assert default, f"variable {named.group(1)} has no string default to compare"
        return default.group(1)
    raise AssertionError(f"cannot resolve {expression!r} statically; use a literal or a variable with a default")


def registration_values(auth_tf: str, variables_tf: str) -> tuple[list[str], list[str]]:
    """(app role values, delegated scope values) of the registration in `auth_tf`."""

    def values(header: str) -> list[str]:
        found = []
        for block in _blocks(auth_tf, header):
            line = re.search(r"^\s*value\s*=\s*(.+)$", block, re.MULTILINE)
            assert line, f"{header} has no value"
            found.append(_resolve_value(line.group(1), variables_tf))
        return found

    return values("app_role {"), values("oauth2_permission_scope {")


def duplicated_values(auth_tf: str, variables_tf: str) -> set[str]:
    """Values used more than once across the app roles AND the scopes. Entra, and the azuread provider at plan time,
    refuse them ("duplicate value found"); the mock providers `terraform test` uses do not run that check."""
    roles, scopes = registration_values(auth_tf, variables_tf)
    every = roles + scopes
    return {v for v in every if every.count(v) > 1}


def _all_tf() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(TF_DIR.glob("*.tf")))


def test_ingress_is_a_variable_not_a_literal_true():
    main = _read("main.tf")
    assert not re.search(r"external_enabled\s*=\s*true", main)
    assert "external_enabled = var.external_enabled" in _block(main, 'resource "azurerm_container_app" "api"')


def test_safe_defaults_external_on_auth_off_override_off():
    assert re.search(r"default\s*=\s*true", _variable("external_enabled"))
    assert re.search(r"default\s*=\s*false", _variable("auth_enabled"))
    override = _variable("dangerously_allow_unauthenticated_external_ingress")
    assert re.search(r"default\s*=\s*false", override)
    assert "DANGEROUS" in override


def test_the_container_app_refuses_external_ingress_without_auth_unless_overridden():
    app = _block(_read("main.tf"), 'resource "azurerm_container_app" "api"')
    lifecycle = _block(app, "lifecycle")
    starts = [m.start() for m in re.finditer(r"precondition\s*\{", lifecycle)]
    preconditions = [_block(lifecycle[s:], "precondition") for s in starts]
    guard = [p for p in preconditions if GUARD in p]
    assert len(guard) == 1, "exactly one precondition carries the external-ingress guard"
    assert "error_message" in guard[0] and "dangerously_allow_unauthenticated_external_ingress" in guard[0]
    # the override is declared, used in the guard and described in the message; nothing else refers to it
    assert _all_tf().count("dangerously_allow_unauthenticated_external_ingress") >= 3


def test_public_results_needs_auth_in_the_plan_as_in_the_app():
    lifecycle = _block(_block(_read("main.tf"), 'resource "azurerm_container_app" "api"'), "lifecycle")
    assert "!var.public_results || var.auth_enabled" in lifecycle


def test_an_existing_registration_needs_a_tenant_and_an_audience_in_the_plan_as_in_the_app():
    lifecycle = _block(_block(_read("main.tf"), 'resource "azurerm_container_app" "api"'), "lifecycle")
    assert 'var.auth_tenant_id != "" && length(var.auth_audiences) > 0' in lifecycle


def test_every_ca_auth_setting_the_code_reads_is_set_by_terraform():
    read = set(re.findall(r'"(CA_AUTH_[A-Z_]+)"', CONFIG.read_text(encoding="utf-8")))
    assert {"CA_AUTH_ENABLED", "CA_AUTH_TENANT_ID", "CA_AUTH_AUDIENCE", "CA_AUTH_AUTHORITY_HOST"} <= read
    set_by_terraform = set(re.findall(r"\b(CA_AUTH_[A-Z_]+)\s*=", _read("auth.tf")))
    # CA_AUTH_JWKS_URL is deliberately unset: the code builds the address from the host and tenant.
    assert set_by_terraform == read - {"CA_AUTH_JWKS_URL"}
    assert 'dynamic "env"' in _read("main.tf") and "for_each = local.auth_env" in _read("main.tf")


def test_no_value_is_both_an_app_role_and_a_delegated_scope():
    """Found by the first real-tenant run: the registration declared `Assessment.Read` as an app role AND as a scope,
    and the azuread provider refused the plan with "duplicate value found" (provider source:
    applicationValidateRolesScopes in internal/services/applications/applications.go). Mock providers cannot see it,
    so check the HCL itself."""
    roles, scopes = registration_values(_read("auth.tf"), _read("variables.tf"))
    assert roles and scopes, "the registration declares at least one role and one scope"
    assert duplicated_values(_read("auth.tf"), _read("variables.tf")) == set()
    assert not set(roles) & set(scopes)


def test_the_duplicate_value_check_catches_the_defect_the_real_tenant_run_found():
    """The pre-fix shape: one variable named by both the role and the scope. The checker must report it."""
    variables = 'variable "auth_permission" {\n  default = "Assessment.Read"\n}\n'
    auth = (
        'resource "azuread_application" "api" {\n'
        "  api {\n    oauth2_permission_scope {\n      value = var.auth_permission\n    }\n  }\n"
        "  app_role {\n    value = var.auth_permission\n  }\n}\n"
    )
    assert duplicated_values(auth, variables) == {"Assessment.Read"}
    fixed = auth.replace("value = var.auth_permission\n    }\n  }", 'value = "access_as_user"\n    }\n  }')
    assert fixed != auth and duplicated_values(fixed, variables) == set()


def test_required_role_and_scope_match_the_code_defaults_and_the_registration_defines_both_kinds():
    assert DEFAULT_AUTH_ROLE != DEFAULT_AUTH_SCOPE
    assert re.search(rf'default\s*=\s*"{re.escape(DEFAULT_AUTH_ROLE)}"', _variable("auth_role_value"))
    assert re.search(rf'default\s*=\s*"{re.escape(DEFAULT_AUTH_SCOPE)}"', _variable("auth_scope_value"))
    # a plan that sets both to one value is refused by the variable, not only by the provider
    assert "var.auth_scope_value != var.auth_role_value" in _variable("auth_scope_value")
    auth = _read("auth.tf")
    assert "app_role {" in auth and "oauth2_permission_scope {" in auth
    assert "value                = var.auth_role_value" in _block(auth, "app_role {")
    assert "value                      = var.auth_scope_value" in _block(auth, "oauth2_permission_scope {")
    # the settings the appliance reads name the same role and scope the registration defines
    assert "CA_AUTH_REQUIRED_ROLES     = var.auth_role_value" in auth
    assert "CA_AUTH_REQUIRED_SCOPES    = var.auth_scope_value" in auth
    # the role is assigned, and the pre-authorised client is given the scope, by their own ids
    assignment = _block(auth, 'resource "azuread_app_role_assignment" "assigned"')
    assert "app_role_id         = local.auth_role_id" in assignment
    preauthorized = _block(auth, 'resource "azuread_application_pre_authorized" "client"')
    assert "permission_ids       = [local.auth_scope_id]" in preauthorized
    assert "${var.auth_role_value}" in auth and "${var.auth_scope_value}" in auth
    assert "auth_permission" not in _all_tf()
    # the code validates the v2 issuer and the client-id audience, and accepts the api:// URI too
    assert "requested_access_token_version = 2" in auth
    assert 'sign_in_audience        = "AzureADMyOrg"' in auth
    assert '"api://${azuread_application.api[0].client_id}"' in auth


def test_service_principal_requires_assignment():
    sp = _block(_read("auth.tf"), 'resource "azuread_service_principal" "api"')
    assert "app_role_assignment_required = true" in sp


def test_no_client_secret_certificate_or_password_in_terraform():
    text = _all_tf()
    for forbidden in (
        "azuread_application_password",
        "azuread_application_certificate",
        "azuread_service_principal_password",
        "azuread_service_principal_certificate",
        "azuread_application_federated_identity_credential",
        "azuread_application_flexible_federated_identity_credential",
        "client_secret",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
        "TURNSTILE_SECRET",
    ):
        assert forbidden not in text, forbidden


def test_providers_are_pinned_and_locked_with_hashes():
    main = _read("main.tf")
    required = _block(main, "required_providers")
    assert re.search(r'azurerm\s*=\s*\{ source = "hashicorp/azurerm", version = "~> \d+\.\d+" \}', required)
    assert re.search(r'azuread\s*=\s*\{ source = "hashicorp/azuread", version = "~> \d+\.\d+" \}', required)
    lock = (TF_DIR / ".terraform.lock.hcl").read_text(encoding="utf-8")
    for provider in ("azurerm", "azuread"):
        entry = _block(lock, f'provider "registry.terraform.io/hashicorp/{provider}"')
        assert re.search(r'version\s*=\s*"\d+\.\d+\.\d+"', entry)
        assert entry.count('"h1:') >= 2 and entry.count('"zh:') >= 1


def test_terraform_test_file_exercises_the_guard_both_ways():
    files = sorted((TF_DIR / "tests").glob("*.tftest.hcl"))
    assert [f.name for f in files] == ["budget_notifications.tftest.hcl", "caller_authentication.tftest.hcl"]
    text = (TF_DIR / "tests" / "caller_authentication.tftest.hcl").read_text(encoding="utf-8")
    assert 'mock_provider "azurerm"' in text and 'mock_provider "azuread"' in text
    runs = re.findall(r'^run "([^"]+)"', text, re.MULTILINE)
    assert "default_external_ingress_without_auth_is_refused" in runs
    assert "override_allows_external_ingress_without_auth_and_says_so" in runs
    assert "private_ingress_plans_without_auth" in runs
    assert "auth_enabled_creates_the_registration_and_wires_the_settings" in runs
    assert text.count("expect_failures = [azurerm_container_app.api]") >= 5
    assert not re.search(r"command\s*=\s*apply", text), "plan-only: a test must never create anything"


def test_budget_exists_only_with_a_recipient_and_the_empty_default_is_tested():
    """Ticket #60: azurerm needs a recipient on every budget notification, so the budget is conditional on
    `alert_emails` (an empty list is the documented opt-out) and `terraform test` plans both cases."""
    budget = _block(_read("main.tf"), 'resource "azurerm_consumption_budget_resource_group" "app"')
    assert "count             = length(var.alert_emails) > 0 ? 1 : 0" in budget
    assert "for_each = [80, 100]" in budget
    variable = _block(_read("variables.tf"), 'variable "alert_emails"')
    assert "default     = []" in variable and "validation" in variable
    assert 'output "budget_notifications"' in _read("outputs.tf")
    text = (TF_DIR / "tests" / "budget_notifications.tftest.hcl").read_text(encoding="utf-8")
    runs = re.findall(r'^run "([^"]+)"', text, re.MULTILINE)
    assert "empty_alert_emails_plans_without_a_budget" in runs
    assert "one_recipient_creates_the_budget_with_both_notifications" in runs
    assert not re.search(r"command\s*=\s*apply", text), "plan-only: a test must never create anything"


def test_tfvars_example_stays_a_plan_that_the_guard_accepts():
    example = _read("terraform.tfvars.example")
    assert re.search(r"^auth_enabled\s*=\s*true", example, re.MULTILINE)
    assert not re.search(r"^\s*dangerously_allow_unauthenticated_external_ingress\s*=", example, re.MULTILINE)


@pytest.mark.parametrize("needle", ["Sign-in (Microsoft Entra ID)", "Real-tenant verification runbook"])
def test_readme_documents_how_to_turn_sign_in_on_and_how_to_verify_it(needle):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert needle in readme
    assert "NOT verified" in readme
    assert "dangerously_allow_unauthenticated_external_ingress" in readme
