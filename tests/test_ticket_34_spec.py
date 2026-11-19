"""Testes de contrato de #34: Conexão Interurbana com Departure Datetime e Margem de Embarque.

O repositório Kairos é docs-only (sem ``src/``): os modelos ``InterCityConnection`` e
``ScheduleService`` de #34 residem nas especificações funcionais, conforme as decisões
arquiteturais do parent #18. Estes testes verificam os contratos de #34 contra os
documentos que os definem, no formato ISO/IEC/IEEE 29119:

- AC 1: ``InterCityConnection`` define ``departure_datetime: datetime`` obrigatório.
- AC 2: ``boarding_cutoff_minutes`` exibe o padrão por modal: ``flying`` → 120,
  ``driving``/``transit`` → 30.
- AC 3: ``ScheduleService`` valida o Roteiro contra os Horários de Funcionamento e a
  Janela de Disponibilidade, reportando desvios.
- AC 4: testes unitários cobrindo: padrão do modal, visita fora do horário de
  funcionamento (desvio reportado), Janela de Disponibilidade violada (desvio reportado).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = (REPO_ROOT / "docs" / "especificacao-requisitos-funcionais.md").read_text(encoding="utf-8")


def test_ac1_define_intercityconnection_departure_datetime_obrigatorio():
    assert "InterCityConnection" in SPEC
    assert "departure_datetime: datetime" in SPEC
    assert "obrigatório" in SPEC


def test_ac2_defina_boarding_cutoff_minutes_com_padroes_por_modal():
    line = re.search(r"boarding_cutoff_minutes[^\n]*", SPEC).group(0)
    assert "120" in line
    assert "flying" in line
    assert "30" in line
    assert "driving" in line
    assert "transit" in line


def test_ac3_define_schedule_service_valida_roteiro_vs_horarios_de_funcionamento():
    assert "ScheduleService" in SPEC
    assert "Horários de Funcionamento" in SPEC
    assert "Janela de Disponibilidade" in SPEC
    assert "Roteiro" in SPEC


def test_ac3_define_schedule_service_reporta_desvios():
    assert "reportando desvios" in SPEC


def test_ac4_inclua_casos_de_teste_padrao_do_modal():
    assert "Padrão do modal" in SPEC


def test_ac4_inclua_casos_de_teste_visita_fora_do_horario_de_funcionamento():
    assert "Visita fora do horário de funcionamento" in SPEC
    assert "desvio reportado" in SPEC


def test_ac4_inclua_casos_de_teste_janela_de_disponibilidade_violada():
    assert "Janela de Disponibilidade violada" in SPEC
    assert "desvio reportado" in SPEC
