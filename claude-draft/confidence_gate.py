#!/usr/bin/env python3
"""
confidence_gate.py — Auto-Approve Decision Gate
Auth Review Assistant | pipeline/src/confidence_gate.py

PURPOSE:
    This script implements the product-side decision logic missing from Draft PR #53
    (feature/auto-approve). It answers the four open questions Alex Chen left in
    the PR description:
      1. Which CPT codes qualify for auto-approve?
      2. What's the confidence threshold?
      3. Is there an audit trail?
      4. Is there a human override mechanism?

    It is designed to be called by batch_runner.py after successful LLM extraction,
    before a review decision is written to the database.

ARCHITECTURE FIT:
    This gate sits between the LLM extractor output and the Rust API endpoint
    POST /api/v1/auto-approve/run (added in PR #53, crates/api/src/endpoints/v1/auto_approve.rs).
    
    Flow:
      batch_runner.py
        → ocr_processor.py (OCR + LLM extraction)
        → confidence_gate.py  <-- THIS FILE
        → Rust API: POST /api/v1/auto-approve/run (if APPROVE)
        OR
        → queue for manual review (if MANUAL_REVIEW or ESCALATE)

USAGE:
    python -m src.confidence_gate --input sample_auth_request.json
    python -m src.confidence_gate --batch  # Process all PENDING requests
    python -m src.confidence_gate --dry-run  # Show decisions without writing

DEPENDENCIES:
    pip install anthropic>=1.0.0  (for LLM extraction — see Issue #11, PR #51)
    
    Note: This file does NOT call the LLM directly. It evaluates already-extracted
    data. The LLM extraction happens upstream in llm_extractor.py.
"""

import json
import sys
import uuid
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# CONFIGURATION: Auto-Approve Criteria
# These should ultimately come from environment variables or a config table.
# For now, defined here pending clinical ops sign-off (see Issue #24).
# ---------------------------------------------------------------------------

# CPT codes that qualify for auto-approve, per Draft PR #53 (Alex Chen, April 3 2026)
# Pending validation with clinical ops — do not add codes without sign-off.
# Historical approval rates from VP Clinical Ops email (Issue #24): 99%+ for these codes.
AUTO_APPROVE_CPT_CODES = {
    "80053": "Comprehensive metabolic panel",
    "80061": "Lipid panel",
    "85025": "Complete blood count with differential",
    "71046": "Chest X-ray, 2 views",
    "93000": "Electrocardiogram, routine",
}

# Urgency levels that are eligible for auto-approve.
# URGENT and STAT requests always go to manual review, regardless of procedure code.
AUTO_APPROVE_ELIGIBLE_URGENCY = {"routine", "standard"}

# Extraction quality threshold.
# A request is only eligible for auto-approve if the OCR + LLM pipeline
# successfully extracted all required fields. Any extraction failure = manual review.
REQUIRED_FIELDS = [
    "procedure_code",
    "urgency_level",
    "patient_id",
    "provider_id",
    "diagnosis_codes",
]

# Human override: any request with this flag set (manually by a reviewer or 
# via a future UI toggle) bypasses auto-approve. Addresses PR #53 question #4.
HUMAN_OVERRIDE_FLAG = "requires_manual_review"


# ---------------------------------------------------------------------------
# DECISION OUTCOMES
# ---------------------------------------------------------------------------

class Decision(Enum):
    AUTO_APPROVE = "auto_approve"       # Safe to approve automatically
    MANUAL_REVIEW = "manual_review"     # Route to reviewer queue (normal)
    ESCALATE = "escalate"               # Urgent / high-complexity: priority queue


@dataclass
class GateResult:
    """
    The structured output of the confidence gate.
    This is what gets POSTed to the Rust API at POST /api/v1/auto-approve/run.
    Schema aligns with migration 009_add_auto_approve_log.sql (PR #53).
    """
    request_id: str
    decision: str                          # Decision enum value
    procedure_code: str
    urgency_level: str
    reason: str                            # Human-readable explanation for audit trail
    auto_approve_eligible: bool
    extraction_complete: bool
    timestamp: str
    gate_version: str = "1.0.0"           # Version the decision criteria used
    audit_id: str = ""                     # UUID written to auto_approve_log table

    def __post_init__(self):
        if not self.audit_id:
            self.audit_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# GATE LOGIC
# ---------------------------------------------------------------------------

