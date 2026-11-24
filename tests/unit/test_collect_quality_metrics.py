"""Testes de comportamento externo do coletor ISO 25010/ISO 5055 (issue #65).

A suíte executa o CLI por subprocesso sobre saídas sintéticas gravadas em
``tmp_path``. Nenhuma ferramenta real é necessária e nenhum valor ausente é
inventado pelo coletor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = REPO_ROOT / "scripts" / "collect_quality_metrics.py"

DEFAULT_REPORTS: dict[str, str] = {
    "ruff.txt": "",
    "mypy.txt": "Success: no issues found in 30 source files\n",
    "radon_cc.txt": "src/core/solvers/optw.py:1:0 -> solve (8)\n",
    "radon_mi.txt": "src/core/solvers/optw.py - C (7.79)\n",
    "radon_raw.txt": (
        "src/core/solvers/optw.py\n"
        "    LOC: 100\n"
        "    LLOC: 60\n"
        "    SLOC: 80\n"
        "    Comments: 5\n"
        "    Single comments: 4\n"
        "    Multi: 0\n"
        "    Blank: 15\n"
    ),
    "pytest.txt": "TOTAL 3200 800 75%\n",
    "import_linter.txt": "Contracts: 2 kept, 0 broken.\n",
    "bandit.txt": "No issues identified.\n",
    "pip_audit.txt": "No known vulnerabilities found\n",
    "vulture.txt": "",
}


def _reports_dir(tmp_path: Path, overrides: dict[str, str] | None = None) -> Path:
    """Gravar saídas sintéticas das ferramentas em um diretório isolado."""
    reports = tmp_path / "tool-output"
    reports.mkdir(parents=True, exist_ok=True)
    content = dict(DEFAULT_REPORTS)
    if overrides:
        content.update(overrides)
    for name, text in content.items():
        (reports / name).write_text(text, encoding="utf-8")
    return reports


def _run_collector(
    tmp_path: Path,
    reports: Path,
    *extra_args: str,
    as_module: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Executar o coletor como script ou módulo e devolver os caminhos gerados."""
    json_path = tmp_path / "reports" / "quality-metrics.json"
    markdown_path = tmp_path / "reports" / "quality-metrics.md"
    command = [sys.executable]
    if as_module:
        command.extend(["-m", "scripts.collect_quality_metrics"])
    else:
        command.append(str(COLLECTOR))
    command.extend(
        [
            "--root",
            str(REPO_ROOT),
            "--reports-dir",
            str(reports),
            "--json-output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
            *extra_args,
        ]
    )
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    return result, json_path, markdown_path


def test_coletor_gera_json_e_markdown_com_mutacao_nao_executada(tmp_path: Path) -> None:
    """O modo rápido produz relatórios estruturados sem inventar mutation score."""
    reports = _reports_dir(tmp_path)

    result, json_path, markdown_path = _run_collector(tmp_path, reports)

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["mode"] == "fast"
    iso_25010 = report["standards"]["iso_25010"]
    iso_5055 = report["standards"]["iso_5055"]

    assert iso_25010["adequacao_funcional"]["cobertura_percentual"]["value"] == 75.0
    assert iso_25010["confiabilidade"]["mutacao"] == {
        "status": "not run",
        "score_percent": None,
    }
    assert iso_25010["seguranca"]["achados_bandit"]["value"] == 0
    assert iso_25010["manutencionabilidade"]["violacoes_contrato_arquitetural"]["value"] == 0
    assert iso_5055["complexidade_ciclomatica"]["maxima"]["value"] == 8
    assert iso_5055["complexidade_ciclomatica"]["limite"] == 9
    assert iso_5055["indice_de_manutencionabilidade"]["value"]["min"] == 7.79

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "ISO/IEC 25010" in markdown
    assert "ISO/IEC 5055" in markdown
    assert "não executado" in markdown


