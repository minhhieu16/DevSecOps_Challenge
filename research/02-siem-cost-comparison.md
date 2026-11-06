# Monitoring Options for Papaya: Google SecOps vs AWS-native SIEM vs Self-managed (no SIEM)

> Version 1.1 · 2026-11-06 · Region priced: **ap-southeast-1 (Singapore)**, on-demand USD
> Companion to [01-bigtech-models-and-top3-solutions.md](01-bigtech-models-and-top3-solutions.md) §4.
> AWS prices come from the AWS Price List API and aws.amazon.com pricing pages (fetched 2026-11-06). Google SecOps has **no public list price**; see §3.

---

## 0. Decision (2026-11-06)

**No SIEM. Option C (self-managed) is adopted.** The goal is still ISO 27001 + HIPAA, with priority on parts the team sets up and maintains itself, to keep costs down for a small or mid-size business. Options A and B below are kept as a record of the alternatives considered and as an upgrade path (§7 triggers). The calculation for option C is in §8.

| USD/year (Singapore, estimated) | Small | Medium |
|---|---|---|
| A: Google SecOps + Security Hub posture | ~$5.4k | ~$18.7k |
| B: AWS-native SIEM (Security Hub + CloudTrail Lake…) | ~$5.0k | ~$16.8k |
| **C: Self-managed, minimum** | **~$0.3k** | **~$1.2k** |
| **C: Self-managed, recommended (+ GuardDuty, + Macie quarterly)** | **~$1.7k** | **~$6.2k** |

---

## 1. Correcting the framing: Security Hub is not a SIEM

**AWS Security Hub alone cannot replace Google SecOps.** Security Hub:
- gathers and normalizes **findings** (OCSF);
- assesses posture (CSPM);
- runs automation rules;
- pushes findings to EventBridge.

What it **cannot** do is run custom detection rules over raw CloudTrail. Its only CloudTrail analysis is the Threat Analytics add-on, which has no user-defined rules.

The like-for-like replacement for SecOps is therefore an **AWS-native SIEM stack**:

| Function | Google SecOps | AWS-native replacement |
|---|---|---|
| Collect and store logs (12 months) | SecOps (UDM), 12 months included | **CloudTrail Lake** (1-year extendable option; ingests non-AWS sources through integrations) |
| Custom detection rules | YARA-L 2.0 (single and multi-event) | **EventBridge rules** (real-time, single event) + **CloudTrail Lake scheduled SQL** (aggregation, correlation) + Lambda |
| Threat detection | Curated rules (Enterprise and up) | **GuardDuty** (in both options as the baseline) |
| Findings aggregation + single pane | SecOps cases | **Security Hub** |
| Posture (CSPM) | ❌ not included (needs SCC / Security Hub) | **Security Hub** (+ AWS Config) |
| SOAR / alert routing | SecOps SOAR (included in Standard) | EventBridge → **Amazon Q Developer in chat apps** (Slack) + Lambda → Linear |
| Dashboards | SecOps dashboards | CloudTrail Lake dashboards + CloudWatch dashboards |

---

## 2. Sizing assumptions (monthly)

No real Papaya data was available, so I modelled **2 scenarios**. These are **estimates**; measure the real volume in Phase 0 and plug it into the model.

