#!/usr/bin/env python3
"""
System State CLI — Auth Review Assistant

Purpose:
  Turn the same artifacts provided in the take-home (Grafana, Slack, Issues, PRs)
  plus a small set of “repo reality checks” into a Monday-morning prioritized action list.

Demo mapping to slides:
  - Slides 3–4 in the presentation are “proven” by running this CLI live.
    Slide 3: SYSTEM HEALTH + TOP RISKS
    Slide 4: ACTION PLAN + WHAT'S BLOCKED PENDING PM DECISION
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
REPO_DIR = ROOT / "repo"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _safe_int(s: str) -> int | None:
    try:
        return int(s)
    except Exception:
        return None


def _safe_float(s: str) -> float | None:
    try:
        return float(s)
    except Exception:
        return None


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


@dataclass(frozen=True)
class ActionItem:
    title: str
    owner: str
    why_now: str
    effort: str
    evidence: list[Evidence]


@dataclass(frozen=True)
class BlockedDecision:
    question: str
    decision_needed: str
    why_this_blocks: str
    evidence: list[Evidence]


def parse_grafana_metrics(text: str) -> list[HealthMetric]:
    metrics: list[HealthMetric] = []

    # Panel 1 volume endpoints
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

    # Panel 2 median turnaround (latest)
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

    # Panel 3 extraction plateau
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

    # Panel 4 P95 latency spikes
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

    # Panel 6 active reviewers latest window
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
    # Leadership escalation
    m = re.search(r"VP Clinical Ops.*?\n(.*auto-approve.*)\n\*No responses", text, flags=re.S)
    if m:
        line = m.group(1).strip()
        quotes["leadership_escalation"] = line
    # Reviewer urgency pain (Thread 3)
    m = re.search(r"Thread 3:.*?waste\s+(\d+)-(\d+)\s+minutes.*?morning", text, flags=re.S)
    if m:
        quotes["queue_pain"] = f"Reviewers report wasting {m.group(1)}–{m.group(2)} minutes each morning finding urgent cases."
    return quotes


def repo_reality_checks() -> list[HealthMetric]:
    checks: list[HealthMetric] = []

    # Analytics turnaround endpoint is todo!()
    analytics_rs = REPO_DIR / "crates" / "api" / "src" / "endpoints" / "v1" / "analytics.rs"
    a = _read_text(analytics_rs)
    if "todo!(\"Waiting on data warehouse access" in a:
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

    # Pending queue ORDER BY
    queries_rs = REPO_DIR / "crates" / "core" / "src" / "data" / "queries.rs"
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

    # PHI debug log line existence
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

    # DB max connections parsed but unused
    mod_rs = REPO_DIR / "crates" / "core" / "src" / "data" / "mod.rs"
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

    # Pipeline CI disabled file exists
    pipeline_ci = REPO_DIR / ".github" / "workflows" / "pipeline-test.yaml.disabled"
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

    # Pipeline entrypoint integration gap
    batch_runner = REPO_DIR / "pipeline" / "src" / "batch_runner.py"
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


def build_action_plan() -> list[ActionItem]:
    return [
        ActionItem(
            title="Merge PR #54 to remove PHI from debug logs",
            owner="Eng Lead (review) + Jordan (author)",
            why_now="Asymmetric risk: one log-level toggle during an incident could create PHI in logs.",
            effort="~15–30 min review + merge",
            evidence=[
                Evidence("PR #54 description", "repo/PULL-REQUESTS.md:102-125"),
                Evidence("Debug PHI log line", "repo/crates/core/src/data/queries.rs:42"),
            ],
        ),
        ActionItem(
            title="Resolve and merge PR #47 (OCR caching) to reduce duplicate OCR work",
            owner="Sarah (pipeline) + Alex (unblock merge conflict)",
            why_now="Extraction is plateaued; PR is approved but blocked by merge conflict.",
            effort="~30–90 min conflict resolution + merge",
            evidence=[
                Evidence("PR #47 approved but unmerged", "repo/PULL-REQUESTS.md:5-36"),
                Evidence("OKR KR2 calls PR #47 blocker", "artifacts/okr-snapshot.md:10-24"),
            ],
        ),
        ActionItem(
            title="Re-enable pipeline CI by fixing the OCR mock and removing .disabled",
            owner="Jordan (CI/infra) + Sarah (pipeline tests)",
            why_now="Pipeline changes are shipping without automated checks; config drift already caused an incident.",
            effort="~0.5–2 days (depends on mock approach)",
            evidence=[
                Evidence("Workflow disabled header", "repo/.github/workflows/pipeline-test.yaml.disabled:1-3"),
                Evidence("Slack Thread #2 confirms disabled CI", "artifacts/slack-threads.md:28-42"),
                Evidence("Issue #16 config drift", "repo/ISSUES.md:245-261"),
            ],
        ),
        ActionItem(
            title="Ship urgency-sorted queue (use existing priority/urgency field) to remove daily reviewer waste",
            owner="API engineer",
            why_now="Reviewers explicitly report daily time loss and urgent cases buried behind routine cases.",
            effort="~0.5 day (query + API surface + test)",
            evidence=[
                Evidence("Issue #26", "repo/ISSUES.md:395-406"),
                Evidence("FIFO ordering in code", "repo/crates/core/src/data/queries.rs:69-72"),
                Evidence("Slack Thread #3 reviewer pain", "artifacts/slack-threads.md:46-60"),
            ],
        ),
        ActionItem(
            title="Wire `DATABASE_MAX_CONNECTIONS` into PgPoolOptions and set it from Helm/env",
            owner="API engineer",
            why_now="Load issues are being debugged with assumptions about a knob that isn’t wired; tuning is guesswork right now.",
            effort="~0.5 day (code + config + test)",
            evidence=[
                Evidence("Env var exists", "repo/.env.example:1-4"),
                Evidence("Parsed but unused", "repo/crates/core/src/data/mod.rs:5-13"),
                Evidence("Issue #2 load timeouts", "repo/ISSUES.md:35-50"),
            ],
        ),
        ActionItem(
            title="Bump API memory limits as stopgap while investigating leak",
            owner="Infra/Platform",
            why_now="Grafana shows restart-correlated latency spikes consistent with OOM loop; current limits are 128Mi in Helm values.",
            effort="~30 min config change + deploy (plus follow-up profiling)",
            evidence=[
                Evidence("Helm API memory limit", "repo/infra/helm/values.yaml:11-18"),
                Evidence("Grafana restart correlation narrative", "artifacts/grafana-dashboard.md:61-74"),
                Evidence("Issue #10 memory growth", "repo/ISSUES.md:157-170"),
            ],
        ),
    ]


def build_blocked_pm_decisions(slack_text: str) -> list[BlockedDecision]:
    quotes = parse_slack_quotes(slack_text)
    return [
        BlockedDecision(
            question="Auto-approve: which CPT codes qualify, with what guardrails?",
            decision_needed="Define initial CPT list + eligibility rules + audit expectations; align with clinical ops and legal review needs (unknown in repo).",
            why_this_blocks=(
                f"{quotes.get('leadership_escalation', 'Escalation exists.')} "
                "Engineering can implement mechanics, but criteria ownership is a PM decision."
            ),
            evidence=[
                Evidence("Issue #24 (codes + ownership question)", "repo/ISSUES.md:367-378"),
                Evidence("PR #53 product questions", "repo/PULL-REQUESTS.md:67-94"),
                Evidence("Leadership escalation", "artifacts/slack-threads.md:80-87"),
            ],
        ),
        BlockedDecision(
            question="Analytics: where should ‘turnaround time dashboard’ compute live?",
            decision_needed="Choose approach (materialized views vs replica vs warehouse) and define the first 2–3 metrics that matter.",
            why_this_blocks="Endpoint exists but is stubbed/todo!(); without a decision, the team can’t ship requested dashboards safely.",
            evidence=[
                Evidence("Analytics endpoint is todo!()", "repo/crates/api/src/endpoints/v1/analytics.rs:20-29"),
                Evidence("Issue #19 options", "repo/ISSUES.md:288-304"),
            ],
        ),
        BlockedDecision(
            question="ML scoring service: still in scope, or remove dead column + README claims?",
            decision_needed="Decide whether to build ML confidence scoring in Phase 2 or remove/soften claims and schema artifacts.",
            why_this_blocks="README implies a service that doesn’t exist; schema contains a column but no implementation path is visible in this repo snapshot.",
            evidence=[
                Evidence("README ML scoring depiction", "repo/README.md:21-37"),
                Evidence("Migration adds ml_confidence_score", "repo/migrations/007_add_ml_confidence.sql:1-9"),
                Evidence("Issue #15: dead column", "repo/ISSUES.md:229-241"),
            ],
        ),
    ]


def _try_rich():
    try:
        from rich.console import Console  # type: ignore
        from rich.panel import Panel  # type: ignore
        from rich.table import Table  # type: ignore
        from rich.text import Text  # type: ignore

        return Console, Panel, Table, Text
    except Exception:
        return None


def render_plain(
    health: list[HealthMetric],
    checks: list[HealthMetric],
    risks: list[Risk],
    actions: list[ActionItem],
    blocked: list[BlockedDecision],
) -> None:
    def h1(title: str):
        print("\n" + "=" * 88)
        print(title)
        print("=" * 88)

    h1("SYSTEM HEALTH")
    for m in health:
        print(f"- {m.name}: {m.value}  ({m.evidence.citation})")
    for c in checks:
        print(f"- {c.name}: {c.value}  ({c.evidence.citation})")

    h1("TOP RISKS")
    for i, r in enumerate(risks, 1):
        print(f"{i}. {r.title}")
        print(f"   - Why it matters: {r.why_it_matters}")
        for e in r.evidence:
            print(f"   - Evidence: {e.citation}")

    h1("ACTION PLAN (prioritized)")
    for i, a in enumerate(actions, 1):
        print(f"{i}. {a.title}")
        print(f"   - Owner: {a.owner}")
        print(f"   - Why now: {a.why_now}")
        print(f"   - Effort: {a.effort}")
        for e in a.evidence:
            print(f"   - Evidence: {e.citation}")

    h1("WHAT'S BLOCKED PENDING PM DECISION")
    for i, b in enumerate(blocked, 1):
        print(f"{i}. {b.question}")
        print(f"   - Decision needed: {b.decision_needed}")
        print(f"   - Why this blocks: {b.why_this_blocks}")
        for e in b.evidence:
            print(f"   - Evidence: {e.citation}")


def render_rich(
    health: list[HealthMetric],
    checks: list[HealthMetric],
    risks: list[Risk],
    actions: list[ActionItem],
    blocked: list[BlockedDecision],
) -> None:
    Console, Panel, Table, Text = _try_rich()  # type: ignore[misc]
    console = Console()

    def metrics_table(title: str, metrics: list[HealthMetric]) -> Table:
        t = Table(title=title, show_header=True, header_style="bold")
        t.add_column("Metric", style="bold")
        t.add_column("Value")
        t.add_column("Evidence", overflow="fold")
        for m in metrics:
            t.add_row(m.name, m.value, m.evidence.citation)
        return t

    console.print(Panel.fit("[bold]SYSTEM HEALTH[/bold] (Slide 3)", border_style="cyan"))
    console.print(metrics_table("Grafana (production reality)", health))
    console.print(metrics_table("Repo reality checks", checks))

    console.print()
    console.print(Panel.fit("[bold]TOP RISKS[/bold] (Slide 3)", border_style="red"))
    for idx, r in enumerate(risks, 1):
        t = Table(show_header=False, box=None)
        t.add_column("k", style="bold")
        t.add_column("v", overflow="fold")
        t.add_row(f"{idx}.", f"[bold]{r.title}[/bold]")
        t.add_row("", f"[bold]Why it matters[/bold]: {r.why_it_matters}")
        for e in r.evidence:
            t.add_row("", f"[bold]Evidence[/bold]: {e.citation}")
        console.print(t)
        console.print()

    console.print(Panel.fit("[bold]ACTION PLAN (prioritized)[/bold] (Slide 4)", border_style="green"))
    for idx, a in enumerate(actions, 1):
        t = Table(show_header=False, box=None)
        t.add_column("k", style="bold")
        t.add_column("v", overflow="fold")
        t.add_row(f"{idx}.", f"[bold]{a.title}[/bold]")
        t.add_row("", f"[bold]Owner[/bold]: {a.owner}")
        t.add_row("", f"[bold]Why now[/bold]: {a.why_now}")
        t.add_row("", f"[bold]Effort[/bold]: {a.effort}")
        for e in a.evidence:
            t.add_row("", f"[bold]Evidence[/bold]: {e.citation}")
        console.print(t)
        console.print()

    console.print(Panel.fit("[bold]WHAT'S BLOCKED PENDING PM DECISION[/bold] (Slide 4)", border_style="yellow"))
    for idx, b in enumerate(blocked, 1):
        t = Table(show_header=False, box=None)
        t.add_column("k", style="bold")
        t.add_column("v", overflow="fold")
        t.add_row(f"{idx}.", f"[bold]{b.question}[/bold]")
        t.add_row("", f"[bold]Decision needed[/bold]: {b.decision_needed}")
        t.add_row("", f"[bold]Why this blocks[/bold]: {b.why_this_blocks}")
        for e in b.evidence:
            t.add_row("", f"[bold]Evidence[/bold]: {e.citation}")
        console.print(t)
        console.print()


def main(argv: list[str]) -> int:
    grafana_path = ARTIFACTS_DIR / "grafana-dashboard.md"
    slack_path = ARTIFACTS_DIR / "slack-threads.md"

    if not grafana_path.exists() or not slack_path.exists():
        print("ERROR: expected artifacts missing. Run from repo workspace root.")
        print(f"Missing: {grafana_path if not grafana_path.exists() else ''} {slack_path if not slack_path.exists() else ''}")
        return 2

    grafana = _read_text(grafana_path)
    slack = _read_text(slack_path)

    health = parse_grafana_metrics(grafana)
    checks = repo_reality_checks()
    risks = build_risks(slack)
    actions = build_action_plan()
    blocked = build_blocked_pm_decisions(slack)

    if _try_rich():
        render_rich(health, checks, risks, actions, blocked)
    else:
        render_plain(health, checks, risks, actions, blocked)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

