# Security policy

Report vulnerabilities privately through GitHub private vulnerability reporting on this repository, or to security@hybridcloudworks.com. Please do not open public issues for security findings. Expect an acknowledgement within 3 business days.

Scope highlights: the appliance reads the client's own Azure scope with a user-assigned managed identity holding `Reader` and `Cost Management Reader` only; it has no upload route, no execution surface and no stored credential, refuses any client-secret shaped environment at startup, holds results in memory only and logs no resource data. The engine (`packages/cloud-assessor-core`) is published from here and consumed by `HCW-CloudAssessor_AddOn`; report engine issues here. Supported version: `main` and the latest `v*` tag.