| Source | Small (~50 engineers) | Medium (~150 engineers) | Basis |
|---|---|---|---|
| CloudTrail management events | 5M events ≈ 7.4 GB | 20M ≈ 29.4 GB | 1,470 B/event (AWS example on the [Security Lake pricing page](https://aws.amazon.com/security-lake/pricing/)); event count is an estimate |
| CloudTrail S3 data events (PHI buckets only) | 10M ≈ 14.7 GB | 50M ≈ 73.5 GB | Estimate; **only PHI buckets**, not all data events |
| GCP Cloud Audit Logs (Admin + Data Access, prod) | 5 GB | 20 GB | Estimate |
| GitHub audit log | 1 GB | 1 GB | Estimate (thousands of events/day) |
| k0s API audit (Metadata, filtered) | 15 GB | 45 GB | Blog: 1–5 GB/day for <50 nodes, ~50% filtered |
| Claude Code OTel (tool events, prompts redacted) | 1 GB | 3 GB | Estimate |
| GuardDuty / Macie / Security Hub findings | < 1 GB | < 1 GB | — |
| VPC Flow Logs | **Not sent to the SIEM** | — | GuardDuty analyzes them itself (billed in the baseline) |
| **Total SIEM ingest** | **≈ 44 GB/month (~530 GB/year)** | **≈ 172 GB/month (~2.1 TB/year)** | |

Resource counts for Security Hub (billed per resource):

| | EC2 | Lambda functions | ECR images | IAM roles |
|---|---|---|---|---|
| Small | 5 | 200 | 300 | 300 |
| Medium | 10 | 600 | 1,000 | 800 |

---

## 3. Unit prices used

### AWS (ap-southeast-1)

| Service | Dimension | Price |
|---|---|---|
| Security Hub (Essentials) | EC2 instance | $3.75/month per unit |
| | Lambda: 12 functions = 1 unit · ECR: 18 images = 1 unit · IAM: 125 roles = 1 unit | $3.75/unit/month |
| | Findings ingestion/aggregation | Included |
| AWS Config | Configuration item recorded | $0.003/CI |
| CloudTrail | Management events, first trail | Free |
| | Data events | $0.10 per 100k |
| CloudTrail Lake (1-year extendable) | Ingestion, CloudTrail · other sources | $0.75/GB · $0.50/GB |
| | Retention beyond year 1 | $0.023/GB-month |
| | Query | $0.005/GB scanned |
| GuardDuty | CloudTrail management events | $4.60 per 1M |
| | S3 data events | $1.16 per 1M |
| | VPC flow / DNS | $1.15/GB (first 500 GB) |
| CloudWatch Logs | Ingestion Standard / IA | $0.70 / $0.35 per GB |
| EventBridge | AWS service events on the default bus | Free ⚠️ (long-standing policy; no SKU appeared in the Price List API) |
| OpenSearch Serverless (alternative) | OCU-hour | $0.283 (min ~2 OCU for a classic collection ≈ $413/month) |

### Google SecOps

| Source type | Figure | Notes |
|---|---|---|
| Official (Google docs) | **Billed on ingestion volume**: an annual subscription plus metering against credits. 12-month retention included. No public list price, minimum commitment not published | [Billing doc](https://docs.cloud.google.com/chronicle/docs/onboard/understand-billing) · [Packages](https://docs.cloud.google.com/chronicle/docs/secops/secops-packages) |
| UK G-Cloud 15 price sheet (Jan 2026) | **$1.95/GB per annum (Standard)**, $2.40 (Enterprise), $4.60 (Enterprise Plus) | ⚠️ The unit is unclear ("GB per annum"), and it may not apply outside the UK public sector. [PDF](https://assets.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-15/documents/720213/629316058669815-pricing-document-2026-01-29-2248.pdf) |
| Vendr (buyer data) | Average ≈ $314k/year, max ≈ $880k | Very small sample (>3 deals), skewed toward enterprise, so not representative of Papaya |
| Bindplane (collector) | **Google Edition is free** for SecOps customers; you only pay for collector compute | [Bindplane docs](https://docs.bindplane.com/plans-and-pricing/google-edition) |

The model uses the **G-Cloud price × GB ingested per year** as the **list-price floor**. A real quote may carry a **minimum annual commitment** (not published), so you must get a quote.

---

## 4. Cost model (USD/month, Singapore)

### 4.1 Common baseline (same in both options)

| Item | Small | Medium | Calculation |
|---|---|---|---|
| CloudTrail S3 data events (PHI buckets) | 10 | 50 | 10M / 50M × $0.10/100k |
| GuardDuty: CloudTrail management events | 23 | 92 | 5M / 20M × $4.60/1M |
| GuardDuty: S3 data events | 12 | 58 | 10M / 50M × $1.16/1M |
| GuardDuty: VPC flow/DNS (assumed 50 / 200 GB) | 58 | 230 | × $1.15/GB |
| Macie (nonprod buckets, PII detection) | 15 | 40 | Estimate |
| 6-year archive (S3 Glacier Deep Archive) | 10 | 10 | Estimate, negligible |
| **Subtotal** | **127** | **480** | |

### 4.2 Option B: AWS-native

| Item | Small | Medium | Calculation |
|---|---|---|---|
| **Posture:** Security Hub Essentials | 153 | 457 | Small: 5 EC2 (18.75) + 200 Lambda/12 × 3.75 (62.5) + 300 ECR/18 × 3.75 (62.5) + 300 IAM/125 × 3.75 (9) |
| **Posture:** AWS Config recording ⚠️ | 60 | 240 | 20k / 80k CI × $0.003 (needed for posture controls; see the note on Lambda churn below) |
| **SIEM:** CloudTrail Lake ingestion | 28 | 112 | CloudTrail 22 / 103 GB × $0.75 + non-AWS 22 / 69 GB × $0.50 |
| **SIEM:** CloudTrail Lake queries (scheduled every 15 min + ad hoc) | 15 | 60 | ~3 / 12 TB scanned × $0.005/GB (estimate) |
| **SIEM:** EventBridge + Lambda glue (Slack, Linear, custom findings) | 5 | 10 | Estimate |
| **SIEM:** Collector for non-AWS sources (OTel collector on Fargate) | 15 | 30 | Estimate |
| **SIEM:** CloudWatch dashboards + alarms | 10 | 15 | Estimate |
| **Subtotal, SIEM layer** | **73** | **227** | |
| **Subtotal, posture layer** | **213** | **697** | |

### 4.3 Option A: Google SecOps Standard

| Item | Small | Medium | Calculation |
|---|---|---|---|
| **SIEM:** SecOps license (list-price floor) ⚠️ | 86 | 335 | 530 / 2,064 GB/year × $1.95 ÷ 12 |
| **SIEM:** Bindplane collector compute | 15 | 30 | Estimate (Bindplane license is free) |
| **SIEM:** Egress AWS → GCP (AWS-origin logs ~38 / 151 GB) | 5 | 18 | × ~$0.12/GB ⚠️ (check the Singapore DTO price) |
| **SIEM:** S3/SQS feed | 1 | 1 | — |
| **Subtotal, SIEM layer** | **107** | **384** | |
| Posture (SecOps doesn't include it) | +213 (if adding Security Hub + Config) | +697 | Same as option B |

### 4.4 Summary

| Monthly total (USD) | Small | Medium | Annual (Small / Medium) |
|---|---|---|---|
| **A: SecOps, without posture** | 127 + 107 = **234** | 480 + 384 = **864** | $2.8k / $10.4k |
| **A: SecOps + Security Hub posture (like-for-like)** | **447** | **1,561** | **$5.4k / $18.7k** |
| **B: AWS-native (SIEM + posture)** | 127 + 73 + 213 = **413** | 480 + 227 + 697 = **1,404** | **$5.0k / $16.8k** |
| SIEM layer only: A vs B | 107 vs 73 | 384 vs 227 | $1.3k vs $0.9k / $4.6k vs $2.7k |

**Break-even:** SecOps beats the AWS-native SIEM layer only if the **annual SecOps license is ≤ ~$0.6k (Small) or ~$2.1k (Medium)**. That is the B SIEM layer minus SecOps' non-license costs. The G-Cloud list floor is already above that, at $1.0k / $4.0k. **Any minimum annual commitment widens the gap further.**

---

## 5. Reading the numbers (principal view)

1. **Tool cost is small at Papaya's volume either way.** The like-for-like difference is only ~10% ($5.0k vs $5.4k/year in the Small scenario). The real cost variables are:
   - **SecOps' minimum annual commitment**, which is unknown. Vendr data shows enterprise deals in the hundreds of thousands of dollars per year.
   - **Engineering time.**
2. **Most of the AWS-native cost is posture management (Security Hub + Config), not the SIEM.** That is a capability SecOps doesn't have. A fair comparison has to include it, or decide to drop posture management.
3. **Engineering effort (TCO)** is the AWS-native weak spot:

| | Google SecOps | AWS-native |
|---|---|---|
| Initial build | ~2 engineer-weeks (feeds, custom k0s/OTel parsers, porting 12 rules to YARA-L, SOAR) | ~3–4 engineer-weeks (EventBridge rules, scheduled SQL, Lambda glue, custom finding import, dashboards) |
| Maintenance | ~1–2 h/week (tuning rules) | ~2–4 h/week (rules + glue code + schema changes) |
| Multi-event / cross-source correlation | Native (YARA-L multi-event, entity graph) | Hand-written in SQL; weak in real time |
| Multi-cloud (GCP, GitHub, k0s) | Native GCP ingestion and GitHub parser | Custom integrations into CloudTrail Lake |

4. **Cost-reduction tips for option B:**
   - Turn on an ECR lifecycle policy, because Security Hub bills per image.
   - Consider periodic recording in Config for high-churn resource types ⚠️.
   - Send only PHI buckets as data events.
   - Never send VPC flow logs to the SIEM.

---

## 6. Capability comparison

| Criterion | A: Google SecOps (Standard) | B: AWS-native |
|---|---|---|
| A real SIEM (correlation, entity graph) | ✅ | ◐ (DIY: EventBridge + SQL) |
| Custom rule language | YARA-L 2.0 (1K single-event / 75 multi-event rules) | EventBridge patterns + SQL |
| Real-time detection | ✅ | ✅ for single events (EventBridge); aggregation lags 15 min |
| Posture (CSPM) | ❌ | ✅ Security Hub |
| Threat detection | Curated rules only in Enterprise; Standard is BYO | ✅ GuardDuty (both use it as the baseline) |
| SOAR | ✅ Base SOAR included | ◐ EventBridge + Lambda + Q Developer chat |
| UEBA | ❌ Standard (Enterprise and up) | ❌ |
| Retention | 12 months included; more costs extra | CloudTrail Lake 1 year; extension $0.023/GB-month; S3 archive |
| Multi-cloud | ✅ Strong | ◐ |
| Contract | Annual subscription, quote-based | Pay-as-you-go, no commitment |
| Vendors and bills | Adds a new vendor (Google Security) | One vendor (AWS-primary) |
| HIPAA BAA | ✅ Covered by the Google Cloud BAA | ✅ Through the AWS BAA (Security Hub, GuardDuty and CloudTrail are on the HIPAA-eligible list ⚠️) |
| Region | asia-southeast1 ⚠️ | ap-southeast-1 ✅ |
| Migration later | — | Detection specs written in a neutral format (Sigma ⚠️) in `agent-platform` make it cheap to move to SecOps later |

---

## 7. Recommendation (between A and B; superseded by §0)

**Pick option B (AWS-native) for the current phase**, because:
- **No commitment and pay-as-you-go**, which suits a small team and the user's preference for simplicity.
- **One vendor and one bill.** It matches the single-account AWS-primary architecture and adds no cross-cloud egress.
- **It adds posture management (Security Hub)**, which SecOps doesn't have.
- **Detection logic stays portable.** The 12 rules live as specs in the governance repo, implemented on EventBridge/SQL, so they can be ported to YARA-L later.

**Triggers to move to Google SecOps (re-evaluate every 6 months):**
- SIEM ingest exceeds ~10 GB/day, or there are more than ~25 rules needing multi-event correlation.
- A dedicated SOC/security team forms and needs real SOAR and UEBA (Enterprise).
- The time to maintain DIY glue exceeds ~4 h/week.
- A Google quote comes in with **no minimum commitment, or ≤ 1.5× the TCO of option B** (including engineering time).
- An ISO auditor or partner requires a "real SIEM".

**Pending data to finalize the numbers:**
- Measure the real CloudTrail volume (event count per month) and S3 data events on PHI buckets.
- Get a Google SecOps quote, and clarify what "per GB per annum" means and what the minimum commitment is.
- Count the real resources (Lambda, ECR images, IAM roles) to price Security Hub.
- Confirm that EventBridge doesn't charge for AWS service events, and check the Singapore DTO price.

---

## 8. Option C: self-managed, no SIEM (adopted)

**Principle:** ISO 27001/HIPAA require Papaya to record, protect, review, respond, and keep evidence. They don't require a SIEM. Architecture: §4 of the main report.

**Components:**
- CloudTrail (management events free) + data events on PHI buckets → S3 Object Lock.
- Athena with partition projection.
- EventBridge rules (critical, real-time).
- EventBridge Scheduler → Lambda → Athena (hourly/daily).
- **Prowler** (open source) weekly in GitHub Actions, replacing Security Hub/Config.
- Fluent Bit / OTel collector in the existing k0s cluster (k0s audit, Claude Code OTel) → S3.
- GCP sink → GCS Bucket Lock.
- A weekly report + evidence pack generated automatically.

| Item (USD/month, Singapore) | Small | Medium | Basis |
|---|---|---|---|
| CloudTrail management events (first trail) | 0 | 0 | Free |
| CloudTrail S3 data events (PHI buckets) | 10 | 50 | 10M / 50M × $0.10/100k |
| S3 log storage (gzip, Standard → IA → Glacier Deep Archive, 6 years) | 3 | 10 | Estimate; CloudTrail compresses well |
| Athena (hourly rules scanning one partition + weekly report + investigations) | 5 | 20 | ~1 / 4 TB scanned × $5/TB (estimate) |
| EventBridge (AWS events) + Lambda + EventBridge Scheduler | 2 | 5 | AWS management events on the default bus are free ([verified](https://aws.amazon.com/eventbridge/pricing/)); Lambda mostly free tier |
| Collectors (Fluent Bit / OTel) | 0 | 0 | Run on existing k0s capacity |
| Prowler on GitHub Actions | 0 | 0 | Within included Actions minutes (weekly run) |
| GCP sink → GCS + storage | 1 | 5 | Routing a sink is free; only GCS storage is billed (secondary source ◐) |
| SNS + Q Developer in chat apps (Slack) | 0 | 0 | Negligible |
| Contingency (KMS requests, S3 requests, data transfer) | 4 | 10 | Estimate |
| **Subtotal, minimum** | **~25** | **~100** | **~$0.3k / $1.2k per year** |
| + GuardDuty (CloudTrail + S3 data events + VPC flow/DNS) | 92 | 380 | Same as the baseline in §4.1 |
| + Macie run manually once a quarter on nonprod (~50 / 100 GB) | 23 | 40 | 50–100 GB × $1.35/GB ÷ 3 |
| **Subtotal, recommended** | **~140** | **~520** | **~$1.7k / $6.2k per year** |

**Effort:** ~2–3 engineer-weeks to build, then ~2–3 h/week to maintain, plus 30–45 minutes of weekly review.

**Trade-offs versus a SIEM:**
- No real-time correlation; aggregation rules lag by up to 1 hour.
- Investigation happens in Athena SQL.
- The weekly review must be done and signed off. Missing one is an audit finding.

**Why GuardDuty is still recommended:** it is the only managed component worth paying for. Building threat intelligence (malicious IPs, crypto-mining, credential exfiltration) in-house isn't realistic for a small team. If the budget is very tight, start with the minimum and turn on GuardDuty once prod handles real PHI.
