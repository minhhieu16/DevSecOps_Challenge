# 08 — Compliance Mapping: ISO 27001:2022 and HIPAA Security Rule

> Annex A titles follow ISO/IEC 27001:2022 (titles checked against a secondary source; verify against the standard text before the audit).
> HIPAA references are to 45 CFR Part 164 Subpart C. Req. = Required, Addr. = Addressable implementation specification.
> This mapping covers the **coding-agent and DevSecOps scope**. It is not the full ISMS (HR, physical, supplier contracts etc. are out of scope).

## 1. ISO/IEC 27001:2022 Annex A

| Control | How the framework meets it | Evidence | Doc |
|---|---|---|---|
| A.5.1 Policies for information security | Agent usage policy + this framework, versioned in Git | `agent-platform/docs/`, PR history | [04](04-agent-guardrails.md) |
| A.5.15 Access control | Permission sets per role; deny-prod; resource policies | IAM policies in Git, Identity Center export | [02](02-access-model.md) |
| A.5.16 Identity management | SSO for humans; separate agent permission set; OIDC for pipelines | Identity Center, OIDC trust policies | [02](02-access-model.md) |
| A.5.17 Authentication information | Secrets in vault, rotation, never in Git or agent context | CrossGuard results, Prowler checks, DET-003 | [06](06-secrets-and-config.md) |
| A.5.18 Access rights | TEAM requests/approvals; quarterly access review | TEAM logs, review records | [02](02-access-model.md) |
| A.5.23 Information security for use of cloud services | Managed settings, MCP/plugin review, cloud guardrails | MCP review records, managed settings history | [04](04-agent-guardrails.md) |
| A.5.24–A.5.28 Incident management (planning, assessment, response, learning, evidence) | Incident flow, break-glass, postmortems, Object Lock on logs | Linear incidents, postmortems, audit logs | [05](05-debug-and-incident.md) |
| A.8.2 Privileged access rights | No standing prod write; break-glass with 2 approvers; JIT with expiry | TEAM logs, DET-004, quarterly test | [02](02-access-model.md), [05](05-debug-and-incident.md) |
| A.8.3 Information access restriction | PHI buckets via VPC endpoint only; prod-debug denies PHI | Resource policies, KMS key policies | [02](02-access-model.md) |
| A.8.4 Access to source code | Rulesets, CODEOWNERS, SSO-enforced GitHub org | Ruleset JSON, GitHub audit log | [03](03-change-workflow.md) |
| A.8.7 Protection against malware | GuardDuty (incl. malware protection where enabled), pinned dependencies, plugin allowlist | GuardDuty findings, marketplace config | [04](04-agent-guardrails.md) |
| A.8.9 Configuration management | IaC as the only path; CrossGuard; drift detection | PR history, CrossGuard results, Prowler | [03](03-change-workflow.md) |
| A.8.15 Logging | CloudTrail/GCP/k0s/GitHub/OTel → Object Lock storage | Audit bucket configuration, retention policy | [07](07-logging-detection-evidence.md) |
| A.8.16 Monitoring activities | Real-time detections + weekly review sign-off | Detection catalogue, `evidence/weekly/` | [07](07-logging-detection-evidence.md) |
| A.8.17 Clock synchronization | Cloud provider time sources; NTP/chrony on k0s nodes | Node configuration | [07](07-logging-detection-evidence.md) |
| A.8.19 Installation of software on operational systems | Only pipelines deploy; plugins/MCP only from the reviewed allowlist | Pipeline logs, managed settings | [03](03-change-workflow.md), [04](04-agent-guardrails.md) |
| A.8.25 Secure development life cycle | PR checks, SAST, secret scanning, threat modelling for agents (Rule of Two) | CI results | [03](03-change-workflow.md) |
| A.8.28 Secure coding | SAST, CrossGuard, conventions in skills | CI results | [03](03-change-workflow.md) |
| A.8.31 Separation of development, test and production environments | 2 environments: VPC + naming/tag deny + boundary + KMS | IAM/resource policies, Prowler DET-011 | [02](02-access-model.md) |
| A.8.32 Change management | PR + approver ≠ last pusher + environment approval; runbooks; reconciliation | GitHub PRs/deployments, monthly evidence pack | [03](03-change-workflow.md) |
| A.8.33 Test information | Synthetic/de-identified data only in nonprod; Macie; DET-005 | Macie reports, DET-005 alerts | [01](01-operating-model.md) |

