# AI Workflow Documentation
**Prototype:** `pipeline/src/confidence_gate.py`  
**Assignment Part 3 — Builder Execution**

---

## What I Built and Why

The confidence gate is the missing product-side layer between what engineering built (Draft PR #53: a Rust endpoint with hardcoded CPT codes) and what's needed to actually ship auto-approve safely. Alex Chen's PR had four open product questions with no one to answer them. This script answers all four, in runnable code.

**What it does:** Takes an extracted auth request (output of `llm_extractor.py`), evaluates it against defined criteria, and returns one of three decisions: `auto_approve`, `manual_review`, or `escalate` — along with a full audit record (the `audit_id` field feeds the `auto_approve_log` table added in migration 009).

**Where it fits in the codebase:**  
`batch_runner.py` (existing) → `ocr_processor.py` (existing) → `llm_extractor.py` (existing) → **`confidence_gate.py`** (new) → POST `/api/v1/auto-approve/run` (PR #53)

---

## AI Tools Used

**Claude (Anthropic) via Claude.ai**  
Primary tool throughout. Used for:
- Cross-artifact synthesis: fed it the PRD, Grafana metrics, OKR snapshot, Slack threads, Issues, and PRs together and asked it to identify the highest-leverage problem across all of them
- Architecture reasoning: asked it to trace the data flow from CDC ingestor → Kafka → API → pipeline and identify where the confidence gate should live
- Initial prototype scaffold: generated the first version of `confidence_gate.py` with all five decision paths
- Code review: asked it to check my test cases against the schema in `sample_auth_request.json` and flag mismatches

**Cursor (AI code editor)**  
Used to navigate and cross-reference the actual codebase files — particularly to verify that the field names in `confidence_gate.py` match the struct definitions in the Rust `core` crate and the sample fixture.

---

## What the AI Got Right on the First Pass

1. **The core gate logic** — the four-check sequence (extraction completeness → override flag → urgency → CPT code) was correct on the first attempt and aligns with the product requirements I defined from the artifacts
2. **The schema alignment** — `GateResult` fields (`audit_id`, `gate_version`, `extraction_complete`) match what migration 009 (from PR #53) would need
3. **The architecture fit comment** — the file header describing where `confidence_gate.py` sits in the pipeline was accurate and complete

---

## What I Fixed Manually

1. **The urgency levels set** — Claude's first version used `{"routine"}` only. I added `"standard"` after re-reading the PRD open questions and the `sample_auth_request.json` which uses `"routine"`. The PRD doesn't define urgency levels exhaustively, so I made an explicit assumption (documented in the code comment) pending clinical ops input.

2. **The test for partial extraction failure** — The initial test case for incomplete extraction (Test 4) only checked for a missing `PatientID`. I updated it to remove `ProviderID` and `DiagnosisCodes` to better simulate the specific failure mode described in Issue #11 (LLM API error mid-extraction).

3. **The `HUMAN_OVERRIDE_FLAG` constant** — Claude named this `manual_review_override`. I renamed it to `requires_manual_review` to match the field naming convention visible in `sample_auth_request.json` and the Rust struct conventions in the codebase.

4. **Added `gate_version` field** — Not in the first AI output. I added it because the criteria list (which CPT codes qualify) will change over time as clinical ops refines the list. Auditors need to know which version of the criteria was applied to each decision. This is a product judgment call, not a code suggestion.

---

## What I Chose Not to Do (and Why)

**I did not build a full ML confidence scorer.**  
The README implies one exists. Issue #15 proves it doesn't. More importantly: we don't need probabilistic ML confidence to ship the first version of auto-approve. Exact CPT code match + routine urgency + complete extraction is already a high-confidence gate. Adding ML scoring before the pipeline reaches 80% extraction would be solving the wrong problem. I called this out explicitly in the State of Product memo.

**I did not wire up the actual Rust API call.**  
The gate produces a `GateResult` that is ready to POST to `/api/v1/auto-approve/run`. But making live API calls in a prototype without a running Kubernetes environment adds complexity without adding demonstration value. The important thing is that the decision logic is correct and the output schema matches what the Rust endpoint expects.

**I did not mock the batch_runner integration.**  
`process_batch()` is included and functional, but I left the actual `batch_runner.py` integration as a comment rather than modifying a file I can't verify won't break the pipeline. The integration point is clearly documented.

---

## Prototype Limitations (Honest Assessment)

- The CPT code list needs clinical ops sign-off before production. The five codes in PR #53 are a starting point, not a final list.
- `urgency_level` normalization (lowercase + strip) assumes consistent input from the LLM extractor. In practice, the extractor may return inconsistent casing — this should be validated against real extraction output.
- There's no integration test against the actual Rust API. The `audit_id` is generated locally but the database write happens in the Rust layer. End-to-end testing requires a running environment.

---

## How I Would Iterate With More Time

1. Pull real extraction outputs from the last 30 days and run them through the gate in `--dry-run` mode to measure the actual auto-approve rate before shipping
2. Add a `--report` flag that outputs a JSON summary suitable for feeding back to the Grafana dashboard
3. Write a proper integration test that spins up the local stack (`docker-compose up`) and tests the full path from gate decision → API write → database record
