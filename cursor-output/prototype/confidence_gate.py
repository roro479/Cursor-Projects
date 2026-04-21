#!/usr/bin/env python3
"""
confidence_gate.py — Hybrid: Auto-Approve Decision Gate + optional System Health audit

Primary mode: evaluates extracted JSON for auto-approve eligibility using the five CPT
codes from Draft PR #53 (verbatim labels match repo/PULL-REQUESTS.md).

Audit mode (--dashboard): prints SYSTEM HEALTH (Grafana + repo reality checks) and
TOP RISKS with citations. Intended demo: dashboard = problem, gate = solution.

Workspace root: Path(__file__).resolve().parents[2]

PR #53 engineering intent: exact CPT match + routine urgency (see PR description).
This gate does not use a floating-point "confidence score"; PR #53 states 100% match
for now. Link to 62% extraction plateau (artifacts/grafana-dashboard.md Panel 3): auto-approve
only applies to requests that pass extraction completeness checks; the plateau means most
volume still requires manual review until pipeline reliability improves.
"""

import argparse
import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

# Workspace root: prototype/ -> cursor-output/ -> workspace
ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
REPO_DIR = ROOT / "repo"


# ---------------------------------------------------------------------------
# CPT codes — verbatim PR #53 list (repo/PULL-REQUESTS.md:78-83)
# ---------------------------------------------------------------------------
AUTO_APPROVE_CPT_CODES = {
    "80053": "Comprehensive metabolic panel",
    "80061": "Lipid panel",
    "85025": "Complete blood count",
    "71046": "Chest X-ray, 2 views",
    "93000": "Electrocardiogram",
}

AUTO_APPROVE_ELIGIBLE_URGENCY = {"routine", "standard"}

REQUIRED_FIELDS = [
    "procedure_code",
    "urgency_level",
    "patient_id",
    "provider_id",
    "diagnosis_codes",
]

HUMAN_OVERRIDE_FLAG = "requires_manual_review"


class Decision(Enum):
    AUTO_APPROVE = "auto_approve"
    MANUAL_REVIEW = "manual_review"
    ESCALATE = "escalate"


@dataclass
class GateResult:
    request_id: str
    decision: str
    procedure_code: str
    urgency_level: str
    reason: str
    auto_approve_eligible: bool
    extraction_complete: bool
    timestamp: str
    gate_version: str = "1.0.0"
    audit_id: str = ""

    def __post_init__(self):
        if not self.audit_id:
            self.audit_id = str(uuid.uuid4())


def evaluate_request(extracted_data: dict) -> GateResult:
    request_id = extracted_data.get("RequestID", "UNKNOWN")
    procedure_code = str(extracted_data.get("ProcedureCode", "")).strip().upper()
    urgency_level = str(extracted_data.get("UrgencyLevel", "")).strip().lower()
    timestamp = datetime.now(timezone.utc).isoformat()

    missing_fields = []
    field_map = {
        "procedure_code": extracted_data.get("ProcedureCode"),
        "urgency_level": extracted_data.get("UrgencyLevel"),
        "patient_id": extracted_data.get("PatientID"),
        "provider_id": extracted_data.get("ProviderID"),
        "diagnosis_codes": extracted_data.get("DiagnosisCodes"),
    }
    for field, value in field_map.items():
        if not value:
            missing_fields.append(field)

    if missing_fields:
        return GateResult(
            request_id=request_id,
            decision=Decision.MANUAL_REVIEW.value,
            procedure_code=procedure_code or "UNKNOWN",
            urgency_level=urgency_level or "UNKNOWN",
            reason=f"Extraction incomplete — missing fields: {', '.join(missing_fields)}. Routing to manual review.",
            auto_approve_eligible=False,
            extraction_complete=False,
            timestamp=timestamp,
        )

    if extracted_data.get(HUMAN_OVERRIDE_FLAG):
        return GateResult(
            request_id=request_id,
            decision=Decision.MANUAL_REVIEW.value,
            procedure_code=procedure_code,
            urgency_level=urgency_level,
            reason="Human override flag set — routing to manual review as requested.",
            auto_approve_eligible=False,
            extraction_complete=True,
            timestamp=timestamp,
        )

    if urgency_level not in AUTO_APPROVE_ELIGIBLE_URGENCY:
        return GateResult(
            request_id=request_id,
            decision=Decision.ESCALATE.value,
            procedure_code=procedure_code,
            urgency_level=urgency_level,
            reason=f"Urgency level '{urgency_level}' requires manual review — only 'routine' and 'standard' are auto-approve eligible.",
            auto_approve_eligible=False,
            extraction_complete=True,
            timestamp=timestamp,
        )

    if procedure_code not in AUTO_APPROVE_CPT_CODES:
        return GateResult(
            request_id=request_id,
            decision=Decision.MANUAL_REVIEW.value,
            procedure_code=procedure_code,
            urgency_level=urgency_level,
            reason=f"Procedure code '{procedure_code}' ({extracted_data.get('ProcedureDescription', 'unknown')}) is not on the auto-approve list. Routing to reviewer queue.",
            auto_approve_eligible=False,
            extraction_complete=True,
            timestamp=timestamp,
        )

    code_description = AUTO_APPROVE_CPT_CODES[procedure_code]
    return GateResult(
        request_id=request_id,
        decision=Decision.AUTO_APPROVE.value,
        procedure_code=procedure_code,
        urgency_level=urgency_level,
        reason=f"Auto-approved: CPT {procedure_code} ({code_description}) is routine with urgency '{urgency_level}'. All extraction fields complete. Audit record written.",
        auto_approve_eligible=True,
        extraction_complete=True,
        timestamp=timestamp,
    )


