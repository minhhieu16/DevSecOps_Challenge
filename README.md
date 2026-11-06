# Papaya: DevSecOps with Coding Agents

This is the deliverable for DevSecOps Challenge 1: a framework and workflow for how Papaya uses coding agents (Claude Code) for DevSecOps. It targets ISO 27001 and HIPAA at a cost a small team can carry.

> **Start here → [FRAMEWORK.md](FRAMEWORK.md)** (high level, about a 10-minute read)

## In one line

> **Agents and humans freely *propose* and *observe*. Only a pipeline *changes* production, from Git, after a named person who is not the author approves it.**

The two positions from the challenge are both met:

- **Engineering's ask** (*"let Claude Code talk to AWS directly"*):
  - Agents get direct read-only access to prod for debugging, self-service, ticket required.
  - They have full freedom in nonprod.
  - Changes go through PRs, with a 15-minute fast lane for incidents.
  - Operations run as one-click runbooks.
- **Compliance's ask** (*"no prod change without a named approver"*):
  - Every prod change is approved in GitHub by someone other than its author.
  - Access is time-boxed and attributed to a person.
  - Real-time alerts fire on anything that bypasses this path.
  - A weekly review is signed off.

## Repository map

| Path | What it is |
|---|---|
| **[FRAMEWORK.md](FRAMEWORK.md)** | **The deliverable** at a high level: answer, operating model, workflows, guardrails, logging/evidence, compliance summary, decisions, roadmap |
| [appendix/docs/](appendix/docs/) | Detailed design, 10 documents: operating model, access model, change workflow, agent guardrails, debug/incident, secrets, logging/detection/evidence, compliance mapping, rollout, ADRs |
| [appendix/agent-platform/](appendix/agent-platform/) | Reference implementation of the governance repo: managed settings, guardrail hook with tests, skills, MCP review, IAM/KMS/S3 policies, CrossGuard, detections, Prowler and weekly-review workflows, evidence |
| [appendix/monorepo-examples/](appendix/monorepo-examples/) | Changes to the app monorepo: PR checks, deploy workflows, runbooks-as-code, CODEOWNERS, PR template, `CLAUDE.md` |
| [research/](research/) | Research: top 5 big-tech models, top 3 solutions with trade-offs, principal review, monitoring cost comparison |
| [sessions/](sessions/) | Raw, unedited Claude Code session transcripts (main session plus every sub-agent) |

## Assumptions

- There was no access to Papaya systems. Names, volumes and costs are placeholders or estimates (account `111122223333`, org `papaya`, region `ap-southeast-1`).
- Reference code is illustrative and not deployed. JSON, YAML and Python were syntax-checked.
- Facts were checked against primary sources where possible. The remaining open items are marked ⚠️ or **Verify:**.

## How this was built

Claude Code orchestrated the work. Sonnet and Haiku sub-agents ran research, fact-checking and reference-implementation drafts in parallel, and the author directed and reviewed each key decision. The full conversation is in [sessions/](sessions/).
