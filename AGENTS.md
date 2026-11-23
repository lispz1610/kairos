# AGENTS.md

## Agent skills

### Issue tracker

GitHub Issues using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Standard 5-label triage vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (`GLOSSARY.md` and `docs/adr/` at the repo root). See `docs/agents/domain.md`.

## Quality gate

Run `./verify_quality.sh` before every commit or PR. The change is not ready until the gate passes. The fast gate also runs the RF × test traceability validator, the traceability matrix `--check` and the docs-as-code validator; any failure blocks the gate.

Run `./verify_quality.sh --full` when the change touches `src/core/`; it adds the mutation-testing stage on top of the fast checks.

The fast gate works on Linux, macOS, and Windows via Git Bash. The `--full` gate requires WSL2 or Linux/macOS because mutmut refuses to run on native Windows. On Windows without WSL, run the fast gate locally and run `--full` in WSL or on Linux/macOS.

Respect `GLOSSARY.md` and `docs/adr/` per `docs/agents/domain.md`: read the relevant documentation before exploring or changing code, and use the glossary's vocabulary. Also respect ISO 5055, ISO 25010 and ISO/IEC/IEEE 29119 before every commit or PR.

On Windows, run the gate in Git Bash (`bash ./verify_quality.sh`) and ensure Python 3.12's Scripts directory is on `PATH` so the gate's tools are found.