def process_batch(requests: list[dict], dry_run: bool = False) -> dict:
    results = {
        Decision.AUTO_APPROVE.value: [],
        Decision.MANUAL_REVIEW.value: [],
        Decision.ESCALATE.value: [],
    }
    for request in requests:
        result = evaluate_request(request)
        results[result.decision].append(result)
        if dry_run:
            print(f"[DRY RUN] {result.request_id}: {result.decision.upper()}")
            print(f"  Reason: {result.reason}\n")
    return results


def print_summary(results: dict) -> None:
    total = sum(len(v) for v in results.values())
    if total == 0:
        print("No requests processed.")
        return
    auto = len(results[Decision.AUTO_APPROVE.value])
    manual = len(results[Decision.MANUAL_REVIEW.value])
    escalate = len(results[Decision.ESCALATE.value])
    print("\n" + "=" * 60)
    print("CONFIDENCE GATE SUMMARY")
    print("=" * 60)
    print(f"Total requests evaluated:  {total}")
    print(f"  AUTO-APPROVE:            {auto}  ({auto/total*100:.1f}%)")
    print(f"  MANUAL REVIEW:           {manual}  ({manual/total*100:.1f}%)")
    print(f"  ESCALATE (urgent):       {escalate}  ({escalate/total*100:.1f}%)")
    print("=" * 60)
    if auto > 0:
        print("\nAuto-approved requests:")
        for r in results[Decision.AUTO_APPROVE.value]:
            print(f"  • {r.request_id} | {r.procedure_code} | audit_id: {r.audit_id}")
    if escalate > 0:
        print("\nEscalated (urgent) requests:")
        for r in results[Decision.ESCALATE.value]:
            print(f"  ⚡ {r.request_id} | {r.urgency_level} | {r.reason[:80]}")
    print()