def test_coletor_nao_duplica_volume_bruto_do_bloco_total(tmp_path: Path) -> None:
    """O bloco `** Total **` do radon raw não pode ser somado duas vezes."""
    raw_report = (
        "src/a.py\n"
        "    LOC: 10\n"
        "    LLOC: 6\n"
        "    SLOC: 8\n"
        "    Comments: 1\n"
        "    Single comments: 1\n"
        "    Multi: 0\n"
        "    Blank: 2\n"
        "** Total **\n"
        "    LOC: 10\n"
        "    LLOC: 6\n"
        "    SLOC: 8\n"
        "    Comments: 1\n"
        "    Single comments: 1\n"
        "    Multi: 0\n"
        "    Blank: 2\n"
    )
    reports = _reports_dir(tmp_path, {"radon_raw.txt": raw_report})

    result, json_path, _ = _run_collector(tmp_path, reports)

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(json_path.read_text(encoding="utf-8"))
    raw = report["standards"]["iso_5055"]["volume_bruto"]["value"]
    assert raw["loc"] == 10
    assert raw["sloc"] == 8


def test_coletor_funciona_como_modulo_e_registra_mutacao_medida(tmp_path: Path) -> None:
    """O modo ``--full`` lê o JSON do mutmut e calcula o score sem impor meta."""
    reports = _reports_dir(tmp_path)
    (reports / "mutmut.json").write_text(
        json.dumps({"killed": 6, "survived": 1, "timeout": 1, "skipped": 2, "total": 10}),
        encoding="utf-8",
    )

    result, json_path, _ = _run_collector(tmp_path, reports, "--full", as_module=True)

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["mode"] == "full"
    mutation = report["standards"]["iso_25010"]["confiabilidade"]["mutacao"]
    assert mutation["status"] == "measured"
    assert mutation["score_percent"] == 87.5
    assert mutation["tested"] == 8
    assert "threshold" not in mutation


def test_coletor_marca_metricas_ausentes_como_indisponiveis(tmp_path: Path) -> None:
    """Sem saídas de ferramentas, o relatório registra ausência em vez de zero."""
    reports = tmp_path / "vazio"
    reports.mkdir()

    result, json_path, markdown_path = _run_collector(tmp_path, reports)

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(json_path.read_text(encoding="utf-8"))
    iso_25010 = report["standards"]["iso_25010"]
    coverage = iso_25010["adequacao_funcional"]["cobertura_percentual"]
    assert coverage == {"value": None, "status": "unavailable"}
    assert iso_25010["confiabilidade"]["erros_de_tipagem"]["status"] == "unavailable"
    assert iso_25010["seguranca"]["achados_bandit"]["status"] == "unavailable"
    assert iso_25010["seguranca"]["vulnerabilidades_de_dependencias"]["status"] == "unavailable"
    assert iso_25010["manutencionabilidade"]["violacoes_ruff"]["status"] == "unavailable"
    assert iso_25010["manutencionabilidade"]["itens_de_codigo_morto"]["status"] == "unavailable"
    assert iso_25010["manutencionabilidade"]["volume_bruto"]["status"] == "unavailable"
    assert report["tools"]["mutmut"]["available"] is False
    assert "não disponível" in markdown_path.read_text(encoding="utf-8")


def test_coletor_check_imprime_resumo_unificado(tmp_path: Path) -> None:
    """``--check`` consome o mesmo relatório e mostra o inventário AST."""
    reports = _reports_dir(tmp_path, {"pytest.txt": "TOTAL 3200 800 95%\n"})

    result, json_path, _ = _run_collector(tmp_path, reports, "--check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "==> Consolidated quality summary" in result.stdout
    assert "Coverage:                  95.0 (minimum 85%)" in result.stdout
    assert "Max syntactic complexity:" in result.stdout
    assert "Structural inventory:" in result.stdout
    assert "Mutation (src/core):       não executado" in result.stdout
    report = json.loads(json_path.read_text(encoding="utf-8"))
    inventory = report["standards"]["iso_5055"]["inventario_estrutural"]["value"]
    assert inventory["core"]["modules"] > 0
    assert inventory["adapters"]["modules"] > 0
    assert inventory["total"]["complexity_distribution"]["10+"] == 0


def test_coletor_check_falha_com_violacao_de_limiar(tmp_path: Path) -> None:
    """Um limiar violado gera diagnóstico único e código de saída 1."""
    reports = _reports_dir(tmp_path)

    result, _, _ = _run_collector(tmp_path, reports, "--check")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "VIOLATION: cobertura 75.0% abaixo do mínimo 85%" in result.stderr
    assert "==> Consolidated quality summary" in result.stdout
