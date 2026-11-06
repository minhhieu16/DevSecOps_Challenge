<!-- Control: change management evidence (ISO A.8.32, HIPAA 164.308(a)(8)). -->
## Ticket
LIN-___ / SEC-___

## Change type
- [ ] Code
- [ ] IaC (Pulumi / Serverless)
- [ ] Config / feature flag
- [ ] Hotfix-ops (persistent change during an incident; add label `hotfix-ops`)

## Description

## Blast radius
Services / data classes affected (phi / pii / internal / public), environments:

## Rollback
How to revert (revert PR, previous version, data considerations):

## Authored with a coding agent?
- [ ] Yes (which tool/session):
- [ ] No

## Reviewer checklist
- [ ] Pulumi preview and Serverless change-set diff reviewed (prod and nonprod)
- [ ] CrossGuard policies passed (no waived `mandatory` policy)
- [ ] No secrets or secret values in diff (definitions/references only)
- [ ] Naming `<env>-<service>-<name>` and required tags (env, service, owner, data-class)
- [ ] No new IAM wildcard; roles in nonprod use `nonprod-boundary`
