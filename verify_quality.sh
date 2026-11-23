#!/usr/bin/env bash
# Quality gate for Kairos (issues #25, #26 and #86).
# Default: ruff -> mypy --strict -> numeric radon CC (< 10) -> pytest with coverage >= 85%
#          -> RF x test traceability -> matrix --check -> docs-as-code.
# --full: same fast gate + mutmut mutation testing restricted to src/core + consolidated summary.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash ./verify_quality.sh [--full]

  (no args)  Fast gate: ruff, mypy --strict, radon CC < 10, pytest --cov >= 85,
             RF x test traceability, matrix --check and docs-as-code validators.
  --full     Fast gate, then mutmut mutation testing restricted to src/core,
             followed by a consolidated metrics summary.
EOF
}

full_mode=0
case "${1:-}" in
  "") full_mode=0 ;;
  --full) full_mode=1 ;;
  *)
    printf 'ERROR: invalid argument: %s\n' "$1" >&2
    usage >&2
    exit 2
    ;;
esac
if (( $# > 1 )); then
  printf 'ERROR: expected at most one argument, got %d\n' "$#" >&2
  usage >&2
  exit 2
fi

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

coverage="n/a"
max_complexity="n/a"
typing_errors=0
traceability_status="not run"
matrix_status="not run"
docs_as_code_status="not run"
mutation_stats=""

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf 'python3\n'
  else
    printf 'python\n'
  fi
}

run_fast_gate() {
  local python_bin
  python_bin="$(resolve_python)"

  echo "==> [1/7] ruff check src tests"
  ruff check src tests

  echo "==> [2/7] mypy --strict src"
  mypy --strict src
  # mypy aborts the gate on any typing error, so reaching this point means zero errors.
  typing_errors=0

  echo "==> [3/7] radon cc -s src (numeric cyclomatic complexity must be < 10)"
  radon_output="$(radon cc -s src)"
  printf '%s\n' "$radon_output"
  # Letter grades are not enough: radon's grade B covers 6-10, so a threshold on
  # the grade cannot reject exactly 10 while still allowing 9. Parse the numeric
  # score printed in parentheses by `radon cc -s` and compare it directly.
  if printf '%s\n' "$radon_output" | awk '
    match($0, /\([0-9]+\)/) {
      score = substr($0, RSTART + 1, RLENGTH - 2) + 0
      if (score >= 10) {
        print "  VIOLATION: " $0
        found = 1
      }
    }
    END { exit(found ? 1 : 0) }
  '; then
    echo "  complexity OK (all scores < 10)"
  else
    echo "  complexity FAILED: found cyclomatic complexity >= 10"
    exit 1
  fi
  max_complexity="$(printf '%s\n' "$radon_output" | awk '
    match($0, /\([0-9]+\)/) {
      score = substr($0, RSTART + 1, RLENGTH - 2) + 0
      if (score > max) max = score
    }
    END { print max + 0 }
  ')"

  echo "==> [4/7] pytest --cov=src --cov-report=term-missing --cov-fail-under=85"
  pytest --cov=src --cov-report=term-missing --cov-fail-under=85 2>&1 | tee "$work_dir/pytest.log"
  coverage="$(awk '
    /^TOTAL[[:space:]]/ { pct = $NF; gsub(/%/, "", pct); value = pct "%" }
    END { print (value == "" ? "n/a" : value) }
  ' "$work_dir/pytest.log")"

  echo "==> [5/7] validate_traceability.py (RF01-RF08 x testes)"
  "$python_bin" scripts/validate_traceability.py \
    --spec docs/especificacao-requisitos-funcionais.md \
    --root .
  traceability_status="OK"

  echo "==> [6/7] generate_traceability_matrix.py --check (matriz RF01-RF08)"
  "$python_bin" scripts/generate_traceability_matrix.py \
    --plan docs/testing/test-plan-29119.md \
    --spec docs/especificacao-requisitos-funcionais.md \
    --root . \
    --check
  matrix_status="OK"

  echo "==> [7/7] validate_docs_as_code.py (docs x artefatos)"
  "$python_bin" scripts/validate_docs_as_code.py \
    --plan docs/testing/test-plan-29119.md \
    --handoff docs/HANDOFF.md \
    --root .
  docs_as_code_status="OK"
}

run_mutation() {
  echo "==> [8/8] mutmut run (mutation testing restricted to src/core)"
  local mutmut_dir="$work_dir/mutmut"
  local python_bin
  python_bin="$(resolve_python)"

  mkdir -p "$mutmut_dir"
  cp -R src tests "$mutmut_dir/"
  if [[ -d scripts ]]; then
    cp -R scripts "$mutmut_dir/"
  fi
  if [[ -d docs ]]; then
    cp -R docs "$mutmut_dir/"
  fi
  cp pyproject.toml "$mutmut_dir/pyproject.toml"
  cp verify_quality.sh "$mutmut_dir/verify_quality.sh"
  if [[ -f README.md ]]; then
    cp README.md "$mutmut_dir/README.md"
  fi
  find "$mutmut_dir" -type d -name "__pycache__" -exec rm -rf {} +

  # mutmut 3.x reads [tool.mutmut] from pyproject.toml in the current directory.
  # Generate that config in an isolated workspace so the repository's pyproject.toml
  # is never touched.
  #
  # mutmut 3.x rejects trampolines whose runtime __module__ starts with `src.`
  # (record_trampoline_hit asserts `not name.startswith("src.")`), and its
  # also_copy step dereferences symlinks into unmutated copies. In the isolated
  # workspace, promote `core` and `adapters` to top-level packages and rewrite
  # `from src.` / `import src.` imports to match, while preserving non-Python
  # template assets under `src/adapters/web/templates` for contract tests.
  mv "$mutmut_dir/src/core" "$mutmut_dir/core"
  mv "$mutmut_dir/src/adapters" "$mutmut_dir/adapters"
  rm -rf "$mutmut_dir/src"
  if [[ -d "$mutmut_dir/adapters/web/templates" ]]; then
    mkdir -p "$mutmut_dir/src/adapters/web"
    cp -R "$mutmut_dir/adapters/web/templates" "$mutmut_dir/src/adapters/web/templates"
  fi

  "$python_bin" - "$mutmut_dir" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
import_re = re.compile(r"^([ \t]*(?:from|import)[ \t]+)src\.", re.MULTILINE)
for folder in ("core", "adapters", "tests"):
    for py_file in (root / folder).rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        updated = import_re.sub(r"\1", text)
        if updated != text:
            py_file.write_text(updated, encoding="utf-8")
PY

  printf '\n[tool.mutmut]\nsource_paths = ["core"]\nalso_copy = ["src", "adapters", "tests", "docs", "scripts", "verify_quality.sh"]\n' >> "$mutmut_dir/pyproject.toml"

  (
    cd "$mutmut_dir"
    # Apenas a execução do mutmut usa o perfil sem prazo do Hypothesis; o gate
    # rápido e as execuções locais preservam os prazos padrão.
    KAIROS_MUTATION=1 mutmut run
    mutmut export-cicd-stats
  )
  mutation_stats="$mutmut_dir/mutants/mutmut-cicd-stats.json"
}

print_summary() {
  local python_bin
  python_bin="$(resolve_python)"

  "$python_bin" - \
    "$coverage" "$max_complexity" "$typing_errors" \
    "$traceability_status" "$matrix_status" "$docs_as_code_status" \
    "$mutation_stats" <<'PY'
import json
import sys

(
    coverage,
    complexity,
    typing_errors,
    traceability,
    matrix,
    docs_as_code,
    stats_path,
) = sys.argv[1:]
print("==> Consolidated quality summary")
print(f"  Coverage:                  {coverage} (minimum 85%)")
print(f"  Max cyclomatic complexity: {complexity} (limit < 10)")
print(f"  Typing errors:             {typing_errors}")
print(f"  RF x test traceability:    {traceability}")
print(f"  Traceability matrix:       {matrix}")
print(f"  Docs-as-code:              {docs_as_code}")
if not stats_path:
    print("  Mutation (src/core):       not run")
else:
    with open(stats_path) as f:
        stats = json.load(f)
    killed = int(stats.get("killed", 0))
    survived = int(stats.get("survived", 0))
    timeout = int(stats.get("timeout", 0))
    tested = int(stats.get("total", 0)) - int(stats.get("skipped", 0))
    score = 0.0 if tested <= 0 else (killed + timeout) / tested * 100
    print(f"  Mutants killed:            {killed}")
    print(f"  Mutants survived:          {survived}")
    print(f"  Mutants timeout:           {timeout}")
    print(f"  Mutation score (src/core): {score:.1f}% ({killed + timeout}/{tested} tested)")
PY
}

run_fast_gate

if (( full_mode )); then
  run_mutation
fi

echo "==> Quality gate PASSED"

if (( full_mode )); then
  print_summary
fi
