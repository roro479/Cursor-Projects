# Slack Thread Excerpts

The following are excerpts from internal Slack channels relevant to the Auth Review Assistant product.

---

## Thread 1: #eng-auth-review — March 20, 2026

**Alex Chen** 9:14 AM
Seeing the API pod memory climb again. Currently at 98Mi, limit is 128Mi. It'll OOM in about 6 hours at this rate.

**Jordan Rivera** 9:22 AM
Can you just bump the limit? We're already at 128Mi though...

**Alex Chen** 9:25 AM
That's the thing — 128Mi is already the limit. I think there's a real leak somewhere. The connection pool shouldn't grow like this. We need to profile it but I haven't had time.

**Jordan Rivera** 9:31 AM
I can bump the limit to 256Mi as a stopgap. But we should actually investigate.

**Alex Chen** 9:33 AM
Yeah. Filed Issue #10. I'll try to get to it next week.

*No further messages in thread.*

---

## Thread 2: #eng-auth-review — March 27, 2026

**Sarah Kim** 2:45 PM
Hey does anyone know why the pipeline CI workflow is disabled? I just pushed a change to the Python code and realized there are no tests running. File is `.github/workflows/pipeline-test.yaml.disabled`

**Jordan Rivera** 2:52 PM
Oh yeah — the OCR mock was flaking so I disabled it back in December. Was supposed to be temporary.

**Sarah Kim** 2:55 PM
That was 4 months ago... so we've had zero CI coverage on the entire Python pipeline this whole time?

**Jordan Rivera** 3:01 PM
😬 yeah. The mock needs to be rewritten, it was hitting a real endpoint in tests. I can look at it but I'm pretty swamped with the Helm migration.

*No further messages in thread.*

---

## Thread 3: #clinical-ops — April 1, 2026

**Maria Torres** 8:30 AM
Quick question for the team — is there a way to see pending requests sorted by urgency? Right now everything comes in the order it was received. I have urgent surgical pre-auths sitting behind routine lab work.

**James Park** 8:45 AM
I've been asking about this for months. The queue is just FIFO right now. I end up scrolling through everything to find the urgent ones.

**Aisha Williams** 8:47 AM
👆 same. I waste 10-15 minutes every morning just finding the urgent cases.

**Maria Torres** 9:02 AM
Is there an engineering contact for this? I don't know who to ask since Dana left.

*No further messages in thread.*

---

## Thread 4: #eng-auth-review — April 3, 2026

**Alex Chen** 7:15 AM
Heads up — the CDC ingestor processed 3 duplicate events last night. Same auth request ID, same payload, ~30 seconds apart. The upsert handles it fine (no data corruption) but it's unnecessary load.

**Jordan Rivera** 7:28 AM
Could be a consumer group rebalance. When a partition gets reassigned, the new consumer might re-process events that were already committed but not yet checkpointed. I'll check the Kafka consumer lag metrics.

**Alex Chen** 7:32 AM
Makes sense. It's been happening about once a week. Not urgent since the upsert is idempotent, but we should understand why.

**Jordan Rivera** 7:40 AM
I'll take a look at the offset commit interval. Currently set to auto-commit which is the default — we might want manual commits after successful processing.

---

## Thread 5: #leadership — March 28, 2026

**VP Clinical Ops** 3:15 PM
Team — what's the status of the auto-approve feature for routine procedure codes? This was on the Q1 roadmap and we're past the deadline. Our reviewers are spending hours approving basic lab work that should be automatic. This is directly impacting our turnaround times.

*No responses in thread.*

*Note: Alex Chen opened Draft PR #53 (auto-approve) on April 3, one week after this message, without product criteria or stakeholder input.*
