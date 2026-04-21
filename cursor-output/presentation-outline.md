## Cursor's Assessment vs. Claude's Version
- Agreed with (independently confirmed):
  - The narrative must be anchored in production reality: volume ↑, turnaround ↑, extraction plateau, active reviewers ↓ (`artifacts/grafana-dashboard.md:12-37`, `artifacts/grafana-dashboard.md:41-58`, `artifacts/grafana-dashboard.md:92-103`).
  - Slides 3–4 should be “proved” by a live demo of a repeatable artifact-to-action synthesis (prototype CLI).
- Disagreed with or modified:
  - I did not assume auto-approve is implementable from existing code in this repo snapshot; PR #53 references files/migrations that are not present (`repo/PULL-REQUESTS.md:67-99` vs `repo/crates/api/src/api.rs:7-31` and `repo/migrations/*`).
- Added:
  - A concrete “repo reality gap” slide callout: analytics endpoints include a `todo!()` that will panic if hit (`repo/crates/api/src/endpoints/v1/analytics.rs:20-29`).

---

## Slide 1 — What this product is, and what the repo actually contains (Week 1)

**Headline:** “Auth Review Assistant is an AI-assisted prior auth workflow; the ‘foundation’ exists, but Phase 2 ‘intelligence’ is mostly implied, not shipped.”

**Callouts (evidence):**
- PRD: Phase 1 shipped; Phase 2 not started (`repo/docs/prd-ai-review-v2.md:23-40`)
- README depicts an ML Scoring Service, but only schema scaffolding exists (`repo/README.md:21-37`; `repo/migrations/007_add_ml_confidence.sql:1-9`; Issue #15 in `repo/ISSUES.md:229-241`)

**Talk track (speaker notes):**
- “I’m treating Grafana + artifacts as ground truth, and using code to validate what’s real vs implied.”

---

## Slide 2 — What the data shows (90 days): the trajectory is worsening

**Callouts (numbers):**
- Volume: ~200/day → ~340/day (`artifacts/grafana-dashboard.md:12-19`)
- Turnaround: 48 hrs → 55 hrs vs 28 hr target (`artifacts/grafana-dashboard.md:23-37`)
- Extraction: plateau at 62% for 6 weeks (failure buckets listed) (`artifacts/grafana-dashboard.md:45-58`)
- Active reviewers: 5 → 3 (`artifacts/grafana-dashboard.md:92-103`)

**Talk track:**
- “This is a math problem: rising demand, falling capacity, capped automation.”

---

## Slide 3 — System health + top risks (DEMO: CLI sections 1–2)

**Title:** “System health is constrained; top risks are asymmetric.”

**DEMO mapping:** Run `python cursor-output/prototype/system_state_cli.py` and show:
- **SYSTEM HEALTH** (Grafana + repo checks)
- **TOP RISKS** (3 risks, cited)

**Risk callouts (with citations):**
- PHI in debug logs (`repo/crates/core/src/data/queries.rs:42`; PR #54 in `repo/PULL-REQUESTS.md:102-125`)
- Analytics endpoint `todo!()` (“will panic”) (`repo/crates/api/src/endpoints/v1/analytics.rs:20-29`; Issue #19 in `repo/ISSUES.md:288-304`)
- OOM/restart-correlated latency spikes (`artifacts/grafana-dashboard.md:61-74`; Issue #10 in `repo/ISSUES.md:157-170`)

**Talk track:**
- “I’m not listing everything; I’m listing what changes the trajectory if delayed.”

---

## Slide 4 — Monday-morning action plan + what’s blocked on PM decisions (DEMO: CLI sections 3–4)

**Title:** “Executable plan, explicit ownership, and the decisions we need.”

**DEMO mapping:** In the same CLI run, show:
- **ACTION PLAN (prioritized)**
- **WHAT'S BLOCKED PENDING PM DECISION**

**Top actions (evidence anchors):**
- Merge PR #54 (PHI) (`repo/PULL-REQUESTS.md:102-125`)
- Unblock PR #47 (OCR caching) (`repo/PULL-REQUESTS.md:5-36`; OKR KR2 in `artifacts/okr-snapshot.md:10-24`)
- Re-enable pipeline CI (`repo/.github/workflows/pipeline-test.yaml.disabled:1-3`; Slack Thread #2 in `artifacts/slack-threads.md:28-42`)
- Ship urgency sort (FIFO today) (`repo/crates/core/src/data/queries.rs:69-72`; Issue #26 in `repo/ISSUES.md:395-406`; Slack Thread #3 in `artifacts/slack-threads.md:46-60`)

**Blocked decisions (examples):**
- Auto-approve criteria ownership + guardrails (`repo/ISSUES.md:367-378`; `repo/PULL-REQUESTS.md:67-94`; `artifacts/slack-threads.md:80-87`)
- Analytics approach (materialized views vs warehouse) (`repo/crates/api/src/endpoints/v1/analytics.rs:20-29`; `repo/ISSUES.md:288-304`)
- ML scoring scope vs remove dead column / soften README (`repo/migrations/007_add_ml_confidence.sql:1-9`; Issue #15 in `repo/ISSUES.md:229-241`)

**Talk track:**
- Use the framing: “This tool demonstrates what a PM does that an engineer can’t…”

---

## Slide 5 — What I need (decisions/inputs I can’t make alone)

**Decisions needed (explicit):**
- Clinical ops validation: initial auto-approve CPT list + human override + audit requirements (`repo/ISSUES.md:367-378`; `repo/PULL-REQUESTS.md:67-94`)
- Analytics architecture call (MV vs warehouse vs replica) + success metrics definition (`repo/ISSUES.md:288-304`)

**Inputs needed:**
- Why active reviewers dropped 5 → 3 (cause unknown; metric is real) (`artifacts/grafana-dashboard.md:92-103`)
- Confirmation of incident runbooks/deploy source of truth (runbook drift) (`repo/docs/operations/runbook.md:8-20`; Issue #27 in `repo/ISSUES.md:409-418`)

**Close:**
- “If we agree on these decisions this week, the engineering path to improving the trajectory becomes straightforward and measurable.”

