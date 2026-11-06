# Evidence

Audit evidence produced by the framework. Raw evidence (Prowler outputs, monthly packs) lives in `s3://papaya-audit-logs/evidence/` under Object Lock. This folder holds the **human-reviewed summaries**, so the sign-off itself is versioned and attributable in Git.

| Folder | Produced by | Signed off by | Satisfies |
|---|---|---|---|
| `weekly/<YYYY>-W<ww>.md` | `weekly-review.yml` opens a PR every Monday | Security reviewer approves the PR (after investigating anomalies) | HIPAA 164.308(a)(1)(ii)(D) Information system activity review · ISO A.8.16 |
| `monthly/<YYYY>-<MM>.md` | Monthly job (change approvals, out-of-pipeline changes, break-glass, Prowler, access list) | Platform + Security | ISO A.8.32, A.8.2, A.5.18 · HIPAA 164.308(a)(8) |
| `postmortems/<date>-<incident>.md` | Incident owner | On-call lead + Security | ISO A.5.27 · HIPAA 164.308(a)(6) |
| `access-reviews/<YYYY>-Q<n>.md` | Quarterly export (Identity Center, TEAM eligibility, GitHub environments) | Security | ISO A.5.18 |
| `breakglass-tests/<YYYY>-Q<n>.md` | Quarterly exercise | Platform + Security | HIPAA 164.312(a)(2)(ii) |

**Rule:** a weekly report PR that isn't approved within 5 working days is escalated. A missed week is recorded as a nonconformity.

See [`weekly/EXAMPLE-2026-W45.md`](weekly/EXAMPLE-2026-W45.md) for the expected shape. It is fictional data for illustration.
