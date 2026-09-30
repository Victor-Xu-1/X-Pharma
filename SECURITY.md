# Security policy

This repository is a development version. Production operators must verify
tenant isolation, data licenses, identity configuration, TLS, backups, capacity
and deployment-specific controls before providing a public service.

Report vulnerabilities through GitHub's private vulnerability reporting for
this repository when available. Otherwise contact the maintainer privately
before sharing exploit details. Do not include secrets, medical records or
customer data in public issues.

Include the affected revision, configuration assumptions, minimal reproduction,
impact and suggested fix. Sanitize tokens and personal data.

Keep dependencies and container digests locked. Security fixes must retain
authentication, RLS, fail-closed parsing and auditable errors. Do not add broad
suppressions to make a failing scan pass.

Credentials belong in an ignored environment or deployment secret store.
Rotate compromised credentials before treating removal from Git as remediation.
Private historical development data is not included in this public repository.
