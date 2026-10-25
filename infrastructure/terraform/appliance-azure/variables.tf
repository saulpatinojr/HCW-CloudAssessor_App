variable "prefix" {
  type        = string
  description = "Resource name prefix. [REVIEW REQUIRED] section 12 names assume hcwca."
  default     = "hcwca"
}
variable "environment" {
  type    = string
  default = "prod"
}
variable "location" {
  type        = string
  description = "Azure region. [REVIEW REQUIRED] centralus is assumed."
  default     = "centralus"
}
variable "location_short" {
  type    = string
  default = "cus"
}
variable "image_ref" {
  type        = string
  description = "The appliance image by digest, e.g. docker.io/hybridcloudworks/img-ca-appliance-app@sha256:<digest>. No default, so a plan never pulls a floating tag."
  validation {
    condition     = can(regex("^docker\\.io/hybridcloudworks/img-ca-appliance-app@sha256:[0-9a-f]{64}$", var.image_ref))
    error_message = "image_ref must be docker.io/hybridcloudworks/img-ca-appliance-app@sha256:<64 hex>."
  }
}
variable "scope_ids" {
  type        = list(string)
  description = "Subscriptions or resource groups the appliance may read (Reader + Cost Management Reader): /subscriptions/<guid> or /subscriptions/<guid>/resourceGroups/<name>. Also the CA_SCOPES value."
  validation {
    condition     = length(var.scope_ids) > 0 && alltrue([for s in var.scope_ids : can(regex("^/subscriptions/[0-9a-fA-F-]{36}(/resourceGroups/[^/]+)?$", s))])
    error_message = "scope_ids must hold at least one /subscriptions/<guid> or /subscriptions/<guid>/resourceGroups/<name> entry."
  }
}
variable "refresh_minutes" {
  type    = number
  default = 60
}
variable "public_results" {
  type        = bool
  description = "Release gate for the results routes (CA_PUBLIC_RESULTS). Set true only after REVIEW.md R-006 is recorded, and only with auth_enabled = true (the appliance refuses to start otherwise, and so does the plan)."
  default     = false
}
variable "external_enabled" {
  type        = bool
  description = "Whether the Container App ingress is reachable from outside its environment. The default is true, which the plan refuses unless auth_enabled = true or the override below is set (REVIEW.md R-009, ticket CA-3). false makes the ingress internal, the private-only posture."
  default     = true
}
variable "auth_enabled" {
  type        = bool
  description = "Require a Microsoft Entra ID access token on every route except GET /api/health (CA_AUTH_ENABLED). This is the supported way to run an externally reachable appliance."
  default     = false
}
variable "dangerously_allow_unauthenticated_external_ingress" {
  type        = bool
  description = "DANGEROUS. Lets the plan accept external_enabled = true with auth_enabled = false, which publishes an appliance that does not check who calls it. Leave false. Setting it is a recorded owner decision (REVIEW.md), not a convenience."
  default     = false
}
variable "auth_create_app_registration" {
  type        = bool
  description = "With auth_enabled, create the Entra application, its Assessment.Read app role and delegated scope, and its service principal (needs the azuread permissions in README.md). false uses an existing registration described by auth_tenant_id and auth_audiences."
  default     = true
}
variable "auth_tenant_id" {
  type        = string
  description = "Existing-registration mode only (auth_create_app_registration = false): the Entra tenant (directory) id whose tokens are accepted (CA_AUTH_TENANT_ID)."
  default     = ""
  validation {
    condition     = var.auth_tenant_id == "" || can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.auth_tenant_id))
    error_message = "auth_tenant_id must be empty or a GUID."
  }
}
variable "auth_audiences" {
  type        = list(string)
  description = "Existing-registration mode only: the audiences (aud claim) accepted, the application (client) id and/or its api:// URI (CA_AUTH_AUDIENCE)."
  default     = []
  validation {
    condition     = alltrue([for a in var.auth_audiences : can(regex("^[^\\s,]+$", a))])
    error_message = "auth_audiences entries must not be empty or contain spaces or commas."
  }
}
variable "auth_authority_host" {
  type        = string
  description = "The Entra sign-in host name only, no scheme, path or port (CA_AUTH_AUTHORITY_HOST). It builds the issuer and the signing-key address. Sovereign clouds use their own host."
  default     = "login.microsoftonline.com"
  validation {
    condition     = can(regex("^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.auth_authority_host))
    error_message = "auth_authority_host must be a lower-case host name only (no scheme, path or port)."
  }
}
variable "auth_permission" {
  type        = string
  description = "The app role and delegated scope a token must carry (CA_AUTH_REQUIRED_ROLES and CA_AUTH_REQUIRED_SCOPES). The registration this module creates defines both with this value; an existing registration must define at least one."
  default     = "Assessment.Read"
  validation {
    condition     = can(regex("^[A-Za-z0-9._-]{1,120}$", var.auth_permission))
    error_message = "auth_permission must be 1 to 120 letters, digits, dots, dashes or underscores."
  }
}
variable "auth_clock_skew_seconds" {
  type        = number
  description = "Clock skew allowed when checking exp and nbf (CA_AUTH_CLOCK_SKEW_SECONDS), 0 to 300."
  default     = 60
  validation {
    condition     = var.auth_clock_skew_seconds >= 0 && var.auth_clock_skew_seconds <= 300 && floor(var.auth_clock_skew_seconds) == var.auth_clock_skew_seconds
    error_message = "auth_clock_skew_seconds must be a whole number from 0 to 300."
  }
}
variable "auth_assigned_object_ids" {
  type        = list(string)
  description = "Created-registration mode: object ids of the users, groups or service principals (including managed identities) given the Assessment.Read app role. The service principal requires assignment, so only these can sign in. Groups need Entra ID P1 or P2."
  default     = []
  validation {
    condition     = alltrue([for o in var.auth_assigned_object_ids : can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", o))])
    error_message = "auth_assigned_object_ids entries must be GUIDs (Entra object ids)."
  }
}
variable "auth_preauthorized_client_ids" {
  type        = list(string)
  description = "Created-registration mode: client application ids allowed to request the delegated scope without a consent prompt. Empty by default. For the real-tenant check in README.md, a sandbox may list the Azure CLI (04b07795-8ddb-461a-bbee-02f9e1bf7b46); do not do that in production."
  default     = []
  validation {
    condition     = alltrue([for c in var.auth_preauthorized_client_ids : can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", c))])
    error_message = "auth_preauthorized_client_ids entries must be GUIDs."
  }
}
variable "monthly_budget" {
  type        = number
  description = "Monthly budget amount (in the billing currency) for the appliance's resource group."
  default     = 50
}
variable "budget_start_date" {
  type        = string
  description = "First day of the month the budget starts, RFC 3339 (e.g. the current month's first day). Azure requires the first of a month, not more than twelve months ahead; no default, because any fixed date expires."
  validation {
    condition     = can(regex("^[0-9]{4}-(0[1-9]|1[0-2])-01T00:00:00Z$", var.budget_start_date))
    error_message = "budget_start_date must be the first day of a month in RFC 3339 UTC, e.g. 2026-11-01T00:00:00Z."
  }
}
variable "alert_emails" {
  type        = list(string)
  description = "Recipients of the 80 and 100 percent budget notifications; empty disables the notifications."
  default     = []
}
variable "custom_domain" {
  type        = string
  description = "Optional custom hostname for the app; empty creates none."
  default     = ""
}
variable "tags" {
  type    = map(string)
  default = {}
}
