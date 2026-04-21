import pptxgen from "pptxgenjs";
import fs from "node:fs";
import path from "node:path";

const OUT_PATH = path.resolve("presentation-deck.pptx");
const OUTLINE_PATH = path.resolve("presentation-outline.md");

function assertExists(p) {
  if (!fs.existsSync(p)) {
    throw new Error(`Missing required file: ${p}`);
  }
}

function addTitle(slide, title) {
  slide.addText(title, {
    x: 0.6,
    y: 0.4,
    w: 12.1,
    h: 0.6,
    fontFace: "Calibri",
    fontSize: 32,
    bold: true,
    color: "1F2937",
  });
}

function addSubtitle(slide, text) {
  slide.addText(text, {
    x: 0.6,
    y: 1.2,
    w: 12.1,
    h: 0.6,
    fontFace: "Calibri",
    fontSize: 18,
    color: "374151",
  });
}

function addBullets(slide, bullets, opts = {}) {
  const {
    x = 0.9,
    y = 1.9,
    w = 11.6,
    h = 5.0,
    fontSize = 18,
  } = opts;

  const runs = [];
  for (const b of bullets) {
    runs.push({ text: b + "\n", options: { bullet: { indent: 18 }, hanging: 6 } });
  }
  slide.addText(runs, {
    x,
    y,
    w,
    h,
    fontFace: "Calibri",
    fontSize,
    color: "111827",
    valign: "top",
  });
}

function addCallout(slide, title, body, x, y, w, h, borderColor = "9CA3AF") {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    fill: { color: "F9FAFB" },
    line: { color: borderColor, width: 1 },
  });
  slide.addText(title, {
    x: x + 0.2,
    y: y + 0.15,
    w: w - 0.4,
    h: 0.3,
    fontFace: "Calibri",
    fontSize: 14,
    bold: true,
    color: "111827",
  });
  slide.addText(body, {
    x: x + 0.2,
    y: y + 0.5,
    w: w - 0.4,
    h: h - 0.6,
    fontFace: "Calibri",
    fontSize: 12,
    color: "374151",
    valign: "top",
  });
}

function addFooter(slide, text) {
  slide.addText(text, {
    x: 0.6,
    y: 7.05,
    w: 12.1,
    h: 0.3,
    fontFace: "Calibri",
    fontSize: 10,
    color: "6B7280",
  });
}

function speakerNotes(md) {
  // PptxGenJS supports notes via slide.addNotes(string)
  // Keep notes short; detailed talk track lives in INTERVIEW_PREP.md
  return md;
}

assertExists(OUTLINE_PATH);

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Cursor (GPT-5.2)";

// Slide 1
{
  const slide = pptx.addSlide();
  addTitle(slide, "Auth Review Assistant — Week 1 Readout");
  addSubtitle(slide, "What’s real in the repo, what the data shows, and what we do Monday morning");
  addCallout(
    slide,
    "Repo reality check",
    "README depicts ML Scoring Service; repo shows schema scaffolding but no implementation.\nEvidence: repo/README.md:21-37; repo/migrations/007_add_ml_confidence.sql:1-9; repo/ISSUES.md:229-241",
    0.9,
    2.2,
    5.8,
    1.4,
    "60A5FA"
  );
  addCallout(
    slide,
    "Phase status",
    "PRD: Phase 1 shipped; Phase 2 “Intelligence” not started.\nEvidence: repo/docs/prd-ai-review-v2.md:23-40",
    6.9,
    2.2,
    5.6,
    1.4,
    "34D399"
  );
  addCallout(
    slide,
    "Key framing",
    "Ground truth = Grafana + artifacts. Code is used to validate what’s real vs implied.",
    0.9,
    3.85,
    11.6,
    1.05,
    "9CA3AF"
  );
  addFooter(slide, "Sources: repo/docs/prd-ai-review-v2.md; repo/README.md; repo/migrations; repo/ISSUES.md");
  slide.addNotes(
    speakerNotes(
      "Open with: I treated Grafana+artifacts as ground truth, and used code to validate what’s real vs implied."
    )
  );
}

// Slide 2
{
  const slide = pptx.addSlide();
  addTitle(slide, "90-day trajectory (Grafana): demand up, outcomes worse");
  addBullets(slide, [
    "Volume: ~200/day → ~340/day (Panel 1)",
    "Turnaround: 48 hrs → 55 hrs vs 28 hr target (Panel 2)",
    "Extraction: plateau at 62% for 6 weeks; failure buckets known (Panel 3)",
    "Active reviewers: 5 → 3 (Panel 6)",
  ]);
  addCallout(
    slide,
    "Why it matters",
    "This is a throughput math problem: rising demand + falling capacity + capped automation ⇒ worsening turnaround.",
    0.9,
    5.25,
    11.6,
    1.4,
    "F59E0B"
  );
  addFooter(slide, "Evidence: artifacts/grafana-dashboard.md Panels 1–3,6");
  slide.addNotes(
    speakerNotes(
      "Say: This is the math. The brief Feb improvement coincides with pipeline rollout, but volume growth overwhelms gains."
    )
  );
}

