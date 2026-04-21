## Prototype: Hybrid Confidence Gate + System Audit

### Files

- **`confidence_gate.py`** (primary submission): PR #53 CPT gate + `--dashboard` / `--audit` (system health + top risks, loads `system_state_cli.py`).
- **`system_state_cli.py`**: full four-section audit (optional; used by `--dashboard`).

### What `system_state_cli.py` prints

Four sections:
- **SYSTEM HEALTH**
- **TOP RISKS**
- **ACTION PLAN (prioritized)**
- **WHAT'S BLOCKED PENDING PM DECISION**

### How to run

**Hybrid (recommended demo):**

```bash
python cursor-output/prototype/confidence_gate.py --dashboard
python cursor-output/prototype/confidence_gate.py --input repo/tests/fixtures/sample_auth_request.json
python cursor-output/prototype/confidence_gate.py --test
```

**Full audit only:**

```bash
python cursor-output/prototype/system_state_cli.py
```

Optional (for formatting): install `rich`.

```bash
pip install rich
```

### Notes

- The script reads markdown artifacts under `artifacts/` and a small set of repo files under `repo/` to anchor claims to verifiable evidence.
- See `DEMO.md` for the exact talk track and how the output maps to slides 3–4.

