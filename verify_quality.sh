#!/usr/bin/env bash
# Quality gate for Kairos (issues #25, #26, #64, #65, #86 and #106).
# Default: ruff -> mypy --strict -> radon CC -> pytest --cov >= 85
#          -> traceability -> docs-as-code -> import-linter -> bandit -> vulture
#          -> radon mi/raw -> pip-audit (advisory) -> collector --check.
# --full: same fast gate + mutmut mutation testing restricted to src/core, with the
#         mutation score included in the consolidated JSON/Markdown report.
# Thresholds and the console summary come from the collector's unified API; this
# script only orchestrates tools and preserves their output artifacts.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash ./verify_quality.sh [--full]

  (no args)  Fast gate: ruff, mypy --strict, radon CC, pytest --cov >= 85,
             traceability, docs-as-code, import-linter, bandit, vulture,
             radon mi/raw, advisory pip-audit and collector --check with the
             consolidated ISO 25010/5055 report, AST inventory and thresholds.
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

  # A saída é preservada como artefato; o limiar sintático é avaliado pelo
  # coletor sobre o inventário AST, sem parser duplicado neste script.
  echo "==> [3/12] radon cc -s src (artifact; AST limit checked by collector)"
  radon cc -s src 2>&1 | tee "$work_dir/radon_cc.txt"

  echo "==> [4/12] pytest --cov=src --cov-report=term-missing --cov-fail-under=85"
  pytest --cov=src --cov-report=term-missing --cov-fail-under=85 2>&1 | tee "$work_dir/pytest.txt"

  echo "==> [5/12] validate_traceability.py (RF01-RF08 x testes)"
  "$python_bin" scripts/validate_traceability.py \
    --spec docs/especificacao-requisitos-funcionais.md \
    --root .

  echo "==> [6/12] generate_traceability_matrix.py --check (matriz RF01-RF08)"
  "$python_bin" scripts/generate_traceability_matrix.py \
    --plan docs/testing/test-plan-29119.md \
    --spec docs/especificacao-requisitos-funcionais.md \
    --root . \
    --check

  echo "==> [7/12] validate_docs_as_code.py (docs x artefatos)"
  "$python_bin" scripts/validate_docs_as_code.py \
    --plan docs/testing/test-plan-29119.md \
    --handoff docs/HANDOFF.md \
    --root .

  echo "==> [8/12] lint-imports (contratos hexagonais ARQ-1 e ARQ-2)"
  lint-imports 2>&1 | tee "$work_dir/import_linter.txt"

  # B104 é ignorado: o literal 0.0.0.0 em safe_fetcher.py pertence a uma denylist
  # anti-SSRF, não a um bind em todas as interfaces.
  echo "==> [9/12] bandit -q -r src -ll (B104 excluído: denylist anti-SSRF)"
  bandit -q -r src -ll -s B104 2>&1 | tee "$work_dir/bandit.txt"

  # Vulture é informativo: nomes exigidos por assinaturas de portas podem ser
  # reportados como não usados sem representar código morto real.
  echo "==> [10/12] vulture (code smell informativo)"
  vulture 2>&1 | tee "$work_dir/vulture.txt" || true

  echo "==> [11/12] radon mi -s src / radon raw -s src"
  radon mi -s src 2>&1 | tee "$work_dir/radon_mi.txt"
  radon raw -s src 2>&1 | tee "$work_dir/radon_raw.txt"

  # pip-audit depende de rede/índice de vulnerabilidades. Em runner self-hosted
  # isolado ele pode falhar por indisponibilidade: a política é aviso, não bloqueio.
  echo "==> [12/12] pip-audit (política de aviso; não bloqueia o gate)"
  if pip-audit -l --progress-spinner off --desc off --aliases off 2>&1 | tee "$work_dir/pip_audit.txt"; then
    :
  else
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
  # workspace, copy `core` and `adapters` as top-level packages and rewrite
  # `from src.` / `import src.` imports in `core`, `adapters`, and `tests`,
  # while preserving `src/` so template assets and AST inventory tests pass.
  cp -R "$mutmut_dir/src/core" "$mutmut_dir/core"
  cp -R "$mutmut_dir/src/adapters" "$mutmut_dir/adapters"

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
  cp "$mutmut_dir/mutants/mutmut-cicd-stats.json" "$work_dir/mutmut.json"
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
echo "==> $collector_label collect_quality_metrics.py --check (ISO 25010 / ISO 5055)"
"$python_bin" scripts/collect_quality_metrics.py "${collector_args[@]}" --check

echo "==> Quality gate PASSED"
