# State of the Product Memo
**To:** Alex Chen, Platform Engineering Lead  
**From:** Rohan [Last Name], Senior PM (Week 1)  
**Date:** April 2026  
**Re:** Current system health, top risks, and recommended next bet

---

Alex — I've spent the week going through the codebase, issues, PRs, Grafana metrics, and Slack history. Here's my honest read. No softening.

---

## Current Health Assessment: System is Degrading, Not Improving

The headline number: median review turnaround is **55 hours as of April 5**. It was 48 hours on January 1. The Q1 target was 28 hours. We're trending in the wrong direction.

The brief improvement in early February (down to 46 hours) coincided with the LLM extraction pipeline going live. That tells me the architecture is right — AI extraction can move the needle. But volume growth (~3% weekly, from 200 to 340 requests/day) outpaced the efficiency gain within 2 weeks, and the pipeline hasn't improved since. Extraction has been flatlined at 62% for 6 weeks. With 3 of 5 reviewers currently active, each person is absorbing more volume with less AI help than the Q1 model assumed.

The system isn't broken. It's constrained — and the constraints are mostly product-side, not engineering-side.

---

## Risk 1: PHI Compliance Exposure — Needs Action This Week

PR #54 (Jordan's `fix/phi-debug-logging`) is sitting unreviewed. It removes a `log::debug!` call at `crates/core/src/data/queries.rs:38` that writes `patient_first_name` and `patient_last_name` to the log stream.

We run at `info` level in production — so it's not currently leaking. But the API pod OOM-crashes every ~48 hours (Issue #10), and the natural engineering response when debugging an OOM crash is `RUST_LOG=debug`. If that happens in production before PR #54 merges, we have PHI in plaintext logs. That's a HIPAA incident report, not just a bug.

This is a 15-minute code review. It should be done today. I'll flag it to Jordan that you're reviewing it.

---

## Risk 2: The Pipeline Ceiling Is Blocking Every Q1 KR

KR2 (80% extraction) and KR1 (28-hour turnaround) are both blocked by the same root cause: the Python pipeline is running at 62% with no path to improvement because three known fixes are sitting idle.

**PR #47 (OCR caching)** — approved March 2, sitting for 45 days because of a single merge conflict in `ocr_processor.py`. Sarah offered to resolve it twice. Merging this gets us ~30% reduction in OCR service load and reduces duplicate-submission failures. This is zero new development. It's a 10-minute conflict resolution.

**Issue #11 (LLM retry logic)** — the Anthropic API extractor has no retry on 429 or 500 responses. A transient rate-limit error permanently fails the document. Exponential backoff with jitter is a day of work, and it fixes ~6% of current failures.

**Issue #6 (rotated PDFs)** — 20% of OCR failures come from scanned documents at wrong angles. `pdfplumber` can detect orientation. This is the biggest single improvement available and it's a known library integration.

Combined, these three fixes likely move extraction from 62% to ~82-85%. That's the unlock for auto-approve — which needs high-confidence extraction to be safe. And frankly, it's the unlock for the VP Clinical Ops relationship.

One more thing on the pipeline: the CI workflow has been disabled since December. `.github/workflows/pipeline-test.yaml.disabled` — four months of Python changes shipping with zero test coverage. Issue #16 (the `config.py` vs `config.yaml` model name discrepancy that caused a prod incident) was a direct consequence of no automated checks. We need to re-enable CI. I'll work with Sarah on a proper OCR mock.

---

## Risk 3: Auto-Approve Is a Stakeholder Clock, and Engineering Is Making Product Decisions

Draft PR #53 (`feature/auto-approve`) opened April 3 — one week after VP Clinical Ops escalated in `#leadership` with no response. You (Alex) opened the PR with a hardcoded list of five CPT codes and four unresolved product questions:

> Is this the right list? What's the confidence threshold? Do we need an audit trail? Should there be a human override?

These are product decisions, not engineering decisions. The previous PM left them unanswered and engineering did the reasonable thing: opened a draft and waited. I'm the product owner now, and I'm going to answer them.

Preliminary answers: The CPT code list (80053, 80061, 85025, 71046, 93000) looks directionally right based on the PRD's criteria, but I need clinical ops validation before we hardcode anything. Confidence threshold: I'd start at exact CPT code match + `urgency_level = "routine"` + extraction success (no OCR failures) rather than a probabilistic ML score — since the ML Scoring Service doesn't exist yet and we don't need it for this first cut. Audit trail: yes, required, the log table in migration 009 is the right approach. Human override: yes, flag for edge cases.

I'll get clinical ops into a room this week. Once we have the criteria, PR #53 can ship. Engineering is already done — I just need to give you a definition of done.

---

## What's Being Ignored

**The reviewer queue is FIFO and nobody's fixing it.** Issues #5, #26, and Slack Thread #3 (April 1: Maria, James, and Aisha all complaining about spending 10-15 minutes finding urgent cases every morning) tell the same story. The `urgency_level` field exists in the schema but isn't used in the sort order. This is a one-query change to `list_requests` in `crates/api/src/endpoints/v1/auth_requests.rs` — `ORDER BY urgency_level DESC, submitted_at ASC`. It's probably 2 hours of work and it materially improves the 3 active reviewers' daily experience. We should ship it.

**The analytics endpoints are registered but empty** (`api.rs` lines 30-32: `/api/v1/analytics/review-metrics`, `/api/v1/analytics/turnaround-times`, `/api/v1/analytics/reviewer-performance`). The VP wants turnaround time dashboards. Issue #19 explains they're blocked on the OLTP vs. analytics question. I'll make a call: start with PostgreSQL materialized views. It's not perfect but it unblocks the dashboard without standing up a data warehouse, and we can migrate to BigQuery later when volume justifies it.

---

## Recommended Next Bet: 30-Day Pipeline Hardening Sprint

**Week 1 (this week):**
- Review and merge PR #54 — PHI fix (today, 15 min)
- Resolve conflict on PR #47 — OCR caching (Sarah can own the conflict resolution)
- Re-enable pipeline CI — I'll spec the mock rewrite

**Week 2:**
- Ship urgency sort (Issue #26) — small but visible win for reviewers
- Implement LLM retry logic (Issue #11) — Sarah's ticket, ~1 day
- Clinical ops session to define auto-approve criteria

**Week 3:**
- Merge PR #53 once criteria are confirmed
- Begin rotated PDF pre-processing (Issue #6)

**Week 4:**
- Materialize views for analytics (Issue #19)
- Bump Kubernetes resource limits (Issue #12) — eliminate OOM cycle while we investigate the memory leak

If extraction reaches ~82% by end of April and auto-approve ships, we'll have a real path to the 28-hour target by end of Q2. Right now we don't.

What do you need from me to make this happen?

— Rohan
