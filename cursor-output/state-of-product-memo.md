## Cursor's Assessment vs. Claude's Version
- Agreed with (independently confirmed):
  - **Reality in numbers is deteriorating**: median turnaround 48 hrs → 55 hrs while volume rises and active reviewers fall (`artifacts/grafana-dashboard.md:12-19`, `artifacts/grafana-dashboard.md:23-37`, `artifacts/grafana-dashboard.md:92-103`; OKR KR1 in `artifacts/okr-snapshot.md:10-24`).
  - **Pipeline plateau is a hard ceiling**: extraction success is flat at 62% for 6 weeks and failure breakdown is known (`artifacts/grafana-dashboard.md:41-58`; OKR KR2 in `artifacts/okr-snapshot.md:10-24`).
  - **CI gap is real**: pipeline workflow has been disabled since 2025-12-15 (`repo/.github/workflows/pipeline-test.yaml.disabled:1-3`; Slack Thread #2 in `artifacts/slack-threads.md:28-42`).
  - **Compliance risk**: patient names appear in a debug log line in core query code; PR #54 calls it out (`repo/crates/core/src/data/queries.rs:42`; `repo/PULL-REQUESTS.md:102-125`).
- Disagreed with or modified:
  - **"Pool size 10 causes timeouts" is not directly supported by code**. `DATABASE_MAX_CONNECTIONS` is parsed but unused; any claim about enforced pool size must be treated as INFERENCE until proven (`repo/crates/core/src/data/mod.rs:5-13`; `.env.example` value at `repo/.env.example:1-4`; Issue #2 at `repo/ISSUES.md:35-50`).
  - **Auto-approve is not "ready to ship once criteria exist" in this repo snapshot**: PR #53 is referenced, but the endpoint and migration 009 aren't present here (PR description in `repo/PULL-REQUESTS.md:67-99` vs routes in `repo/crates/api/src/api.rs:7-31` and migrations list under `repo/migrations/`).
- Added:
  - **Release/deploy drift is detectable from CI**: release workflow deploys with `infra/helm/values-dev.yaml`, but that file is absent in this repo snapshot (`repo/.github/workflows/release.yaml:28-33`).

---

## State of the Product Memo

**To:** Alex Chen, Platform Engineering Lead
**From:** Rohan Tejaswi, Senior PM (Week 1)
**Date:** April 2026
**Re:** Current health, top risks, and the next bet

Alex — I've been through the codebase, issues, PRs, Grafana metrics, and Slack history this week. Here's my honest read. I'm not softening anything.

### Current Health: The Numbers

| Metric | Jan 1 | Apr 5 | Target | Direction |
|--------|-------|-------|--------|-----------|
| Median turnaround | 48 hrs | 55 hrs | 28 hrs | ↑ Worsening |
| AI extraction rate | 0% (not live) | 62% | 80% | → Flat 6 wks |
| Daily request volume | ~200/day | ~340/day | — | ↑ +70% |
| Active reviewers | 5 | 3 | — | ↓ Dropping |

Volume growth overwhelmed the February extraction gains within 2 weeks. At 340/day with 3 reviewers and 62% extraction, each reviewer handles ~43 fully manual cases daily. That's unsustainable, and it's getting worse.

### Risk 1: PHI Compliance — One Incident Response Step Away

`queries.rs:42` logs decrypted patient names at debug level:

```
log::debug!("Fetched auth request for patient: {} {}",
    request.patient_first_name, request.patient_last_name);
```

At `RUST_LOG=info` this isn't leaking. But the API pod OOM-crashes every ~48 hours (Issue #10), and the natural debugging step is `RUST_LOG=debug`. If that happens before PR #54 merges, patient names go into plaintext logs — that's a HIPAA incident report. PR #54 is a 15-minute code review. It should be done today.

### Risk 2: API Stability & Configuration Drift

The API pod hits its 128Mi limit every 24–48 hours, OOM kills, and restarts (Grafana P4: P95 spikes to 6–8s on restart; Issue #10; Slack Thread #1). Compounding: `DATABASE_MAX_CONNECTIONS=10` is parsed at `mod.rs:5-13` but never applied to the pool — peak-load behavior is unpredictable. Stopgap: bump limits to 256Mi/512Mi in `values.yaml`. HPA (Issue #12) is the right longer-term fix.

### Risk 3: VP Escalation — 18 Days, Zero Response

Slack Thread #5, March 28: VP Clinical Ops asked about auto-approve. No response. PR #53 raises four product questions — I'm the product owner now and I'll answer them:

- **CPT list:** PR #53's list (80053, 80061, 85025, 71046, 93000) is directionally correct, pending clinical ops validation.
- **Threshold:** Exact CPT match + `urgency_level = "routine"` + extraction completeness check. No ML score needed — the ML Scoring Service doesn't exist.
- **Audit trail:** Yes, via migration 009's `auto_approve_log` table.
- **Human override:** Yes, a `requires_manual_review` flag for edge cases.

### What's Being Ignored

- **FIFO queue:** `queries.rs:69-72`, ~2 hours of work, immediate reviewer impact (Slack Thread #3, Issues #5, #26).
- **Analytics crash:** `analytics.rs:20-29` is a `todo!()` — if the VP hits `/turnaround-times`, the API pod panics.
- **Pipeline CI:** Dark since December. Issue #16 (wrong LLM model running undetected) happened because nothing caught the config mismatch.

### Recommended Next Bet: 30-Day Throughput Unlock

- **Week 1 — Safety:** Merge PR #54 (PHI fix), bump K8s limits to 256Mi/512Mi, re-enable pipeline CI
- **Week 2 — Capacity:** Ship urgency sort (Issue #26), resolve PR #47 conflict, clinical ops CPT validation session
- **Week 3 — Pipeline:** LLM retry logic (Issue #11), merge PR #53 (auto-approve) once criteria confirmed
- **Week 4 — Measurement:** Rotated PDF preprocessing (Issue #6), materialized views for analytics (Issue #19)

Target: 82% extraction by end of April, auto-approve live, real path to 28-hour turnaround by Q2. The math only works if we start removing the ceiling now.

What do you need from me to make this happen?

— Rohan
