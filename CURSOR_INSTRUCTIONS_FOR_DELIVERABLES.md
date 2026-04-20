# Cursor Instructions: Auth Review Dashboard

## Goal

Build a single-file Streamlit dashboard that combines the functionality of two existing CLI
prototypes into a visual, interactive interface suitable for a live demo walkthrough.

**Source files (do not rewrite their logic — import from them):**
- `cursor-output/prototype/confidence_gate.py`
- `cursor-output/prototype/system_state_cli.py`

**Output file:** `cursor-output/dashboard/app.py` (single file only — no subdirectories,
no separate CSS, no requirements.txt unless asked)

**Also generate:** `cursor-output/dashboard/sample_batch.json` — exactly 6 sample requests,
one per decision branch, covering every path through `evaluate_request()`. Base the field
structure on the existing `sample_auth_request.json` in the repo. The 6 scenarios must be:

| # | Scenario label | Key conditions | Expected decision |
|---|---|---|---|
| 1 | Routine lipid panel | CPT `80061`, urgency `routine`, all fields complete, no override | `auto_approve` |
| 2 | Incomplete extraction | CPT `80053`, urgency `routine`, `ProviderID` and `DiagnosisCodes` missing/null | `manual_review` |
| 3 | Human override flag | CPT `85025` (CBC, eligible), urgency `routine`, `requires_manual_review: true` | `manual_review` |
| 4 | CPT not on list | CPT `27447` (total knee arthroplasty), urgency `routine`, all fields complete | `manual_review` |
| 5 | Urgent urgency | CPT `93000` (ECG, eligible), urgency `urgent`, all fields complete | `escalate` |
| 6 | Stat + CPT not on list | CPT `99213` (office visit), urgency `stat`, all fields complete | `escalate` |

Each row should use realistic-looking PatientID, ProviderID, RequestID, and DiagnosisCodes
values. Include a `"scenario_label"` field in each object (ignored by the gate) so the
batch results table is self-explanatory during a demo.

**To run (add as comments at top of app.py):**
```
# pip install streamlit
# streamlit run cursor-output/dashboard/app.py
```

---

## Layout Rules

- `st.set_page_config(layout="wide", page_title="Auth Review Dashboard")`
- Two tabs in the main content area: **"System Health & Intelligence"** and **"Confidence Gate"**
- Do not use `st.sidebar`. All navigation is via tabs in the main pane.
- Do not use custom CSS files or external stylesheets.
- Use `st.success()`, `st.warning()`, and `st.error()` for decision outcome banners.
- Use `st.markdown()` with minimal inline HTML only for the decision result banner in the
  Confidence Gate tab (colored badge showing AUTO-APPROVE / MANUAL REVIEW / ESCALATE).

---

## Tab 1: System Health & Intelligence

Replicates the four analysis sections from `system_state_cli.py` as visual panels.
Call `parse_grafana_metrics()`, `repo_reality_checks()`, `build_risks()`,
`build_action_plan()`, and `build_blocked_pm_decisions()` directly from the imported module.

**If artifact files are missing** (`artifacts/grafana-dashboard.md` or
`artifacts/slack-threads.md`), show a `st.error()` explaining which file is missing and
where it is expected. Do not crash. Tab 2 (Confidence Gate) must work independently even
when Tab 1 artifacts are absent.

### Section 1: System Health

Two side-by-side columns using `st.columns(2)`:
- Left column: "Grafana Metrics" — render each `HealthMetric` as `st.metric()`. Use
  `delta` and `delta_color` to signal direction where the value implies trend (e.g.,
  turnaround hours going up = red, extraction % plateaued = orange).
- Right column: "Repo Reality Checks" — render each check as `st.metric()` with a neutral
  delta or a `st.warning()` badge where the check indicates a risk (e.g., `todo!()` panic,
  PHI in debug logs).

### Section 2: Top Risks

Each risk as a `st.expander()` card. Label the expander header with the risk title.
Inside, show "Why it matters" and each evidence citation on its own line. Color-signal
the expander label: prefix with 🔴 for FACT+INFERENCE risks, 🟡 for INFERENCE risks.

### Section 3: Action Plan

Each action item as a `st.expander()` card (consistent with risks section — do not use
`st.dataframe` here). Inside each expander: Owner, Why Now, Effort, and Evidence citations.
Prefix the expander label with a colored effort badge:
- 🟢 for efforts under 1 day
- 🟡 for 1–3 days
- 🔴 for longer

### Section 4: Blocked PM Decisions

Each blocked decision as a `st.warning()` box. Bold the question. Show "Decision needed"
and "Why this blocks" as labeled lines below.

---

## Tab 2: Confidence Gate Evaluator

Import `evaluate_request`, `process_batch`, `GateResult`, `Decision`, and
`AUTO_APPROVE_CPT_CODES` directly from `confidence_gate.py`. Do not rewrite this logic.

### Section A: Summary Metrics Bar

Four `st.metric()` cards in a `st.columns(4)` row at the top:
Total Evaluated / Auto-Approved / Manual Review / Escalated.
These update live as requests are submitted or a batch is uploaded during the session.
Store running totals in `st.session_state`.

### Section B: Editable CPT Auto-Approve List

**This is a key interactive feature.**

Display the current auto-approve CPT code list as an editable table using
`st.data_editor()`. Columns: Code, Description, Enabled (boolean checkbox).

- On load, populate from `AUTO_APPROVE_CPT_CODES` in `confidence_gate.py`.
- The user can add new rows (new CPT code + description), edit existing descriptions,
  or uncheck "Enabled" to temporarily disable a code without deleting it.
