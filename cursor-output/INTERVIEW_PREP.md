## Cursor's Assessment vs. Claude's Version
- **Agreed with (independently confirmed)**: The core interview risk isn’t “missing a feature,” it’s missing the *reasoning chain* from evidence → diagnosis → bet → required decisions (Grafana/OKR/Slack triangulation: `artifacts/grafana-dashboard.md:12-104`, `artifacts/okr-snapshot.md:10-24`, `artifacts/slack-threads.md:80-87`).
- **Modified**: I anchor answers to what is *actually in this repo snapshot*. Example: PR #53 references auto-approve code/migration that are not present here (`repo/PULL-REQUESTS.md:67-99` vs `repo/crates/api/src/api.rs:7-31`, `repo/migrations/*`).
- **Added**: A concrete demo artifact (CLI) that is the evidence for slides 3–4, and a set of “hard engineer questions” with citations that show you read code (e.g., DB pool sizing knob parsed-but-unused in `repo/crates/core/src/data/mod.rs:5-13`).

---

## (a) 5 likely hard questions Phil Mora will ask (with evidence-grounded answers)

### 1) “Why did you build a CLI instead of fixing the pipeline or implementing urgency sort?”

**Answer (use this framing verbatim):**  
“This tool demonstrates what a PM does that an engineer can’t: it turns dispersed signals across Slack, Grafana, Issues, and PRs into a prioritized action list that the team can act on Monday morning. The PM’s job isn’t to have all the answers—it’s to make the right questions impossible to ignore.”