// Slide 3 (DEMO)
{
  const slide = pptx.addSlide();
  addTitle(slide, "System health + top risks (Demo = evidence)");
  addSubtitle(slide, "Run: python cursor-output/prototype/system_state_cli.py");
  addCallout(
    slide,
    "Demo sections (Slide 3)",
    "SYSTEM HEALTH\nTOP RISKS",
    0.9,
    1.9,
    3.7,
    1.2,
    "06B6D4"
  );
  addCallout(
    slide,
    "Risk 1 (asymmetric): PHI in debug logs",
    "Patient names logged at debug in core query path.\nEvidence: repo/crates/core/src/data/queries.rs:42; PR #54 in repo/PULL-REQUESTS.md",
    4.8,
    1.9,
    7.7,
    1.2,
    "EF4444"
  );
  addCallout(
    slide,
    "Risk 2: stability loop",
    "P95 latency spikes correlate with restarts; pattern consistent with OOM/leak loop.\nEvidence: artifacts/grafana-dashboard.md Panel 4; Issue #10",
    0.9,
    3.25,
    5.8,
    1.55,
    "EF4444"
  );
  addCallout(
    slide,
    "Risk 3: implied features not implemented",
    "Analytics turnaround endpoint is todo!() (will panic if hit).\nEvidence: repo/crates/api/src/endpoints/v1/analytics.rs:20-29; Issue #19",
    6.9,
    3.25,
    5.6,
    1.55,
    "EF4444"
  );
  addFooter(slide, "Demo file: cursor-output/prototype/system_state_cli.py (prints citations inline)");
  slide.addNotes(
    speakerNotes(
      "Live-demo the CLI. Slide 3 is ‘proved’ by SYSTEM HEALTH and TOP RISKS sections."
    )
  );
}

// Slide 4 (DEMO)
{
  const slide = pptx.addSlide();
  addTitle(slide, "Monday-morning plan + what’s blocked on PM decisions (Demo)");
  addSubtitle(slide, "Same CLI run: ACTION PLAN + WHAT'S BLOCKED PENDING PM DECISION");
  addCallout(
    slide,
    "Action Plan (prioritized)",
    "1) Merge PR #54 (PHI)\n2) Unblock PR #47 (OCR caching)\n3) Re-enable pipeline CI\n4) Ship urgency sort\n5) Wire DATABASE_MAX_CONNECTIONS\n6) Bump API memory stopgap",
    0.9,
    1.9,
    5.8,
    3.1,
    "22C55E"
  );
  addCallout(
    slide,
    "Blocked pending PM decisions",
    "Auto-approve criteria + guardrails (clinical ops + legal path)\nAnalytics approach: MV vs replica vs warehouse\nML scoring: build vs remove dead column/soften README",
    6.9,
    1.9,
    5.6,
    3.1,
    "FBBF24"
  );
  addCallout(
    slide,
    "Why this prototype",
    "Turns dispersed signals (Grafana, Slack, Issues, PRs) into an executable plan and makes missing decisions impossible to ignore.",
    0.9,
    5.2,
    11.6,
    1.35,
    "60A5FA"
  );
  addFooter(slide, "Evidence is printed in the CLI output; see cursor-output/prototype/DEMO.md for talk track.");
  slide.addNotes(
    speakerNotes(
      "Demo ACTION PLAN + BLOCKED decisions. Use the ‘connective tissue’ framing verbatim if asked why CLI over pipeline fix."
    )
  );
}

// Slide 5
{
  const slide = pptx.addSlide();
  addTitle(slide, "What I need (decisions/inputs I can’t make alone)");
  addBullets(slide, [
    "Clinical ops: validate auto-approve CPT list + override + audit expectations (Issue #24)",
    "Engineering + Product: choose analytics approach (Issue #19; analytics endpoint is todo!())",
    "Leadership/ops: explain active reviewer drop 5 → 3 (capacity driver; cause unknown)",
    "Platform: confirm deploy source-of-truth (runbook drift vs Helm reality)",
  ]);
  addCallout(
    slide,
    "Close",
    "If we align on these decisions this week, the engineering path to improving the trajectory becomes straightforward and measurable.",
    0.9,
    5.25,
    11.6,
    1.2,
    "9CA3AF"
  );
  addFooter(slide, "Evidence: artifacts/grafana-dashboard.md; repo/ISSUES.md; repo/crates/api/src/endpoints/v1/analytics.rs; repo/docs/operations/runbook.md");
  slide.addNotes(
    speakerNotes(
      "End with explicit asks. Emphasize: I’m not asking for permission to code—I’m asking for decisions that unblock execution."
    )
  );
}

await pptx.writeFile({ fileName: OUT_PATH });
console.log(`Wrote ${OUT_PATH}`);

