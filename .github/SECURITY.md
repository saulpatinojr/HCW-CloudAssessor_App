# Security policy

## Reporting a vulnerability

Please report a suspected vulnerability privately, not in a public issue.

1. Open <https://github.com/saulpatinojr/HCW-CloudAssessor_App/security/advisories/new> (or go to the repository's
   **Security** tab and choose **Report a vulnerability**). This is GitHub private vulnerability reporting.
2. Describe what you found. Only the maintainers and you can see the report.

Do not put exploit details, credentials, tokens, private endpoints, tenant or subscription identifiers, personal data or
customer data in a public issue, a pull request, a comment or a commit message. If the private form is not available to
you, open a minimal public issue that asks for a secure contact and says nothing about the problem itself. Only test
systems and data you own or are explicitly allowed to assess.

When it is safe to do so, please include the affected version (the `version` that `GET /api/health` reports, a release
tag or a commit), the component, the impact and any preconditions in plain words, steps to reproduce with sensitive
values removed, and any workaround you know of.

## What is in scope

The appliance reads the client's own Azure scope with a user-assigned managed identity holding `Reader` and
`Cost Management Reader` only; it has no upload route, no execution surface and no stored credential, refuses any
client-secret shaped environment at startup, holds results in memory only and logs no resource data. The engine
(`packages/cloud-assessor-core`) is published from here and consumed by `HCW-CloudAssessor_AddOn`; report engine issues
here. The container images, the Terraform in `infrastructure/`, the workflows in `.github/` and any example, test,
fixture or document that exposes a secret or sensitive data are in scope too. The lab edition,
[HCW-CloudAssessor_AddOn](https://github.com/saulpatinojr/HCW-CloudAssessor_AddOn), has its own repository and policy.

## If you find a secret

Treat any secret in a commit, issue, log, artifact or document as disclosed. Tell the maintainers privately (use the
form above), keep only the minimum evidence, and do not try to use it. The maintainers rotate or revoke the value.

## What happens next

Reports are read and triaged by the repository owner named in `.github/CODEOWNERS`. This is a one-maintainer project and
no response time is promised. Please keep the report private until the maintainers confirm that disclosure is
coordinated. Credit is given in the advisory if you want it.

## Supported versions

| Version or branch | Supported |
| --- | --- |
| `main` | Yes |
| The latest `v*` release | Yes |
| Earlier releases | No; update to the latest one |
