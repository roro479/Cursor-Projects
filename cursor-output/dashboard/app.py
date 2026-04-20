"""Auth Review Dashboard — Streamlit UI for the two CLI prototypes.

Combines system_state_cli.py (System Health & Intelligence) and
confidence_gate.py (Confidence Gate evaluator) into a single interactive
dashboard suitable for a live demo.

# pip install streamlit
# streamlit run cursor-output/dashboard/app.py
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Import the existing prototype modules without rewriting their logic.
# app.py lives in cursor-output/dashboard/; the modules live in cursor-output/prototype/.
# ---------------------------------------------------------------------------
PROTOTYPE_DIR = Path(__file__).resolve().parent.parent / "prototype"
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_DIR))

import confidence_gate as cg  # noqa: E402
import system_state_cli as ssc  # noqa: E402
from confidence_gate import (  # noqa: E402
    AUTO_APPROVE_CPT_CODES,
    Decision,
    GateResult,
    evaluate_request,
    process_batch,
)
from system_state_cli import (  # noqa: E402
    build_action_plan,
    build_blocked_pm_decisions,
    build_risks,
    parse_grafana_metrics,
    repo_reality_checks,
)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Auth Review Dashboard")

# ---------------------------------------------------------------------------
# Sample fixture defaults for the request builder form
# (Structure mirrors repo/tests/fixtures/sample_auth_request.json)
# ---------------------------------------------------------------------------
SAMPLE_DEFAULTS: dict[str, Any] = {
    "RequestID": "PA-2025-00847",
    "PatientID": "PT-39201",
    "PatientFirstName": "Jane",
    "PatientLastName": "Smith",
    "ProviderID": "PRV-4421",
    "ProviderName": "Dr. Robert Chen",
    "NPI": "1234567890",
    "ProcedureCode": "27447",
    "ProcedureDescription": "Total knee arthroplasty",
    "DiagnosisCodes": "M17.11, M17.12",
    "DiagnosisDescriptions": "Primary osteoarthritis, right knee; Primary osteoarthritis, left knee",
    "RequestedServiceDate": date(2025, 11, 15),
    "UrgencyLevel": "routine",
    "ClinicalNotes": (
        "Patient has failed 6 months of conservative treatment including physical "
        "therapy and NSAID therapy. BMI 28. X-rays show Kellgren-Lawrence grade 3-4 "
        "bilateral osteoarthritis."
    ),
    "RequiresManualReview": False,
}

URGENCY_OPTIONS = ["routine", "standard", "urgent", "stat"]
REQUIRED_FORM_FIELDS = ["RequestID", "ProcedureCode", "PatientID", "ProviderID"]


# ---------------------------------------------------------------------------
# Session state initialization — every key seeded so first run never KeyErrors.
# ---------------------------------------------------------------------------
def _default_cpt_list() -> list[dict[str, Any]]:
    return [
        {"code": code, "description": desc, "enabled": True}
        for code, desc in AUTO_APPROVE_CPT_CODES.items()
    ]


def _seed_form_state() -> None:
    for field, value in SAMPLE_DEFAULTS.items():
        st.session_state[f"form_{field}"] = value


def _init_session_state() -> None:
    if "cpt_list" not in st.session_state:
        st.session_state.cpt_list = _default_cpt_list()
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "metric_counts" not in st.session_state:
        st.session_state.metric_counts = {
            "total": 0,
            "auto_approve": 0,
            "manual_review": 0,
            "escalate": 0,
        }
    if "batch_results_df" not in st.session_state:
        st.session_state.batch_results_df = None
    if "last_batch_file_id" not in st.session_state:
        st.session_state.last_batch_file_id = None
    if "form_initialized" not in st.session_state:
        _seed_form_state()
        st.session_state.form_initialized = True


_init_session_state()


# ---------------------------------------------------------------------------
# CPT override helpers — monkey-patch the module constant so Section B edits
# affect Section C/D evaluations without touching gate logic.
# ---------------------------------------------------------------------------
def _effective_cpt_dict() -> dict[str, str]:
    rows = st.session_state.cpt_list
    result: dict[str, str] = {}
    for row in rows:
        code = str(row.get("code", "")).strip().upper()
        if not code:
            continue
        if not row.get("enabled", True):
            continue
        result[code] = str(row.get("description", "")).strip()
    return result


def _run_gate_single(req: dict) -> GateResult:
    cg.AUTO_APPROVE_CPT_CODES = _effective_cpt_dict()
    try:
        return evaluate_request(req)
    finally:
        cg.AUTO_APPROVE_CPT_CODES = AUTO_APPROVE_CPT_CODES


def _run_gate_batch(requests_list: list[dict]) -> dict:
    cg.AUTO_APPROVE_CPT_CODES = _effective_cpt_dict()
    try:
        return process_batch(requests_list)
    finally:
        cg.AUTO_APPROVE_CPT_CODES = AUTO_APPROVE_CPT_CODES


def _bump_counts(decision: str) -> None:
    st.session_state.metric_counts["total"] += 1
    if decision in st.session_state.metric_counts:
        st.session_state.metric_counts[decision] += 1


# ---------------------------------------------------------------------------
# Effort badge parser for Action Plan items.
# Correction #4: check day ranges BEFORE "0.5 day" to avoid early match on
# strings like "~0.5–2 days" (which should be yellow, not green).
# ---------------------------------------------------------------------------
def _effort_badge(effort: str) -> str:
    e = effort.lower()
    day_range = re.search(
        r"(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)\s*days?", e
    )
    if day_range:
        hi = float(day_range.group(2))
        if hi <= 1:
            return "🟢"
        if hi <= 3:
            return "🟡"
        return "🔴"
    if "min" in e or "0.5 day" in e or "~0.5" in e:
        return "🟢"
    single_day = re.search(r"(\d+(?:\.\d+)?)\s*days?", e)
    if single_day:
        n = float(single_day.group(1))
        if n <= 1:
            return "🟢"
        if n <= 3:
            return "🟡"
        return "🔴"
    return "🟡"


DECISION_THEME = {
    "auto_approve": ("#1b7f3a", "🟢 AUTO-APPROVE"),
    "manual_review": ("#b47a00", "🟡 MANUAL REVIEW"),
    "escalate": ("#b02a37", "🔴 ESCALATE"),
}


# ---------------------------------------------------------------------------
# Layout — two tabs
# ---------------------------------------------------------------------------
st.title("Auth Review Dashboard")
st.caption(
    "Live view of system health and the auto-approve decision gate. "
    "All data is read from repo files and artifacts — no production DB connection."
)

tab_health, tab_gate = st.tabs(
    ["System Health & Intelligence", "Confidence Gate"]
)


# ===========================================================================
# TAB 1 — System Health & Intelligence
# ===========================================================================
with tab_health:
    grafana_path = ssc.ARTIFACTS_DIR / "grafana-dashboard.md"
    slack_path = ssc.ARTIFACTS_DIR / "slack-threads.md"

    missing = [p for p in (grafana_path, slack_path) if not p.exists()]
    if missing:
        for p in missing:
            st.error(
                f"Missing required artifact: `{p}`. "
                "System Health cannot render without it. "
                "Run the dashboard from the workspace root so relative paths resolve."
            )
        st.info(
            "The Confidence Gate tab works independently and does not require these artifacts."
        )
    else:
        grafana_text = grafana_path.read_text(encoding="utf-8")
        slack_text = slack_path.read_text(encoding="utf-8")

        health_metrics = parse_grafana_metrics(grafana_text)
        try:
            reality_checks = repo_reality_checks()
        except FileNotFoundError as exc:
            st.error(
                f"Repo reality checks could not read a required file: `{exc.filename}`. "
                "Ensure the `repo/` tree is present alongside `artifacts/`."
            )
            reality_checks = []
        risks = build_risks(slack_text)
        action_items = build_action_plan()
        blocked_decisions = build_blocked_pm_decisions(slack_text)

        # -------- Section 1: System Health (2 columns) --------
        st.header("System Health")
        col_left, col_right = st.columns(2)

        GRAFANA_DELTA: dict[str, tuple[str, str]] = {
            "Avg daily requests (latest)": ("+70% vs Jan", "off"),
            "Median review turnaround (latest)": ("+7 hrs vs Jan baseline", "inverse"),
            "AI extraction success (plateau)": ("flat 6 weeks", "off"),
            "API P95 latency spike": ("threshold 2s", "inverse"),
            "Active reviewers (latest)": ("-2 vs team size", "inverse"),
        }

        with col_left:
            st.subheader("Grafana Metrics")
            for m in health_metrics:
                delta_text, delta_color = GRAFANA_DELTA.get(m.name, ("", "off"))
                st.metric(
                    label=m.name,
                    value=m.value,
                    delta=delta_text or None,
                    delta_color=delta_color,
                )
                st.caption(f"Source: `{m.evidence.citation}`")

        RISKY_CHECK_NAMES = {
            "Analytics turnaround endpoint",
            "PHI in debug logs",
            "Pipeline CI",
            "Pipeline integration",
        }

        with col_right:
            st.subheader("Repo Reality Checks")
            for c in reality_checks:
                st.metric(
                    label=c.name,
                    value=c.value,
                    delta=None,
                    delta_color="off",
                )
                st.caption(f"Source: `{c.evidence.citation}`")
                if c.name in RISKY_CHECK_NAMES:
                    st.warning(f"Risk flagged: {c.evidence.citation}")

        # -------- Section 2: Top Risks --------
        # Spec: FACT or FACT+INFERENCE -> red, INFERENCE-only -> yellow.
        # All risks currently produced have FACT evidence, so default to red
        # and downgrade to yellow only if the text is INFERENCE-only.
        st.header("Top Risks")
        for idx, r in enumerate(risks, 1):
            inference_only = (
                "INFERENCE" in r.why_it_matters.upper()
                and "PLATEAUED" not in r.why_it_matters.upper()
                and len(r.evidence) == 0
            )
            prefix = "🟡" if inference_only else "🔴"
            with st.expander(f"{prefix} Risk {idx}: {r.title}"):
                st.markdown(f"**Why it matters:** {r.why_it_matters}")
                st.markdown("**Evidence:**")
                for e in r.evidence:
                    st.markdown(f"- `{e.citation}` — {e.label}")

        # -------- Section 3: Action Plan --------
        st.header("Action Plan (prioritized)")
        for idx, a in enumerate(action_items, 1):
            badge = _effort_badge(a.effort)
            with st.expander(f"{badge} {idx}. {a.title}"):
                st.markdown(f"**Owner:** {a.owner}")
                st.markdown(f"**Why now:** {a.why_now}")
                st.markdown(f"**Effort:** {a.effort}")
                st.markdown("**Evidence:**")
                for e in a.evidence:
                    st.markdown(f"- `{e.citation}` — {e.label}")

        # -------- Section 4: Blocked PM Decisions --------
        st.header("Blocked Pending PM Decision")
        for b in blocked_decisions:
            evidence_lines = "\n".join(
                f"- `{e.citation}` — {e.label}" for e in b.evidence
            )
            st.warning(
                f"**{b.question}**\n\n"
                f"**Decision needed:** {b.decision_needed}\n\n"
                f"**Why this blocks:** {b.why_this_blocks}\n\n"
                f"**Evidence:**\n{evidence_lines}"
            )


# ===========================================================================
# TAB 2 — Confidence Gate Evaluator
# ===========================================================================
with tab_gate:
    # -------- Section A: Summary Metrics Bar --------
    st.header("Summary")
    counts = st.session_state.metric_counts
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Total Evaluated", counts["total"])
    mcol2.metric("Auto-Approved", counts["auto_approve"])
    mcol3.metric("Manual Review", counts["manual_review"])
    mcol4.metric("Escalated", counts["escalate"])
    st.divider()

    # -------- Section B: Editable CPT Auto-Approve List --------
    st.header("Auto-Approve CPT Codes")
    st.caption(
        "Edit descriptions, toggle Enabled, or add new rows. "
        "Changes apply immediately to the gate evaluator below."
    )

    # Correction #2: assign the return value of st.data_editor back to session state.
    st.session_state.cpt_list = st.data_editor(
        st.session_state.cpt_list,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "code": st.column_config.TextColumn("Code", required=True),
            "description": st.column_config.TextColumn("Description"),
            "enabled": st.column_config.CheckboxColumn("Enabled", default=True),
        },
        key="cpt_editor",
    )

    reset_cpt, _cpt_spacer = st.columns([1, 4])
    with reset_cpt:
        if st.button("Reset to defaults", key="reset_cpt_btn"):
            st.session_state.cpt_list = _default_cpt_list()
            st.rerun()
    st.caption(
        "Changes apply for this session. In production, this list would persist "
        "to a configuration store."
    )
    st.divider()

    # -------- Section C: Auth Request Builder + Single Request Evaluator --------
    st.header("Evaluate an Auth Request")
    builder_col, result_col = st.columns([3, 2])

    with builder_col:
        with st.form("auth_request_form", clear_on_submit=False):
            st.subheader("Auth Request Builder")

            c1, c2 = st.columns(2)
            with c1:
                st.text_input("RequestID", key="form_RequestID")
                st.text_input("PatientID", key="form_PatientID")
                st.text_input("PatientFirstName", key="form_PatientFirstName")
                st.text_input("PatientLastName", key="form_PatientLastName")
                st.text_input("ProviderID", key="form_ProviderID")
                st.text_input("ProviderName", key="form_ProviderName")
                st.text_input("NPI", key="form_NPI")
            with c2:
                st.text_input("ProcedureCode", key="form_ProcedureCode")
                st.text_input("ProcedureDescription", key="form_ProcedureDescription")
                st.text_input(
                    "DiagnosisCodes (comma-separated)",
                    key="form_DiagnosisCodes",
                )
                st.text_input(
                    "DiagnosisDescriptions (semicolon-separated)",
                    key="form_DiagnosisDescriptions",
                )
                st.date_input(
                    "RequestedServiceDate",
                    key="form_RequestedServiceDate",
                )
                st.selectbox(
                    "UrgencyLevel",
                    options=URGENCY_OPTIONS,
                    key="form_UrgencyLevel",
                )

            st.text_area(
                "ClinicalNotes",
                key="form_ClinicalNotes",
                height=100,
            )
            st.checkbox(
                "Requires Manual Review (human override)",
                key="form_RequiresManualReview",
            )

            # Correction #1: both buttons captured as separate booleans, then dispatched.
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                evaluate_clicked = st.form_submit_button(
                    "Evaluate Request", type="primary", use_container_width=True
                )
            with btn_col2:
                reset_clicked = st.form_submit_button(
                    "Reset to Sample", type="secondary", use_container_width=True
                )

    # Dispatch — Reset first (no evaluation), then Evaluate.
    if reset_clicked:
        _seed_form_state()
        st.session_state.last_result = None
        st.rerun()

    if evaluate_clicked:
        missing_fields = [
            f for f in REQUIRED_FORM_FIELDS
            if not str(st.session_state.get(f"form_{f}", "")).strip()
        ]
        if missing_fields:
            st.warning(
                "Missing required fields: " + ", ".join(missing_fields) +
                ". Fill them in and click Evaluate again."
            )
        else:
            diag_raw = str(st.session_state.form_DiagnosisCodes or "")
            diag_list = [s.strip() for s in diag_raw.split(",") if s.strip()]
            diag_desc_raw = str(st.session_state.form_DiagnosisDescriptions or "")
            diag_desc_list = [
                s.strip() for s in diag_desc_raw.split(";") if s.strip()
            ]
            service_date = st.session_state.form_RequestedServiceDate
            if isinstance(service_date, date):
                service_date_iso = service_date.isoformat()
            else:
                service_date_iso = str(service_date)

            req = {
                "RequestID": st.session_state.form_RequestID,
                "PatientID": st.session_state.form_PatientID,
                "PatientFirstName": st.session_state.form_PatientFirstName,
                "PatientLastName": st.session_state.form_PatientLastName,
                "ProviderID": st.session_state.form_ProviderID,
                "ProviderName": st.session_state.form_ProviderName,
                "NPI": st.session_state.form_NPI,
                "ProcedureCode": st.session_state.form_ProcedureCode,
                "ProcedureDescription": st.session_state.form_ProcedureDescription,
                "DiagnosisCodes": diag_list,
                "DiagnosisDescriptions": diag_desc_list,
                "RequestedServiceDate": service_date_iso,
                "UrgencyLevel": st.session_state.form_UrgencyLevel,
                "ClinicalNotes": st.session_state.form_ClinicalNotes,
                "requires_manual_review": bool(
                    st.session_state.form_RequiresManualReview
                ),
            }
            result = _run_gate_single(req)
            st.session_state.last_result = asdict(result)
            _bump_counts(result.decision)

    with result_col:
        st.subheader("Evaluation Result")
        result = st.session_state.last_result
        if result is None:
            st.info(
                "Fill in the request fields and click Evaluate to see the gate decision."
            )
        else:
            color, label = DECISION_THEME.get(
                result["decision"], ("#444444", result["decision"].upper())
            )
            st.markdown(
                f'<div style="background:{color};color:white;padding:16px;'
                f'border-radius:8px;font-size:20px;font-weight:700;'
                f'text-align:center;">{label}</div>',
                unsafe_allow_html=True,
            )
            st.write("")
            st.write(result["reason"])
            st.write("---")
            st.write(f"**RequestID:** {result['request_id']}")
            st.write(f"**ProcedureCode:** {result['procedure_code']}")
            proc_desc = (
                AUTO_APPROVE_CPT_CODES.get(result["procedure_code"])
                or st.session_state.form_ProcedureDescription
                or "(not provided)"
            )
            st.write(f"**ProcedureDescription:** {proc_desc}")
            st.write(f"**UrgencyLevel:** {result['urgency_level']}")
            st.write(f"**ExtractionComplete:** {result['extraction_complete']}")
            st.write(f"**AuditID:** `{result['audit_id']}`")
            st.write(f"**GateVersion:** {result['gate_version']}")
            with st.expander("Full result JSON", expanded=False):
                st.json(result)

    st.divider()

    # -------- Section D: Batch Upload --------
    st.header("Batch Upload")
    st.caption(
        "Upload a JSON array of auth request objects. "
        "Try `cursor-output/dashboard/sample_batch.json` for the 6 demo scenarios."
    )
    uploaded = st.file_uploader(
        "Upload batch JSON", type=["json"], key="batch_uploader"
    )

    if uploaded is not None and uploaded.file_id != st.session_state.last_batch_file_id:
        try:
            raw = uploaded.getvalue().decode("utf-8")
            requests_list = json.loads(raw)
            if not isinstance(requests_list, list):
                raise ValueError("Expected a JSON array of request objects.")
        except Exception:
            st.error(
                "Could not parse uploaded file. "
                "Expected a JSON array of request objects."
            )
        else:
            results_by_decision = _run_gate_batch(requests_list)
            flat_rows: list[dict[str, Any]] = []
            for decision_key, result_list in results_by_decision.items():
                for res in result_list:
                    as_dict = asdict(res)
                    source = next(
                        (
                            r for r in requests_list
                            if r.get("RequestID") == as_dict["request_id"]
                        ),
                        {},
                    )
                    flat_rows.append(
                        {
                            "scenario_label": source.get("scenario_label", ""),
                            "RequestID": as_dict["request_id"],
                            "ProcedureCode": as_dict["procedure_code"],
                            "UrgencyLevel": as_dict["urgency_level"],
                            "Decision": as_dict["decision"],
                            "Reason": (
                                as_dict["reason"][:80] + "..."
                                if len(as_dict["reason"]) > 80
                                else as_dict["reason"]
                            ),
                        }
                    )
                    _bump_counts(as_dict["decision"])

            # Correction #5: scenario_label is the first column.
            df = pd.DataFrame(
                flat_rows,
                columns=[
                    "scenario_label",
                    "RequestID",
                    "ProcedureCode",
                    "UrgencyLevel",
                    "Decision",
                    "Reason",
                ],
            )
            st.session_state.batch_results_df = df
            st.session_state.last_batch_file_id = uploaded.file_id
            st.rerun()

    if st.session_state.batch_results_df is not None:
        df = st.session_state.batch_results_df

        # Correction #3: df.style.map (not applymap, deprecated in pandas 2.1).
        def _color_decision(v: str) -> str:
            return {
                "auto_approve": "background-color: #1b7f3a; color: white",
                "manual_review": "background-color: #b47a00; color: white",
                "escalate": "background-color: #b02a37; color: white",
            }.get(v, "")

        styler = df.style.map(_color_decision, subset=["Decision"])
        st.dataframe(styler, use_container_width=True)

    st.divider()

    # -------- Section E: CPT Reference Table --------
    st.header("Current Auto-Approve Eligible Codes")
    enabled_rows = [
        row for row in st.session_state.cpt_list if row.get("enabled", True)
    ]
    if enabled_rows:
        st.dataframe(pd.DataFrame(enabled_rows), use_container_width=True)
    else:
        st.info("No CPT codes are currently enabled. Edit the list above.")
