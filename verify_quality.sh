#!/usr/bin/env bash
# Quality gate for Kairos (issues #25, #26, #64, #65 and #86).
# Default: ruff -> mypy --strict -> radon CC (< 10) -> pytest --cov >= 85
#          -> traceability -> docs-as-code -> import-linter -> bandit -> vulture
#          -> radon mi/raw -> pip-audit (advisory) -> ISO 25010/5055 collector.
# --full: same fast gate + mutmut mutation testing restricted to src/core, with the
#         mutation score included in the consolidated JSON/Markdown report.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash ./verify_quality.sh [--full]

  (no args)  Fast gate: ruff, mypy --strict, radon CC < 10, pytest --cov >= 85,
             traceability, docs-as-code, import-linter, bandit, vulture,
             radon mi/raw, advisory pip-audit and ISO 25010/5055 report.
  --full     Fast gate, then mutmut mutation testing restricted to src/core and
             a final collector run that records the measured mutation score.
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
architecture_status="not run"
security_status="not run"
dead_code_status="not run"
pip_audit_status="not run"
mutation_stats=""

resolve_python() {
  # Prefira `python`: em ambientes Windows o alias `python3` pode apontar para
  # o stub da Microsoft Store mesmo quando um virtualenv real está no PATH.
  if command -v python >/dev/null 2>&1; then
    printf 'python\n'
  else
    printf 'python3\n'
  fi
}

run_fast_gate() {
  local python_bin
  python_bin="$(resolve_python)"

  echo "==> [1/12] ruff check src tests"
  ruff check src tests 2>&1 | tee "$work_dir/ruff.txt"

  echo "==> [2/12] mypy --strict src"
  mypy --strict src 2>&1 | tee "$work_dir/mypy.txt"
  # mypy aborts the gate on any typing error, so reaching this point means zero errors.
  typing_errors=0

  echo "==> [3/12] radon cc -s src (numeric cyclomatic complexity must be < 10)"
  radon_output="$(radon cc -s src)"
  printf '%s\n' "$radon_output" | tee "$work_dir/radon_cc.txt"
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

  echo "==> [4/12] pytest --cov=src --cov-report=term-missing --cov-fail-under=85"
  pytest --cov=src --cov-report=term-missing --cov-fail-under=85 2>&1 | tee "$work_dir/pytest.txt"
  cp "$work_dir/pytest.txt" "$work_dir/pytest.log"
  coverage="$(awk '
    /^TOTAL[[:space:]]/ { pct = $NF; gsub(/%/, "", pct); value = pct "%" }
    END { print (value == "" ? "n/a" : value) }
  ' "$work_dir/pytest.log")"

  echo "==> [5/12] validate_traceability.py (RF01-RF08 x testes)"
  "$python_bin" scripts/validate_traceability.py \
    --spec docs/especificacao-requisitos-funcionais.md \
    --root .
  traceability_status="OK"

  echo "==> [6/12] generate_traceability_matrix.py --check (matriz RF01-RF08)"
  "$python_bin" scripts/generate_traceability_matrix.py \
    --plan docs/testing/test-plan-29119.md \
    --spec docs/especificacao-requisitos-funcionais.md \
    --root . \
    --check
  matrix_status="OK"

  echo "==> [7/12] validate_docs_as_code.py (docs x artefatos)"
  "$python_bin" scripts/validate_docs_as_code.py \
    --plan docs/testing/test-plan-29119.md \
    --handoff docs/HANDOFF.md \
    --root .
  docs_as_code_status="OK"

  echo "==> [8/12] lint-imports (contratos hexagonais ARQ-1 e ARQ-2)"
  lint-imports 2>&1 | tee "$work_dir/import_linter.txt"
  architecture_status="OK"

  # B104 é ignorado: o literal 0.0.0.0 em safe_fetcher.py pertence a uma denylist
  # anti-SSRF, não a um bind em todas as interfaces.
  echo "==> [9/12] bandit -q -r src -ll (B104 excluído: denylist anti-SSRF)"
  bandit -q -r src -ll -s B104 2>&1 | tee "$work_dir/bandit.txt"
  security_status="OK"

  # Vulture é informativo: nomes exigidos por assinaturas de portas podem ser
  # reportados como não usados sem representar código morto real.
  echo "==> [10/12] vulture (code smell informativo)"
  vulture 2>&1 | tee "$work_dir/vulture.txt" || true
  dead_code_status="REPORTED"

  echo "==> [11/12] radon mi -s src / radon raw -s src"
  radon mi -s src 2>&1 | tee "$work_dir/radon_mi.txt"
  radon raw -s src 2>&1 | tee "$work_dir/radon_raw.txt"

  # pip-audit depende de rede/índice de vulnerabilidades. Em runner self-hosted
  # isolado ele pode falhar por indisponibilidade: a política é aviso, não bloqueio.
  echo "==> [12/12] pip-audit (política de aviso; não bloqueia o gate)"
  if pip-audit -l --progress-spinner off --desc off --aliases off 2>&1 | tee "$work_dir/pip_audit.txt"; then
    pip_audit_status="OK"
  else
    pip_audit_status="WARNING"
    echo "  pip-audit: falha de auditoria registrada como aviso (política documentada)."
  fi
}

run_mutation() {
  echo "==> [13/14] mutmut run (mutation testing restricted to src/core)"
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
  mutation_stats="$work_dir/mutmut.json"
  cp "$mutmut_dir/mutants/mutmut-cicd-stats.json" "$mutation_stats"
}

print_summary() {
  local python_bin
  python_bin="$(resolve_python)"

  "$python_bin" - \
    "$coverage" "$max_complexity" "$typing_errors" \
    "$traceability_status" "$matrix_status" "$docs_as_code_status" \
    "$architecture_status" "$security_status" "$dead_code_status" "$pip_audit_status" \
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
    architecture,
    security,
    dead_code,
    pip_audit,
    stats_path,
) = sys.argv[1:]
print("==> Consolidated quality summary")
print(f"  Coverage:                  {coverage} (minimum 85%)")
print(f"  Max cyclomatic complexity: {complexity} (limit < 10)")
print(f"  Typing errors:             {typing_errors}")
print(f"  RF x test traceability:    {traceability}")
print(f"  Traceability matrix:       {matrix}")
print(f"  Docs-as-code:              {docs_as_code}")
print(f"  Contratos arquiteturais:   {architecture}")
print(f"  Segurança estática:        {security}")
print(f"  Código morto (vulture):    {dead_code}")
print(f"  Auditoria de deps.:        {pip_audit}")
print("  Relatório ISO:             reports/quality-metrics.json / .md")
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

collector_label="[13/13]"
if (( full_mode )); then
  collector_label="[14/14]"
fi
python_bin="$(resolve_python)"
collector_args=(
  --root .
  --reports-dir "$work_dir"
  --json-output reports/quality-metrics.json
  --markdown-output reports/quality-metrics.md
)
if (( full_mode )); then
  collector_args+=(--full)
fi
echo "==> $collector_label collect_quality_metrics.py (ISO 25010 / ISO 5055)"
"$python_bin" scripts/collect_quality_metrics.py "${collector_args[@]}"

echo "==> Quality gate PASSED"

if (( full_mode )); then
  print_summary
fi
