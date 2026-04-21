## Demo: System State CLI (this IS Slides 3–4)

### Goal

Run one command and walk Phil through “what the evidence says” and “what we do Monday morning,” while proving you read the repo and artifacts.

### One-command run

From the workspace root (`C:/Users/rohan/Documents/Cursor Projects`):

```bash
python cursor-output/prototype/system_state_cli.py
```

If `rich` is installed, the output will be color/formatted. If not, it prints plain text.

### What to show (section-by-section)

#### Slide 3 evidence: SYSTEM HEALTH

Narration (30–45s):
- “This is the reality in numbers from the provided Grafana snapshot, plus a few repo checks that indicate where the product is ‘real’ vs ‘implied’.”

Callouts to point at in the terminal output:
- Median turnaround and volume trend (`artifacts/grafana-dashboard.md:12-37`)
- Extraction plateau + failure breakdown (`artifacts/grafana-dashboard.md:41-58`)
- Active reviewers drop (`artifacts/grafana-dashboard.md:92-103`)
- Repo checks: analytics `todo!()`, FIFO queue ordering, pipeline CI disabled, pipeline write-back TODO, DB knob parsed-but-unused

#### Slide 3 evidence: TOP RISKS

Narration (45–60s):
- “I’m not listing everything wrong. These are the three risks that compound the trajectory: compliance asymmetry, throughput math, and stakeholder clock/ownership.”

Proof points:
- PHI debug log line exists (`repo/crates/core/src/data/queries.rs:42`; PR #54 in `repo/PULL-REQUESTS.md:102-125`)
- Throughput chain is shown in Grafana + OKRs (`artifacts/grafana-dashboard.md`, `artifacts/okr-snapshot.md:10-24`)
- Auto-approve escalation with no response (`artifacts/slack-threads.md:80-87`; Issue #24 in `repo/ISSUES.md:367-378`)

#### Slide 4 evidence: ACTION PLAN (prioritized)

Narration (60–90s):
- “This is the Monday-morning list: owners, why-now, expected effort, and citations. It’s designed to be executable without a new strategy deck.”

Key emphasis:
- Merge PR #54 (fast, asymmetric risk)
- Unblock PR #47 (already approved; throughput lever)
- Re-enable pipeline CI (stop regressions; reduce invisible drift)
- Ship urgency sort (high felt pain, small change)
- Wire `DATABASE_MAX_CONNECTIONS` properly (tuning knob should match reality)
- Bump API memory stopgap while investigating leak

#### Slide 4 evidence: WHAT'S BLOCKED PENDING PM DECISION

Narration (45–60s):
- “This is the PM part: not writing requirements in isolation, but making the missing decisions explicit so engineering isn’t blocked or forced to guess.”

Decisions to highlight:
- Auto-approve criteria + guardrails (clinical ops + legal path)
- Analytics computation approach (materialized views vs warehouse vs replica)
- ML scoring scope vs remove dead column / soften README claims

### “Why did you build this instead of a pipeline fix?” (use this wording)

“This tool demonstrates what a PM does that an engineer can’t: it turns dispersed signals across Slack, Grafana, Issues, and PRs into a prioritized action list that the team can act on Monday morning. The PM’s job isn’t to have all the answers—it’s to make the right questions impossible to ignore.”