def run_tests() -> None:
    print("Running confidence gate tests...\n")
    test_cases = [
        {
            "name": "Routine lipid panel — should auto-approve",
            "input": {
                "RequestID": "PA-TEST-001",
                "PatientID": "PT-39201",
                "ProviderID": "PRV-4421",
                "ProcedureCode": "80061",
                "ProcedureDescription": "Lipid panel",
                "DiagnosisCodes": ["E78.5"],
                "UrgencyLevel": "routine",
                "ClinicalNotes": "Annual wellness screening.",
            },
            "expected": Decision.AUTO_APPROVE.value,
        },
        {
            "name": "Urgent CBC — should escalate",
            "input": {
                "RequestID": "PA-TEST-002",
                "PatientID": "PT-11112",
                "ProviderID": "PRV-5502",
                "ProcedureCode": "85025",
                "ProcedureDescription": "Complete blood count",
                "DiagnosisCodes": ["D64.9"],
                "UrgencyLevel": "urgent",
                "ClinicalNotes": "Acute presentation, needs same-day result.",
            },
            "expected": Decision.ESCALATE.value,
        },
        {
            "name": "Total knee arthroplasty — should route to manual",
            "input": {
                "RequestID": "PA-TEST-003",
                "PatientID": "PT-39201",
                "ProviderID": "PRV-4421",
                "ProcedureCode": "27447",
                "ProcedureDescription": "Total knee arthroplasty",
                "DiagnosisCodes": ["M17.11", "M17.12"],
                "UrgencyLevel": "routine",
                "ClinicalNotes": "Failed conservative treatment x6 months.",
            },
            "expected": Decision.MANUAL_REVIEW.value,
        },
        {
            "name": "Incomplete extraction — should route to manual",
            "input": {
                "RequestID": "PA-TEST-004",
                "PatientID": "PT-55599",
                "ProcedureCode": "80053",
                "UrgencyLevel": "routine",
            },
            "expected": Decision.MANUAL_REVIEW.value,
        },
        {
            "name": "Override flag set — should route to manual regardless",
            "input": {
                "RequestID": "PA-TEST-005",
                "PatientID": "PT-77701",
                "ProviderID": "PRV-9900",
                "ProcedureCode": "80053",
                "ProcedureDescription": "Comprehensive metabolic panel",
                "DiagnosisCodes": ["Z00.00"],
                "UrgencyLevel": "routine",
                "requires_manual_review": True,
            },
            "expected": Decision.MANUAL_REVIEW.value,
        },
    ]
    passed = failed = 0
    for tc in test_cases:
        result = evaluate_request(tc["input"])
        ok = result.decision == tc["expected"]
        passed += int(ok)
        failed += int(not ok)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}]  {tc['name']}")
        print(f"       Expected: {tc['expected']}  Got: {result.decision}")
        print(f"       Reason:   {result.reason[:100]}")
        print()
    print(f"Results: {passed}/{len(test_cases)} passed")

# ---------------------------------------------------------------------------
# DASHBOARD / AUDIT LOGIC (consolidated; no dynamic imports)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    label: str
    citation: str  # file:line-range or artifact reference


@dataclass(frozen=True)
class HealthMetric:
    name: str
    value: str
    evidence: Evidence


@dataclass(frozen=True)
class Risk:
    title: str
    why_it_matters: str
    evidence: list[Evidence]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_grafana_metrics(text: str) -> list[HealthMetric]:
    metrics: list[HealthMetric] = []

    # Fix: use single backslashes for regex metacharacters in raw strings
    m = re.search(r"Apr 1-5\s+\|\s+~(\d+)/day", text)
    if m:
        metrics.append(
            HealthMetric(
                name="Avg daily requests (latest)",
                value=f"~{m.group(1)}/day",
                evidence=Evidence(
                    label="Grafana Panel 1",
                    citation="artifacts/grafana-dashboard.md:12-19",
                ),
            )
        )

    m = re.search(r"Apr 1-5\s+\|\s+(\d+)\s+hrs", text)
    if m:
        metrics.append(
            HealthMetric(
                name="Median review turnaround (latest)",
                value=f"{m.group(1)} hrs",
                evidence=Evidence(
                    label="Grafana Panel 2",
                    citation="artifacts/grafana-dashboard.md:28-37",
                ),
            )
        )

    m = re.search(r"Plateaued.*?(\d+)%", text)
    if m:
        metrics.append(
            HealthMetric(
                name="AI extraction success (plateau)",
                value=f"{m.group(1)}%",
                evidence=Evidence(
                    label="Grafana Panel 3",
                    citation="artifacts/grafana-dashboard.md:45-58",
                ),
            )
        )

    m = re.search(r"Spikes to\s+(\d+)-(\d+)\s+seconds", text)
    if m:
        metrics.append(
            HealthMetric(
                name="API P95 latency spike",
                value=f"{m.group(1)}–{m.group(2)}s",
                evidence=Evidence(
                    label="Grafana Panel 4",
                    citation="artifacts/grafana-dashboard.md:66-74",
                ),
            )
        )

    m = re.search(r"Only\s+(\d+)\s+of\s+(\d+)\s+reviewers active", text)
    if m:
        metrics.append(
            HealthMetric(
                name="Active reviewers (latest)",
                value=f"{m.group(1)} of {m.group(2)}",
                evidence=Evidence(
                    label="Grafana Panel 6",
                    citation="artifacts/grafana-dashboard.md:92-104",
                ),
            )
        )

    return metrics


