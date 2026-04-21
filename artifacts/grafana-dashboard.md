# Grafana Dashboard: Auth Review Assistant
**Dashboard URL:** grafana.internal/d/auth-review
**Time Range:** Last 90 days (January 5 — April 5, 2026)

---

## Panel 1: Auth Request Volume (daily)
**Type:** Time series line chart
**Y-axis:** Requests per day
**Trend:** Steadily increasing

| Period | Avg Daily Requests | Notes |
|--------|-------------------|-------|
| Jan 5-31 | ~200/day | Stable baseline |
| Feb 1-28 | ~245/day | +22% month-over-month |
| Mar 1-31 | ~305/day | +24% month-over-month |
| Apr 1-5 | ~340/day | Continuing acceleration |

**Notable:** The growth rate is accelerating, not linear. Weekday volume is ~30% higher than weekends. Monday is consistently the highest-volume day (~380 requests on recent Mondays).

---

## Panel 2: Median Review Turnaround Time
**Type:** Time series line chart with target line
**Y-axis:** Hours from submission to decision
**Target line:** 28 hours (dashed red)

| Period | Median Turnaround | Notes |
|--------|-------------------|-------|
| Jan 5-31 | 48 hrs | Baseline at quarter start |
| Feb 1-14 | 46 hrs | Slight improvement after LLM extraction launch |
| Feb 15-28 | 49 hrs | Regression — higher volume absorbs the gains |
| Mar 1-15 | 52 hrs | Continued worsening |
| Mar 16-31 | 54 hrs | |
| Apr 1-5 | 55 hrs | 15% worse than baseline |

**Notable:** The brief improvement in early February coincides with the LLM extraction pipeline going live. But volume growth overwhelmed the efficiency gain within 2 weeks. The target of 28 hours is nowhere close.

---

## Panel 3: AI Extraction Success Rate
**Type:** Time series area chart
**Y-axis:** Percentage of documents successfully processed by OCR + LLM pipeline

| Period | Success Rate | Notes |
|--------|-------------|-------|
| Jan 5-31 | 0% | Pipeline not yet live |
| Feb 1-7 | 35% | Initial rollout, many failures |
| Feb 8-28 | 55% | Stabilization after bug fixes |
| Mar 1-15 | 61% | Gradual improvement |
| Mar 16-Apr 5 | 62% | **Plateaued — flat for 6 weeks** |

**Failure breakdown (from last 30 days):**
- OCR failure (rotated/poor quality): 20%
- OCR timeout (large documents): 8%
- LLM extraction failure (API error, no retry): 6%
- LLM parse failure (invalid JSON output): 4%

---

## Panel 4: API P95 Latency
**Type:** Time series line chart with threshold
**Y-axis:** Milliseconds
**Threshold line:** 2000ms (red)

| Period | P95 Latency (avg) | Spikes | Notes |
|--------|--------------------|--------|-------|
| Jan-Feb | ~800ms | Rare | Stable |
| Mar 1-15 | ~1,200ms | 2 events | Latency creeping up with volume |
| Mar 16-31 | ~1,200ms | 4 events | Spikes to 6-8 seconds every 2-3 days |
| Apr 1-5 | ~1,400ms | 2 events | Worsening trend |

**Notable:** The periodic spikes to 6-8 seconds correlate with API pod restarts (OOM kills). After restart, latency drops to ~400ms and gradually climbs over 24-48 hours. Pattern is consistent with a memory leak.

---

## Panel 5: CDC Event Processing Lag
**Type:** Time series line chart
**Y-axis:** Seconds of lag between event production and consumption

| Period | Avg Lag | Max Lag | Spike Events | Notes |
|--------|---------|---------|-------------|-------|
| Jan-Feb | <10s | 120s | 1 spike | Generally healthy |
| Mar 1-15 | <10s | 2,700s (45 min) | 2 spikes | Spikes to 45 min |
| Mar 16-31 | <15s | 2,700s (45 min) | 1 spike | |
| Apr 1-5 | <10s | 600s (10 min) | 1 spike | |

**Notable:** The 45-minute lag spikes in March coincide with Kafka consumer group rebalances (see Issue #4). During a spike, new auth requests are not visible to reviewers until the lag clears. After the spike resolves, a burst of events processes rapidly (catching up).

---

## Panel 6: Active Reviewers
**Type:** Bar chart (weekly)
**Y-axis:** Number of distinct reviewers who submitted at least one decision

| Week | Active Reviewers | Total Reviewers | Notes |
|------|-----------------|-----------------|-------|
| Jan 6-12 | 5 | 5 | Full team active |
| Jan 13 - Feb 23 | 4-5 | 5 | Typical range |
| Feb 24 - Mar 9 | 4 | 5 | One reviewer less active |
| Mar 10-23 | 3 | 5 | Two reviewers less active |
| Mar 24 - Apr 5 | 3 | 5 | **Only 3 of 5 reviewers active in past 2 weeks** |

**Notable:** The decline from 5 to 3 active reviewers is concerning. Combined with increasing volume, this explains the turnaround time degradation. Possible causes: reviewer burnout, tool friction (see Issues #7, #14, #22), or staffing changes not reflected in the system.