**Evidence to point at live:** run `python cursor-output/prototype/system_state_cli.py` and show the four sections. Then tie one action to one source:
- Extraction plateau and failure buckets are in Grafana (`artifacts/grafana-dashboard.md:41-58`).
- PR #47 is approved but unmerged due to conflict (`repo/PULL-REQUESTS.md:5-36`).
- Pipeline CI disabled since 2025-12-15 (`repo/.github/workflows/pipeline-test.yaml.disabled:1-3`; Slack Thread #2 in `artifacts/slack-threads.md:28-42`).

**If pressed (“but why not just ship urgency sort?”):**  
I’m not claiming urgency sort is unimportant; it’s explicitly in the action plan (Issue #26 + FIFO ordering in code) (`repo/ISSUES.md:395-406`; `repo/crates/core/src/data/queries.rs:69-72`). The CLI makes it *hard to ignore* and assigns ownership/effort so it can ship Monday.

---

### 2) “You keep saying ‘pool size 10’—where is that actually enforced in code?”

**Answer:**  
In this repo snapshot, it’s not enforced. `DATABASE_MAX_CONNECTIONS` is parsed, but the pool is created using `PgPool::connect` and the parsed value is never applied (`repo/crates/core/src/data/mod.rs:5-13`). So “pool size 10 causes timeouts” is an **INFERENCE** based on `.env.example` (`repo/.env.example:1-4`) and Issue #2’s symptoms (`repo/ISSUES.md:35-50`), not a provable fact from code.

**Good follow-up:**  
The fix isn’t just “increase connections,” it’s “make the tuning knob real” (use `PgPoolOptions::new().max_connections(...)`) and then tune alongside resource limits (Helm is currently 64Mi/128Mi for API) (`repo/infra/helm/values.yaml:11-18`).

---

### 3) “Your ‘analytics endpoints are stubs’ claim—can you show me that in code?”

**Answer:**  
Yes. `get_review_metrics` returns `"status": "not_implemented"` (`repo/crates/api/src/endpoints/v1/analytics.rs:7-18`) and `get_turnaround_times` is a `todo!()` with a note “Waiting on data warehouse access” (`repo/crates/api/src/endpoints/v1/analytics.rs:20-29`). The router registers these endpoints (`repo/crates/api/src/api.rs:26-29`). That means the API surface implies dashboards exist, but one endpoint will panic if hit.

**How to phrase the product implication:**  
This is an expectation mismatch: “endpoints exist” isn’t equivalent to “feature shipped.”

---

### 4) “What’s your proof that turnaround is getting worse for structural reasons, not noise?”

**Answer:**  
The 90-day snapshot shows a consistent trend:
- Median turnaround: 48 hrs (Jan) → 55 hrs (Apr 1–5) (`artifacts/grafana-dashboard.md:28-37`).
- Volume: ~200/day → ~340/day (`artifacts/grafana-dashboard.md:12-19`).
- Active reviewers: 5 → 3 (`artifacts/grafana-dashboard.md:92-103`).
- Extraction plateau: 62% flat for 6 weeks (`artifacts/grafana-dashboard.md:45-52`).

That combination is not random variance; it’s throughput math. OKRs corroborate the same reasoning and explicitly cite that volume growth + extraction underperformance is driving KR1 off-track (`artifacts/okr-snapshot.md:10-24`).

---

### 5) “Auto-approve—what’s actually blocking it? Engineering or product?”

**Answer:**  
Both, but in different ways:
- **Product decision vacuum is real**: VP escalation has no response (`artifacts/slack-threads.md:80-87`), and Issue #24 asks “who owns criteria?” (`repo/ISSUES.md:367-378`).
- **Engineering implementation is not verifiably present in this repo snapshot**: PR #53 describes an endpoint and migration 009, but those files do not exist here (`repo/PULL-REQUESTS.md:67-99` vs `repo/crates/api/src/api.rs:7-31` and `repo/migrations/*`). So “criteria alone unblocks shipping” would be overstated for this snapshot.

**What I’d do Monday:**  
Define criteria + guardrails with clinical ops, and in parallel verify/land the implementation surface (route + migration) so “criteria → ship” is actually true.

---

## (b) 2–3 things most likely to trip up a PM in this presentation (and how to handle them)

### Pitfall 1: Treating repo markdown as “truth” without code verification
**What goes wrong:** You repeat PR descriptions (e.g., auto-approve endpoint exists) that are not present in the repo snapshot.  
**How to handle:** Use language like: “PR #53 *proposes* X, but in this repo snapshot I can’t verify the endpoint/migration is present; I’m treating it as a plan, not shipped code.” (Cite: `repo/PULL-REQUESTS.md:67-99` vs `repo/crates/api/src/api.rs:7-31`.)

### Pitfall 2: Saying “pool size = 10” as a fact
**What goes wrong:** Phil will ask where it’s set; code contradicts it.  
**How to handle:** Preempt it: “The env var exists, but the code doesn’t apply it; so the right fix is to make the knob real and then tune.” (`repo/crates/core/src/data/mod.rs:5-13`; `repo/.env.example:1-4`.)

### Pitfall 3: Getting lost in “everything that’s wrong” instead of one bet
**What goes wrong:** You list 10 issues and make zero recommendations.  
**How to handle:** Keep repeating the bet: “Throughput unlock: raise extraction ceiling + remove daily reviewer friction + remove asymmetric compliance risk.” Then show the CLI action plan as the executable list.

---

## (c) 5-minute verbal walkthrough script (slide-by-slide)

### 0:00–0:40 — Slide 1 (What it is; what’s real)
“This is an AI-assisted prior auth review workflow. Phase 1 exists—OCR ingestion, LLM extraction, decision recording. But Phase 2 ‘intelligence’ is mostly implied: the README shows ML scoring, but the repo only has schema scaffolding and an open issue saying the service was never built. I’m going to ground the rest of this in Grafana + artifacts, and use code to validate what’s real.”

### 0:40–1:40 — Slide 2 (Data trajectory)
“Over 90 days, volume rises from ~200/day to ~340/day while median turnaround worsens from 48 hrs to 55 hrs vs a 28 hr target. Extraction plateaus at 62% for 6 weeks, and active reviewers drop from 5 to 3. That’s a throughput math problem: demand up, capacity down, automation capped.”

### 1:40–3:10 — Slide 3 (Demo = evidence: system health + risks)
“Instead of summarizing loosely, I built a small CLI that reads the same artifacts Phil provided and prints a repeatable report. I’ll run it now.”
Run the CLI and show:
- SYSTEM HEALTH: cite the metrics
- TOP RISKS: PHI debug log line (asymmetric), stability loop, implied analytics feature is literally `todo!()`

### 3:10–4:30 — Slide 4 (Demo = evidence: action plan + blocked decisions)
“Here’s what the team can do Monday morning—owners, why-now, effort, and citations. And here are the decisions that are blocked on product leadership: auto-approve criteria, analytics architecture choice, and whether ML scoring is in scope.”

### 4:30–5:00 — Slide 5 (What I need)
“To change the trajectory, I need three decisions/inputs: clinical ops criteria ownership for auto-approve, an analytics approach choice, and an explanation for the reviewer capacity drop so we don’t optimize the wrong lever.”

Close: “If we align on those decisions this week, the engineering plan becomes straightforward and measurable.”

---

## (d) High-level explanation of what’s built + what’s in the product (with acronyms)

### What you built for this take-home
- **Product archaeology doc**: `cursor-output/product-archaeology.md` (VP Product audience; evidence-grounded narrative)
- **State-of-product memo**: `cursor-output/state-of-product-memo.md` (engineering lead audience; direct, technical)
- **Working prototype**: `cursor-output/prototype/system_state_cli.py` (+ `AI_WORKFLOW.md`, `DEMO.md`)
- **Presentation**: `cursor-output/presentation-outline.md` + real deck `cursor-output/presentation-deck.pptx` (generated with PptxGenJS)

### What’s in the repo (system overview)
- **API (Rust/Axum)**: routes for auth requests, documents, reviews, health, and analytics (`repo/crates/api/src/api.rs:7-31`).
  - Analytics is partially stubbed / `todo!()` (`repo/crates/api/src/endpoints/v1/analytics.rs:7-39`).
- **Core (Rust/sqlx)**: DB queries for pending requests, single request fetch, docs, decisions; includes PHI decryption and audit logging (`repo/crates/core/src/data/queries.rs:7-45`; PHI audit table in `repo/migrations/003_add_phi_audit.sql:1-14`).
  - Pending queue is FIFO today (`repo/crates/core/src/data/queries.rs:69-72`).
  - Debug log prints patient name (risk) (`repo/crates/core/src/data/queries.rs:42`).
- **Pipeline (Python)**: `pipeline/src/batch_runner.py` runs OCR + LLM extraction and logs results but does not write back (`repo/pipeline/src/batch_runner.py:64-66`).
  - OCR processor has polling; comments state missing pre-processing/retry improvements (`repo/pipeline/src/ocr_processor.py:58-100`).
  - LLM extractor calls Anthropic with no retry; parse failures handled with a limited markdown-strip fallback (`repo/pipeline/src/llm_extractor.py:60-83`).
- **Infra**: Helm values show tight API memory (64Mi request / 128Mi limit) (`repo/infra/helm/values.yaml:11-18`).
- **CI**:
  - Rust tests run with migrations in GitHub Actions (`repo/.github/workflows/test.yaml:1-56`).
  - Pipeline CI is disabled (`repo/.github/workflows/pipeline-test.yaml.disabled:1-3`).
  - Release workflow deploys via Helm and references a `values-dev.yaml` that is missing from this snapshot (`repo/.github/workflows/release.yaml:28-33`).

### Acronyms (plain-English)
- **ADR**: Architecture Decision Record (why a major tech choice was made) (`repo/docs/adr/001-rust-over-go.md`).
- **API**: Application Programming Interface (the backend HTTP endpoints).
- **CDC**: Change Data Capture (streaming DB changes into Kafka) (`artifacts/grafana-dashboard.md:77-89`).
- **CI**: Continuous Integration (automated tests on change) (`repo/.github/workflows/test.yaml`).
- **CPT**: Procedure code standard used for billing/authorization (e.g., Issue #24 list) (`repo/ISSUES.md:367-378`).
- **Grafana**: Monitoring dashboard tool (here, “ground truth” metrics) (`artifacts/grafana-dashboard.md`).
- **Helm**: Kubernetes package manager (deployment config) (`repo/infra/helm/values.yaml`).
- **HIPAA/PHI**: Healthcare privacy law / Protected Health Information (patient identifiers) (`repo/migrations/003_add_phi_audit.sql:1-14`).
- **KR/OKR**: Key Result / Objectives & Key Results (quarterly goals) (`artifacts/okr-snapshot.md`).
- **LLM**: Large Language Model (Claude used for extraction) (`repo/pipeline/src/llm_extractor.py:62-67`).
- **OOM**: Out-of-memory kill (process terminated due to memory limit) (`artifacts/grafana-dashboard.md:61-74`; Issue #10 `repo/ISSUES.md:157-170`).
- **P95**: 95th percentile latency (tail latency) (`artifacts/grafana-dashboard.md:61-74`).
- **PR**: Pull Request (change proposal) (`repo/PULL-REQUESTS.md`).

### “Questions to be answered” surfaced by the assignment (explicit list)
- Why did active reviewers drop from 5 → 3? (metric is real; cause unknown) (`artifacts/grafana-dashboard.md:92-103`)
- Which procedure codes qualify for auto-approve and what guardrails/audit trail are required? (`repo/ISSUES.md:367-378`; `artifacts/slack-threads.md:80-87`)
- What analytics architecture is appropriate (materialized views vs replica vs warehouse)? (`repo/ISSUES.md:288-304`; `repo/crates/api/src/endpoints/v1/analytics.rs:20-29`)
- Is ML confidence scoring actually in scope, or should the dead column/README be corrected? (`repo/migrations/007_add_ml_confidence.sql:1-9`; Issue #15 `repo/ISSUES.md:229-241`; `repo/README.md:21-37`)
- What’s the intended end-to-end pipeline integration (batch runner → API write-back), and who owns it? (`repo/pipeline/src/batch_runner.py:64-66`)

---

## (e) 60-minute talk track for the full presentation + interview

### 0–10 min: Slides 1–2 (align on reality and trajectory)
- Goal: get Phil to agree the inputs are grounded and the system is trending worse.
- Use citations and keep it crisp: volume, turnaround, extraction, active reviewers.

### 10–25 min: Live demo (Slides 3–4)
- Run CLI; show “SYSTEM HEALTH” then “TOP RISKS”.
- Pause for questions (Phil will ask “show me the code line” — be ready with citations already printed).
- Move to “ACTION PLAN” and “BLOCKED DECISIONS”.

### 25–40 min: Deep dive Q&A (engineer-style)
Be ready to open these citations fast:
- Analytics `todo!()` (`repo/crates/api/src/endpoints/v1/analytics.rs:20-29`)
- FIFO ordering (`repo/crates/core/src/data/queries.rs:69-72`)
- DB knob parsed-but-unused (`repo/crates/core/src/data/mod.rs:5-13`)
- Pipeline write-back TODO (`repo/pipeline/src/batch_runner.py:64-66`)
- Pipeline CI disabled (`repo/.github/workflows/pipeline-test.yaml.disabled:1-3`)

### 40–55 min: Strategy tradeoffs
- Show you can reason about options:
  - analytics MV vs warehouse
  - stopgap memory bump vs leak profiling
  - extraction hardening vs auto-approve sequencing
- Keep it anchored: “what happens if we delay?” not “what I would like”.

### 55–60 min: Close with explicit asks
- Decisions and inputs (Slide 5) + next-step cadence.