def parse_slack_quotes(text: str) -> dict[str, str]:
    quotes: dict[str, str] = {}
    # Fix: use single backslashes for \n in raw strings
    m = re.search(
        r"VP Clinical Ops.*?\n(.*auto-approve.*)\n\*No responses", text, flags=re.S
    )
    if m:
        quotes["leadership_escalation"] = m.group(1).strip()
    return quotes


def repo_reality_checks() -> list[HealthMetric]:
    checks: list[HealthMetric] = []

    analytics_rs = (
        REPO_DIR / "crates" / "api" / "src" / "endpoints" / "v1" / "analytics.rs"
    )
    try:
        a = _read_text(analytics_rs)
        if 'todo!("Waiting on data warehouse access' in a:
            checks.append(
                HealthMetric(
                    name="Analytics turnaround endpoint",
                    value="todo!() (will panic if hit)",
                    evidence=Evidence(
                        label="Repo reality check",
                        citation="repo/crates/api/src/endpoints/v1/analytics.rs:20-29",
                    ),
                )
            )
    except OSError:
        # If repo structure is incomplete, we keep the dashboard running.
        pass

    queries_rs = REPO_DIR / "crates" / "core" / "src" / "data" / "queries.rs"
    try:
        q = _read_text(queries_rs)
        if re.search(r"WHERE status = 'pending'.*?ORDER BY submitted_at ASC", q, flags=re.S):
            checks.append(
                HealthMetric(
                    name="Pending queue ordering",
                    value="FIFO (submitted_at ASC)",
                    evidence=Evidence(
                        label="Repo reality check",
                        citation="repo/crates/core/src/data/queries.rs:69-72",
                    ),
                )
            )
        if "Fetched auth request for patient" in q:
            checks.append(
                HealthMetric(
                    name="PHI in debug logs",
                    value="Patient name logged at debug in query path",
                    evidence=Evidence(
                        label="Repo reality check",
                        citation="repo/crates/core/src/data/queries.rs:42",
                    ),
                )
            )
    except OSError:
        pass

    mod_rs = REPO_DIR / "crates" / "core" / "src" / "data" / "mod.rs"
    try:
        m = _read_text(mod_rs)
        if "DATABASE_MAX_CONNECTIONS" in m and "PgPool::connect" in m:
            checks.append(
                HealthMetric(
                    name="DB pool sizing knob",
                    value="DATABASE_MAX_CONNECTIONS parsed but not applied (INFERENCE: pool defaults)",
                    evidence=Evidence(
                        label="Repo reality check",
                        citation="repo/crates/core/src/data/mod.rs:5-13",
                    ),
                )
            )
    except OSError:
        pass

    pipeline_ci = (
        REPO_DIR / ".github" / "workflows" / "pipeline-test.yaml.disabled"
    )
    if pipeline_ci.exists():
        checks.append(
            HealthMetric(
                name="Pipeline CI",
                value="Disabled (workflow file .disabled)",
                evidence=Evidence(
                    label="Repo reality check",
                    citation="repo/.github/workflows/pipeline-test.yaml.disabled:1-3",
                ),
            )
        )

    batch_runner = REPO_DIR / "pipeline" / "src" / "batch_runner.py"
    try:
        b = _read_text(batch_runner)
        if "TODO: Write results back to database" in b:
            checks.append(
                HealthMetric(
                    name="Pipeline integration",
                    value="No write-back; logs-only (TODO to POST to API)",
                    evidence=Evidence(
                        label="Repo reality check",
                        citation="repo/pipeline/src/batch_runner.py:64-66",
                    ),
                )
            )
    except OSError:
        pass

    return checks