- Show a "Reset to defaults" button that restores the original list from
  `AUTO_APPROVE_CPT_CODES`.
- The gate evaluation logic in Section C must use this session-state CPT list, not the
  hardcoded dict, so edits take effect immediately on the next evaluation.
- Add a `st.caption()` below the table: *"Changes apply for this session. In production,
  this list would persist to a configuration store."*

### Section C: Auth Request Builder + Single Request Evaluator

**This is the primary interactive demo feature.** The user builds or edits a full auth
request directly in the dashboard — no JSON file needed. Every field is editable, making
it easy to modify a request mid-demo to show different gate outcomes live.

Layout: two columns using `st.columns([3, 2])`.

**Left column — Auth Request Builder form (`st.form()`):**

All fields pre-populated from `sample_auth_request.json` on first load so the dashboard
is demo-ready immediately:

| Field | Input type | Default value |
|---|---|---|
| RequestID | text_input | `PA-2025-00847` |
| PatientID | text_input | `PT-39201` |
| PatientFirstName | text_input | `Jane` |
| PatientLastName | text_input | `Smith` |
| ProviderID | text_input | `PRV-4421` |
| ProviderName | text_input | `Dr. Robert Chen` |
| NPI | text_input | `1234567890` |
| ProcedureCode | text_input | `27447` |
| ProcedureDescription | text_input | `Total knee arthroplasty` |
| DiagnosisCodes | text_input | `M17.11, M17.12` (comma-separated, parsed to list on submit) |
| DiagnosisDescriptions | text_input | `Primary osteoarthritis, right knee; Primary osteoarthritis, left knee` (semicolon-separated) |
| RequestedServiceDate | date_input | `2025-11-15` |
| UrgencyLevel | selectbox | options: routine / standard / urgent / stat — default: routine |
| ClinicalNotes | text_area | `Patient has failed 6 months of conservative treatment including physical therapy and NSAID therapy. BMI 28. X-rays show Kellgren-Lawrence grade 3-4 bilateral osteoarthritis.` |
| Requires Manual Review override | checkbox | unchecked |

Below the form fields, add two buttons side by side:
- **"Evaluate Request"** (primary) — submits and runs the gate
- **"Reset to Sample"** (secondary) — restores all fields to the `sample_auth_request.json`
  defaults without re-running evaluation

**Right column — Evaluation Result (updates after each submission):**

On submit, call `evaluate_request()` using the session-state CPT list from Section B.
Display result as:
- A large colored banner: 🟢 AUTO-APPROVE / 🟡 MANUAL REVIEW / 🔴 ESCALATE
- The reason text below the banner in normal weight
- Key fields echoed back: RequestID, ProcedureCode, ProcedureDescription, UrgencyLevel,
  ExtractionComplete (boolean), AuditID
- A collapsed `st.expander("Full result JSON")` showing the raw `GateResult` as formatted JSON

On first load (before any submission), show a neutral placeholder in the right column:
`st.info("Fill in the request fields and click Evaluate to see the gate decision.")`

Update the summary metrics in Section A after each submission.

### Section D: Batch Upload

`st.file_uploader()` accepting `.json` files. On upload, call `process_batch()` using the
session-state CPT list. Display results as a `st.dataframe()` with columns: RequestID,
ProcedureCode, UrgencyLevel, Decision, Reason (truncated to 80 chars). Color-code the
Decision column using `st.dataframe` with a pandas Styler — green for auto_approve, yellow
for manual_review, red for escalate.

Update the summary metrics in Section A after batch upload.

### Section E: CPT Reference Table

A static `st.dataframe()` at the bottom showing the current session-state CPT list
(reflects any edits made in Section B). Label it "Current Auto-Approve Eligible Codes."

---

## Demo Walkthrough Order (for reference — informs layout priority)

1. **Tab 1** → System Health metrics (call out extraction plateau + reviewer capacity) →
   Top Risks (expand Risk 1: PHI in logs) → Action Plan → Blocked PM Decisions
2. **Tab 2, Section C** → Point out the pre-populated request (`27447`, knee arthroplasty,
   routine) → hit Evaluate → manual review result → explain why (CPT not on list)
3. **Edit ProcedureCode to `80061`** (lipid panel) → Evaluate → auto-approve → explain
   the gate criteria
4. **Edit UrgencyLevel to `stat`** → Evaluate → escalate → explain urgency branch
5. **Check the override flag** → Evaluate → manual review even with eligible CPT →
   explain human-in-the-loop design intent
6. **Clear ProviderID field** → Evaluate → manual review: incomplete extraction →
   connect this to the 62% extraction plateau on Tab 1
7. **Section B** → Add a new CPT code to the editable list → go back to Section C,
   enter that code → Evaluate → auto-approves → show the list is live, not hardcoded
8. **Section D** → Upload `sample_batch.json` → show the color-coded results table
   covering all 6 scenarios at once

---

## Error Handling

- Missing artifact files: `st.error()` with file path, no crash
- Malformed batch JSON: `st.error("Could not parse uploaded file. Expected a JSON array of request objects.")`
- Empty required fields on submit (RequestID, ProcedureCode, PatientID, ProviderID):
  validate before calling `evaluate_request()` and show `st.warning()` listing which
  fields are missing — do not block submission for optional fields (ClinicalNotes,
  SupportingDocuments, NPI)
- DiagnosisCodes: if the comma-separated field is empty, pass an empty list `[]` to the
  gate — the gate will catch this as an incomplete extraction
- "Reset to Sample" button must restore all form fields to `sample_auth_request.json`
  defaults and clear the result panel without running a new evaluation
- Session state: initialize all session_state keys at the top of the file with defaults
  to prevent KeyError on first run
