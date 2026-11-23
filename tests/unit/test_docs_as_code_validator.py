"""Testes de CLI do validador docs-as-code da issue #84.

Cada cenário usa ``tmp_path`` para fornecer documentos e uma árvore de código
isolados, verificando códigos de saída e mensagens diagnósticas sem rede.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_docs_as_code.py"


def _write(path: Path, text: str) -> None:
    """Gravar um arquivo de texto criando os diretórios intermediários."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(plan: Path, handoff: Path, root: Path) -> subprocess.CompletedProcess[str]:
    """Executar a CLI do validador com documentos e raiz de código explícitos."""
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--plan",
            str(plan),
            "--handoff",
            str(handoff),
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )


def _create_artifacts(root: Path) -> None:
    """Criar a árvore de código que materializa os componentes verificáveis."""
    _write(root / "src/core/domain/events.py", "class DelayEvent:\n    pass\n")
    _write(root / "src/adapters/web/contingency.py", "def apply_contingency_event():\n    pass\n")
    _write(root / "src/core/services/replanning.py", "class ReplanningService:\n    pass\n")
    _write(root / "src/adapters/web/app.py", '@app.post("/api/trip/replan")\n')
    for test_file in (
        "tests/unit/test_events.py",
        "tests/unit/test_apply_contingency_event.py",
        "tests/unit/test_replanning_service.py",
        "tests/integration/test_trip_replan_endpoint.py",
    ):
        _write(root / test_file, "def test_componente():\n    pass\n")
    _write(root / "verify_quality.sh", "pytest --cov=src\n")


def test_documentos_coerentes_com_lacuna_parcial_de_navegador_passam(tmp_path: Path) -> None:
    """Lacunas parciais de navegador não devem gerar contradição."""
    plan = tmp_path / "test-plan.md"
    _write(
        plan,
        """## 8. Lacunas conhecidas

1. **Backup/restauração JSON no navegador (RF08)**: não há testes de navegador
   para os botões; sem testes de navegador nesta versão.
2. **Modal de Confirmação (RF06)**: os endpoints são testados, mas o modal
   ainda não possui implementação nem teste.
3. **Componente inexistente**: ainda sem código e sem testes nesta versão.
""",
    )
    handoff = tmp_path / "HANDOFF.md"
    _write(
        handoff,
        """## 4. Estado Atual

Documentação versionada.

## 5. Próximos Passos Imediatos para o Próximo Agente

1. Configuração do Projeto Python.
""",
    )
    root = tmp_path / "code"
    root.mkdir()

    result = _run(plan, handoff, root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "nenhuma contradição encontrada" in result.stdout
    assert "contradição docs-as-code" not in result.stdout


def test_ausencia_total_com_artefatos_presentes_falha_com_diagnostico(tmp_path: Path) -> None:
    """Ausência total declarada e pendências com artefatos presentes falham."""
    plan = tmp_path / "test-plan.md"
    _write(
        plan,
        """## 8. Lacunas conhecidas

3. **Eventos de Contingência e Replanejamento (extensão dinâmica)**: ainda sem
   código e sem testes nesta versão.
""",
    )
    handoff = tmp_path / "HANDOFF.md"
    _write(
        handoff,
        """## 5. Próximos Passos Imediatos para o Próximo Agente

2. **Implementação do Domínio Puro (`src/core/domain/`) via TDD**:
   - `events.py`: Modelos dos 4 eventos de contingência.
   - Motor de contingência: recálculo a partir do ponto/horário corrente.
7. **Script de Automação de Qualidade**: `verify_quality.sh` executando `pytest`.
""",
    )
    root = tmp_path / "code"
    _create_artifacts(root)

    result = _run(plan, handoff, root)
    output = result.stdout + result.stderr

    assert result.returncode == 1, output
    assert "Evento de Contingência" in output
    assert "Replanejamento" in output
    assert "script de gate de qualidade" in output
    assert "src/core/domain/events.py" in output
    assert "verify_quality.sh" in output
    assert "contradição docs-as-code" in output


def test_validador_aponta_contradições_conhecidas_no_repositorio() -> None:
    """No estado atual do repositório, as três divergências conhecidas aparecem."""
    result = _run(
        REPO_ROOT / "docs/testing/test-plan-29119.md",
        REPO_ROOT / "docs/HANDOFF.md",
        REPO_ROOT,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 1, output
    assert "Evento de Contingência" in output
    assert "Replanejamento" in output
    assert "script de gate de qualidade" in output
    assert "verify_quality.sh" in output


def test_documento_ausente_retorna_codigo_de_uso(tmp_path: Path) -> None:
    """Documentos inexistentes são erros de entrada, não contradições."""
    handoff = tmp_path / "HANDOFF.md"
    _write(handoff, "## 5. Próximos Passos\n\nNada pendente.\n")
    root = tmp_path / "code"
    root.mkdir()

    result = _run(tmp_path / "inexistente.md", handoff, root)

    assert result.returncode == 2
    assert "documento não encontrado" in result.stderr