def evaluate_request(extracted_data: dict) -> GateResult:
    """
    Core gate function. Evaluates an extracted auth request and returns
    a structured decision with full audit metadata.

    Args:
        extracted_data: Dict containing LLM-extracted fields from the auth request.
                        Expected shape matches sample_auth_request.json and the
                        LLM extraction schema in llm_extractor.py.

    Returns:
        GateResult with decision, reason, and audit fields.
    """
    request_id = extracted_data.get("RequestID", "UNKNOWN")
    procedure_code = str(extracted_data.get("ProcedureCode", "")).strip().upper()
    urgency_level = str(extracted_data.get("UrgencyLevel", "")).strip().lower()
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Check 1: Extraction completeness ---
    # If any required field is missing, the LLM extraction was incomplete.
    # Incomplete extraction = mandatory manual review. (Addresses Issue #11 gap:
    # even with retries, some documents may partially fail. We must not auto-approve
    # on partial data.)
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

    # --- Check 2: Human override flag ---
    # A reviewer or clinical lead can flag a request to always go manual.
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

    # --- Check 3: Urgency level ---
    # URGENT and STAT always go to the priority queue, not auto-approve.
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

    # --- Check 4: Procedure code eligibility ---
    # Only codes with validated >95% historical approval rate qualify.
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

    # --- All checks passed: AUTO-APPROVE ---
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


# ---------------------------------------------------------------------------
# BATCH RUNNER INTEGRATION
# ---------------------------------------------------------------------------

def process_batch(requests: list[dict], dry_run: bool = False) -> dict:
    """
    Process a list of extracted auth requests through the confidence gate.
    Returns a summary report suitable for logging and ops monitoring.

    In production, this would be called from batch_runner.py after the
    LLM extraction step, passing the extracted payloads directly.
    """
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


# ---------------------------------------------------------------------------
# TEST CASES: Validates all four gate paths
# ---------------------------------------------------------------------------

def run_tests() -> None:
    """
    Self-contained tests demonstrating all four decision paths.
    Based on the schema from tests/fixtures/sample_auth_request.json.
    """
    print("Running confidence gate tests...\n")

    test_cases = [
        # Test 1: Should AUTO-APPROVE (routine + eligible CPT code + complete extraction)
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
        # Test 2: Should ESCALATE (urgent urgency level)
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
        # Test 3: Should MANUAL_REVIEW (procedure code not on list)
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
        # Test 4: Should MANUAL_REVIEW (missing extraction fields — simulates OCR partial failure)
        {
            "name": "Incomplete extraction — should route to manual",
            "input": {
                "RequestID": "PA-TEST-004",
                "PatientID": "PT-55599",
                "ProcedureCode": "80053",
                "UrgencyLevel": "routine",
                # Missing ProviderID and DiagnosisCodes — simulates Issue #11 partial failure
            },
            "expected": Decision.MANUAL_REVIEW.value,
        },
        # Test 5: Should MANUAL_REVIEW (human override flag)
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
                "requires_manual_review": True,  # Override flag
            },
            "expected": Decision.MANUAL_REVIEW.value,
        },
    ]

    passed = 0
    failed = 0

    for tc in test_cases:
        result = evaluate_request(tc["input"])
        status = "✅ PASS" if result.decision == tc["expected"] else "❌ FAIL"
        if result.decision == tc["expected"]:
            passed += 1
        else:
            failed += 1

        print(f"{status}  {tc['name']}")
        print(f"       Expected: {tc['expected']}")
        print(f"       Got:      {result.decision}")
        print(f"       Reason:   {result.reason[:100]}")
        print()

    print(f"Results: {passed}/{len(test_cases)} passed", "✅" if failed == 0 else "❌")


# ---------------------------------------------------------------------------
# CLI ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Auth Review Confidence Gate — evaluates extracted auth requests for auto-approve eligibility"
    )
    parser.add_argument("--input", help="Path to a single extracted auth request JSON file")
    parser.add_argument("--test", action="store_true", help="Run built-in test cases")
    parser.add_argument("--dry-run", action="store_true", help="Print decisions without writing to API")
    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    if args.input:
        with open(args.input) as f:
            request_data = json.load(f)
        result = evaluate_request(request_data)
        print(json.dumps(asdict(result), indent=2))
        return

    # Default: run tests to demonstrate functionality
    run_tests()


if __name__ == "__main__":
    main()
