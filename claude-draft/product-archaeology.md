# Product Archaeology: Auth Review Assistant
**Author:** Rohan [Last Name]  
**Date:** April 2026  
**Prepared for:** Machinify Senior PM Take-Home — Panel Review

---

## 1. What Is This Product, Who Uses It, and What's the Architecture?

The Auth Review Assistant is an AI-powered clinical workflow tool that helps insurance payers process prior authorization (prior auth) requests faster. Prior auths are insurance approvals required before doctors can perform procedures — they're high-volume, time-sensitive, and heavily manual. This system's goal is to reduce that manual load using AI.

**Users**

There are two user groups visible from the artifacts:

- **Clinical Reviewers** (5 total, 3 currently active per Grafana Panel 6): The primary users. They process incoming prior auth requests — reading clinical documents, cross-referencing procedure codes against coverage criteria, and submitting approve/deny decisions with rationale. Issues #7, #14, #22 all come from named reviewers (Maria Torres, James Park, Aisha Williams), revealing a small but vocal user base experiencing compounding UX friction.

- **Clinical Ops Leadership** (VP Clinical Ops visible in Slack Thread #5): A secondary stakeholder focused on aggregate throughput and turnaround time. The VP escalated directly on March 28 about the missing auto-approve feature and received zero response — a critical stakeholder relationship gap that opened the moment the PM departed.

**Architecture**

The system is a five-component platform: a Rust/Axum API server serving the reviewer frontend, a Kafka-based CDC ingestor that pulls change events from the legacy SQL Server claims database, a backfill worker for async document processing, a Python pipeline handling OCR and LLM extraction, and a PostgreSQL database. Per `README.md`, the system also shows an "ML Scoring Service" in the architecture diagram. That service does not exist (see Section 2).

The choice of Rust was deliberate — documented in `docs/adr/001-rust-over-go.md` for performance predictability and compile-time PHI safety via SQLx. The agreed 6-month architecture review (due February 2026) has not been conducted as of April 2026.

---

## 2. What Does the Repo Tell You That the README Doesn't?

**Finding 1: The ML Scoring Service is fictional**

The `README.md` architecture diagram prominently shows `MLS [ML Scoring Service] → confidence scores → API` as if it's live and feeding the system. It isn't. `Migration 007` added a `ml_confidence_score` column to the `review_decisions` table — but per Issue #15, "no code reads or writes this column." The column exists. The service does not. The PRD corroborates this: ML Confidence Scoring is listed as Phase 2 / NOT STARTED. The README overstates the system's maturity in a way that could mislead any new stakeholder, engineer, or PM who read it before reading the issues.

**Finding 2: The Python pipeline has had zero CI coverage for 4 months**

`.github/workflows/pipeline-test.yaml` was disabled in December 2025 — renamed to `.disabled` as a "temporary" fix when the OCR mock was flaking (Slack Thread #2, Jordan Rivera: "the mock needs to be rewritten... I can look at it but I'm pretty swamped"). That was 4 months ago. Every change to the Python pipeline since December has shipped without any automated test coverage. This explains why Issue #16 (config conflict between `config.py` and `config.yaml`) could silently cause a production incident where the team thought they were running Claude-3.5-Sonnet but were actually hitting Claude-3-Haiku — a meaningful quality and cost difference.

**Finding 3: PR #47 has been approved and mergeable (with minor conflict resolution) for 45 days**

PR #47 adds Redis-based OCR result caching — approved by Sarah Kim on March 2, estimated to reduce OCR service load by ~30%. It has a single merge conflict in `pipeline/src/ocr_processor.py` introduced by a direct hotfix on main. Sarah offered to resolve it twice (March 2, March 18). No response from Alex. This is not a technical block — it's an attention/bandwidth block. Merging this PR is zero new development work and would immediately improve the extraction success rate.

**Finding 4: PHI is present in debug logs**

`crates/core/src/data/queries.rs:38` logs `patient_first_name` and `patient_last_name` at debug level. PR #54 (opened April 7) identifies and fixes this. It's currently unreviewed. This is benign at the current `info` log level — but the API pod crashes every 48 hours due to a memory leak (Issue #10), and the natural troubleshooting response is to set `RUST_LOG=debug`. If that happens in production before PR #54 is merged, patient names go into logs. HIPAA exposure.

**Finding 5: The API has a connection pool ceiling that can't support peak load**

`DATABASE_MAX_CONNECTIONS=10` in `.env.example`. Issue #2 documents 504 errors at 50 concurrent requests — a condition that occurs every Monday morning when all reviewers start their queues simultaneously. A pool of 10 connections can't serve 50 concurrent users. Issue #12 also flags that the Kubernetes resource limits (64Mi request, 128Mi limit) are inadequate for a Rust binary with a database connection pool, and no HorizontalPodAutoscaler exists.

---

## 3. What's Working and What's Broken?

**Working**

- **OCR + LLM extraction pipeline is live**: 62% success rate as of April 2026 (Grafana Panel 3), up from 0% in January. The pipeline is functional — it just needs hardening.
- **Reviewer decision recording works**: The core workflow (open case → read documents → submit decision) is operational. Reviewers are actively using it (5 users, 3 currently active).
- **CDC ingestor is functionally stable**: Duplicate events are handled gracefully via idempotent upserts (Issue #4). Lag spikes occur but resolve. Kafka infrastructure is healthy.
- **Backfill worker and migrations**: All Phase 1 PRD items are marked shipped and confirmed live in production. Database schema through Migration 008 is deployed.

**Broken or Dangerously Degraded**

| Problem | Evidence | Severity |
|---|---|---|
| Turnaround time worsening | Grafana Panel 2: 48hrs → 55hrs. Target: 28hrs | Critical |
| Extraction rate plateaued | 62% for 6 weeks. 38% fully manual. (Panel 3, KR2) | High |
| No retry on LLM failures | Issue #11: transient API errors = permanent failure | High |
| PHI in debug logs | PR #54 unreviewed. `queries.rs:38` | High |
| No urgency sort in queue | Issues #5, #26, Slack Thread #3: surgical pre-auths buried behind routine lab work | High |
| Approved PR unmerged 45 days | PR #47: merge conflict nobody resolved | Medium |
| CI disabled since December | Slack Thread #2: `.pipeline-test.yaml.disabled` | Medium |
| Memory leak / OOM crashes | Issue #10: pod crashes every ~48hrs | Medium |
| Analytics endpoints are stubs | Issue #19: `/api/v1/analytics/*` routes exist in `api.rs` but return nothing usable | Medium |
| Config split across 3 files | Issue #16: model name discrepancy caused prod incident | Medium |
| Runbook outdated | Issue #27: still references `kubectl apply`, team uses Helm | Low |

---

## 4. What Is the Single Most Important Problem to Solve Right Now?

**The extraction pipeline is the bottleneck on every business goal.**

The PRD's 40% turnaround reduction was predicated on 80% AI extraction success (KR2). At 62%, that assumption fails. The math is straightforward: with ~340 requests/day, 38% manual processing means ~130 cases/day that require full reviewer attention. With only 3 of 5 reviewers active, each reviewer handles ~113 cases/day under the current load — unsustainable.

But here's the specific reason this is the *most* important problem, not just any problem: **the extraction ceiling is currently 62% not because of hard engineering work but because three known, solvable issues are unaddressed.** PR #47 is already approved. Issue #11 (LLM retry) is estimated at ~1 day of work. Issue #6 (rotated PDFs) has a known library solution (`pdfplumber`). Fixing all three would likely move extraction from 62% to ~82-85% — within striking distance of the 80% target.

That 80% threshold is the unlock for auto-approve. Auto-approve is the unlock for the VP Clinical Ops relationship. The VP escalated March 28 with zero response — that silence is a business risk, not just an ops inconvenience.

---

## 5. What Information Is Missing That I'd Need to Validate This Diagnosis?

- **Why did 2 of 5 reviewers go inactive?** Grafana Panel 6 shows the drop from 5 to 3 active reviewers starting in mid-February. Is this burnout from tool friction? A staffing change? Sick leave? If it's attrition, the capacity math changes fundamentally.
- **What is the actual OCR failure mode breakdown beyond the 62/38 split?** The Grafana dashboard shows failure categories (rotation: 20%, timeout: 8%, LLM error: 6%, parse fail: 4%) — but these are last-30-day aggregates. Is rotation really the top issue across the full 90 days, or did it spike recently?
- **What procedure codes make up the backlog?** If 30%+ of the current backlog matches the CPT codes in Draft PR #53 (80053, 80061, 85025, 71046, 93000), the auto-approve ROI is immediate. If it's 5%, the urgency changes.
- **Has legal reviewed the auto-approve regulatory requirements?** The PRD notes "regulatory compliance: auto-approve feature needs legal review for state-specific requirements." No evidence this happened before Dana departed.
- **What does the reviewer UX look like?** Issues #7, #22, and #14 all describe significant friction — 30-second document load times, scroll state resetting, no side-by-side history view. I'd want to do a 30-minute session observation with one reviewer to calibrate how much these issues are contributing to the 3/5 active reviewer problem.