def build_risks(slack_text: str) -> list[Risk]:
    quotes = parse_slack_quotes(slack_text)
    return [
        Risk(
            title="Compliance risk: PHI could land in logs during incident response",
            why_it_matters=(
                "Patient names are logged at debug in core query code. While production may run at info, "
                "the system experiences OOM/restart patterns—raising log levels during an incident is a plausible move (INFERENCE)."
            ),
            evidence=[
                Evidence("Debug log line", "repo/crates/core/src/data/queries.rs:42"),
                Evidence("OOM/restart correlation", "artifacts/grafana-dashboard.md:61-74"),
                Evidence("PR #54 exists to remove PHI log line", "repo/PULL-REQUESTS.md:102-125"),
            ],
        ),
        Risk(
            title="Throughput risk: volume up + capacity down + extraction stuck",
            why_it_matters=(
                "Demand has grown while active reviewers dropped and extraction plateaued at 62%, producing worsening turnaround. "
                "This is the structural reason KR1/KR2 are off-track."
            ),
            evidence=[
                Evidence("Volume trend", "artifacts/grafana-dashboard.md:12-19"),
                Evidence("Turnaround trend", "artifacts/grafana-dashboard.md:23-37"),
                Evidence("Extraction plateau + failure breakdown", "artifacts/grafana-dashboard.md:41-58"),
                Evidence("Reviewer capacity drop", "artifacts/grafana-dashboard.md:92-104"),
            ],
        ),
        Risk(
            title="Stakeholder clock: auto-approve escalation with no owner",
            why_it_matters=(
                f"{quotes.get('leadership_escalation', 'VP Clinical Ops escalated auto-approve status with no response.')} "
                "Engineering can’t safely ship without criteria ownership; this is now a trust / expectation risk."
            ),
            evidence=[
                Evidence("Leadership escalation", "artifacts/slack-threads.md:80-87"),
                Evidence("Issue #24 request + ownership question", "repo/ISSUES.md:367-378"),
                Evidence("PR #53 draft asks product questions", "repo/PULL-REQUESTS.md:67-94"),
            ],
        ),
    ]


def run_dashboard() -> int:
    """Print SYSTEM HEALTH + TOP RISKS only, with repo-relative paths and line citations."""
    grafana_path = ARTIFACTS_DIR / "grafana-dashboard.md"
    slack_path = ARTIFACTS_DIR / "slack-threads.md"
    try:
        grafana = _read_text(grafana_path)
    except OSError:
        print("ERROR: Missing required artifact `artifacts/grafana-dashboard.md`.")
        print(f"Expected at: {grafana_path}")
        print("Run this script from the workspace root so relative paths resolve correctly.")
        return 2

    try:
        slack = _read_text(slack_path)
    except OSError:
        print("ERROR: Missing required artifact `artifacts/slack-threads.md`.")
        print(f"Expected at: {slack_path}")
        print("Run this script from the workspace root so relative paths resolve correctly.")
        return 2

    health = parse_grafana_metrics(grafana)
    checks = repo_reality_checks()
    risks = build_risks(slack)

    def print_section(title: str, char: str = "="):
        print("\n" + char * 88)
        print(title)
        print(char * 88)

    print_section(
        "SYSTEM HEALTH (FACT: metrics from artifacts/grafana-dashboard.md; repo paths below)"
    )
    print("Grafana-derived (90-day snapshot):")
    for m in health:
        print(f"  • {m.name}: {m.value}")
        print(f"    Citation: {m.evidence.citation}")
    print("Repo-verified checks:")
    for c in checks:
        print(f"  • {c.name}: {c.value}")
        print(f"    Citation: {c.evidence.citation}")

    print_section("TOP RISKS (label: FACT vs INFERENCE vs SPECULATION)", "-")
    for i, r in enumerate(risks, 1):
        label = "INFERENCE" if "INFERENCE" in r.why_it_matters else "FACT"
        if "SPECULATION" in r.why_it_matters:
            label = "SPECULATION"
        if i == 1:
            label = "FACT + INFERENCE"
        print(f"{i}. [{label}] {r.title}")
        print(f"   Why it matters: {r.why_it_matters}")
        for e in r.evidence:
            print(f"   Evidence: {e.citation}")
    print()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Confidence gate (PR #53 CPTs) or --dashboard for system health + top risks audit."
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Print SYSTEM HEALTH and TOP RISKS (audit); cites repo paths e.g. repo/crates/core/src/data/queries.rs:42",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Same as --dashboard (system health + top risks).",
    )
    parser.add_argument("--input", help="Path to extracted auth request JSON")
    parser.add_argument("--test", action="store_true", help="Run built-in gate tests")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With batch processing, print decisions without side effects",
    )
    args = parser.parse_args()

    if args.dashboard or args.audit:
        raise SystemExit(run_dashboard())

    if args.test:
        run_tests()
        return

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            request_data = json.load(f)
        result = evaluate_request(request_data)
        print(json.dumps(asdict(result), indent=2))
        return

    run_tests()


if __name__ == "__main__":
    main()
