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
  description = "The appliance image by digest, e.g. docker.io/hybridcloudworks/hcw-cloud-assessor-appliance@sha256:<digest>. No default, so a plan never pulls a floating tag."
  validation {
    condition     = can(regex("^docker\\.io/hybridcloudworks/hcw-cloud-assessor-appliance@sha256:[0-9a-f]{64}$", var.image_ref))
    error_message = "image_ref must be docker.io/hybridcloudworks/hcw-cloud-assessor-appliance@sha256:<64 hex>."
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
  description = "Release gate for the results routes (CA_PUBLIC_RESULTS). Set true only after REVIEW.md R-006 and R-009 are recorded."
  default     = false
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
