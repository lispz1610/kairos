#!/usr/bin/env bash
# Fast, deterministic quality gate for Kairos (issue #25).
# Stages: ruff -> mypy --strict -> numeric radon CC (< 10) -> pytest with coverage >= 85%.
set -euo pipefail

echo "==> [1/4] ruff check src tests"
ruff check src tests

echo "==> [2/4] mypy --strict src"
mypy --strict src

echo "==> [3/4] radon cc -s src (numeric cyclomatic complexity must be < 10)"
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

echo "==> [4/4] pytest --cov=src --cov-report=term-missing --cov-fail-under=85"
pytest --cov=src --cov-report=term-missing --cov-fail-under=85

echo "==> Quality gate PASSED"