## 2. HIPAA Security Rule

| Standard / specification | How the framework meets it | Evidence |
|---|---|---|
| 164.308(a)(1)(ii)(D) Information system activity review (Req.) | Weekly review report generated from audit logs, signed off via PR | `evidence/weekly/` |
| 164.308(a)(3)/(a)(4) Workforce security / Information access management | Role-based permission sets, JIT, leaver deprovisioning via SSO | Identity Center, TEAM |
| 164.308(a)(5)(ii)(B)/(C) Protection from malicious software / Log-in monitoring (Addr.) | GuardDuty; SSO sign-in logs; DET-008 | GuardDuty findings, CloudTrail |
| 164.308(a)(6) Security incident procedures (Req.) | Incident flow, Linear incidents, postmortems | [05](05-debug-and-incident.md) |
| 164.308(a)(8) Evaluation | Weekly Prowler HIPAA checks, monthly evidence pack | Prowler reports |
| 164.312(a)(1) Access control | Permission sets, deny-prod, resource and KMS policies | IAM in Git |
| 164.312(a)(2)(i) Unique user identification (Req.) | Per-person SSO; separate agent permission set; OTel `user.email` | CloudTrail, OTel |
| 164.312(a)(2)(ii) Emergency access procedure (Req.) | Break-glass with 2 approvers, quarterly test | Test records, DET-004 |
| 164.312(a)(2)(iii) Automatic logoff (Addr.) | Session duration 1h for prod permission sets; SSO session limits | Identity Center config |
| 164.312(a)(2)(iv) Encryption and decryption (Addr.) | SSE-KMS with per-environment keys; RDS encryption enforced by CrossGuard | KMS policies, CrossGuard |
| 164.312(b) Audit controls (Req. standard) | CloudTrail + PHI data events + audit logs with Object Lock + Athena | Audit bucket, queries |
| 164.312(c)(1) Integrity | Object Lock on logs; PR-only changes; signed commits optional | Bucket config |
| 164.312(d) Person or entity authentication | SSO + MFA for people; OIDC/WIF for workloads | IdP config, trust policies |
| 164.312(e)(1) Transmission security | TLS enforced by bucket policies (`aws:SecureTransport`), VPC endpoints | Resource policies |
| BAA (164.308(b), 164.314) | Agents don't read PHI until a BAA covers the channel ([ADR-006](10-decisions.md#adr-006-agents-do-not-read-phi-until-the-baa-is-in-place)); AWS/GCP BAAs for infrastructure | Contracts |

**Watch item:** HHS published a Security Rule NPRM in January 2025. As of this writing no final rule was found. If finalised, some *Addressable* specifications may become mandatory (e.g. encryption, MFA). The framework already implements most of them.

## 3. OWASP for agentic systems

| Risk | Mitigation |
|---|---|
| LLM01 Prompt Injection / ASI01 Agent Goal Hijack | Rule of Two; read-only debug; no CI agents on untrusted triggers with credentials; IAM as the real boundary |
| LLM03 Supply Chain / ASI04 Agentic Supply Chain Vulnerabilities | MCP/plugin allowlist with review; pinned versions; internal marketplace only |
| LLM06 Excessive Agency / ASI02 Tool Misuse | No prod write for agents; guardrail hook; permission deny rules; sandbox |
| ASI03 Identity & Privilege Abuse | Separate agent permission set; no IAM writes; nonprod permission boundary |
| ASI09 Human-Agent Trust Exploitation | Approver ≠ author; agent disclosure in PRs; small PRs; runbooks triggered by humans |
| LLM02 Sensitive Information Disclosure | No PHI/secret values in agent context; OTel prompts redacted |
