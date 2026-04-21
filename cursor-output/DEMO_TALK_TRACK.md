# DEMO_TALK_TRACK.md — Auth Review Assistant take-home

Run all commands from the workspace root: `C:\Users\rohan\Documents\Cursor Projects` (or your equivalent path). Python: use `python` or `py -3` on Windows if `python` is not on PATH.

---

## 2-minute demo script (problem → solution)

### Part A — The problem (`--dashboard`, ~60 seconds)

**Say:** “Before proposing auto-approve, I’m grounding the story in production metrics and in the repo. This script’s audit mode pulls the same Grafana snapshot we were given plus a few file-level checks with line citations.”

**Run:**

```bash
python cursor-output/prototype/confidence_gate.py --dashboard
```

**Point to on screen:**

1. **SYSTEM HEALTH — Grafana (FACT):** Median turnaround **55 hrs**, extraction **62%** plateau, volume and reviewer count — every number traces to `artifacts/grafana-dashboard.md` (citations printed inline).
2. **SYSTEM HEALTH — Repo checks:** Call out explicitly:
   - PHI at **`repo/crates/core/src/data/queries.rs:42`**
   - Analytics **`todo!()`** at **`repo/crates/api/src/endpoints/v1/analytics.rs:20-29`**
   - Pipeline CI disabled: **`repo/.github/workflows/pipeline-test.yaml.disabled:1-3`**
3. **TOP RISKS:** Read the `[FACT]`, `[FACT + INFERENCE]`, etc. labels — “I’m not treating inference as fact.”

**Bridge sentence:** “That’s the throughput and trust environment. The product question is: what can we safely automate anyway?”

### Part B — The solution (gate, ~60 seconds)

**Say:** “Draft PR #53 lists five CPT codes verbatim; the hybrid script implements that list and PR #53’s ‘exact match’ intent. The gate only auto-approves when extraction is complete and urgency is routine/standard — which is conservative given the **62%** extraction plateau: most cases never become clean candidates until the pipeline improves.”

**Run:**

```bash
python cursor-output/prototype/confidence_gate.py --input repo/tests/fixtures/sample_auth_request.json
```

**Expected:** `manual_review` for procedure **27447** (knee) — not on the PR #53 list — with JSON `reason` explaining routing.

**Optional — prove auto-approve path:**

```bash
python cursor-output/prototype/confidence_gate.py --test
```

**Close:** “One script: `--dashboard` shows why we’re underwater; the gate shows how we’d still ship auto-approve safely under PM-owned criteria.”

---

## 60-minute interview arc (aligns with CURSOR_INSTRUCTIONS_FOR_DELIVERABLES.md)

| Time | Focus | What to use |
|------|--------|-------------|
| 0–8 min | Problem framing + ground rules | Artifacts = ground truth; code verifies “official story” (`CURSOR_INSTRUCTIONS_FOR_DELIVERABLES.md` evidence rules). |
| 8–20 min | Live demo | `confidence_gate.py --dashboard` then `--input` / `--test`. |
| 20–35 min | Deep dive | Walk `product-archaeology.md` + `state-of-product-memo.md`; be ready to open cited files (PHI line, analytics `todo!()`, FIFO query). |
| 35–48 min | Tradeoffs | Auto-approve vs extraction first; analytics MV vs warehouse (Issue #19); pool wiring vs Helm limits — cite `FACT` vs `INFERENCE`. |
| 48–58 min | Stakeholder + PM ownership | Slack Thread #5, Issue #24, PR #53 questions; who owns CPT list and audit trail. |
| 58–60 min | Ask | One decision you need from leadership this week. |

---

## Deliverables index (what you built)

| File | Role |
|------|------|
| `cursor-output/product-archaeology.md` | VP-style archaeology + technical audit table |
| `cursor-output/state-of-product-memo.md` | Eng lead memo + FACT/INFERENCE + if/then close |
| `cursor-output/prototype/confidence_gate.py` | Hybrid: `--dashboard` / `--audit` + gate + `--test` |
| `cursor-output/prototype/system_state_cli.py` | Full four-section audit (optional; loaded by `--dashboard`) |
| `cursor-output/presentation-outline.md` / `presentation-deck.pptx` | Slides (if part of submission) |
| `cursor-output/INTERVIEW_PREP.md` | Hard questions + pitfalls |

---

## One-liner for “why this prototype?”

The prototype demonstrates that a PM can be the connective tissue between engineering signals and business decisions: it takes the same artifacts (Grafana, Slack, Issues, PRs) and produces a prioritized, citable picture of health, then shows the decision gate that would apply once product criteria match PR #53.
