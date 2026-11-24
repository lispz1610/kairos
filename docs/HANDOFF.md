# Handoff — Projeto Kairos (Traçador Dinâmico de Rotas Turísticas)

**Data**: 2026-11-07 (atualizado em 2026-11-22)  
**Repositório Remoto**: `git@github.com:lispz1610/kairos.git` (branch `main`)  
**Workspace Local**: `/home/agent/.gemini/antigravity-cli/scratch/kairos`  
**Disciplina**: DCC061 - Engenharia de Software (UFJF) — Prof. Fabrício Martins Mendonça  
**Status**: Sistema implementado e verificado. Concepção e design concluídos (Grilling + Domain Modeling, ADRs e Glossário versionados), com Eventos de Contingência, Replanejamento, gate de qualidade e rastreabilidade docs-as-code entregues; restam apenas lacunas parciais de interação em navegador real (ver §8 do Plano de Testes).

---

## 1. Contexto Acadêmico & Requisitos (DCC061)

O trabalho prático exige:
1. **Escolha de 2 temas da disciplina**: O grupo selecionou **Testes de Software** e **Qualidade de Software**.
2. **Entregáveis (40 pontos)**:
   - **Documento-texto (20 pts)**: Monografia (DOCX/PDF) abordando definição, histórico, importância, ferramentas, normas, profissões, certificações e impactos de IA em Testes e Qualidade.
   - **Código-fonte no Git (20 pts)**: Sistema que demonstre na prática a aplicação dos princípios dos temas escolhidos.
   - **Apresentação em sala**: 15 a 20 minutos com slides em PDF.

---

## 2. Decisões Arquiteturais e Fundamentação Técnica

Toda a concepção do sistema foi refinada através de *Grilling* e registrada em ADRs formais:

- **[GLOSSARY.md](../GLOSSARY.md)**: Vocabulário ubíquo do domínio (*Viagem*, *Etapa de Viagem*, *Conexão Interurbana*, *Ponto de Interesse*, *Roteiro*, *Janela de Disponibilidade*, *Janela de Funcionamento*, *Tempo de Permanência*, *Pontuação de Utilidade*, *Evento de Contingência*, *Replanejamento*).
- **[ADR 0001: Formulação como OPTW](./adr/0001-formulacao-algoritmica-optw.md)**: Modelagem como *Orienteering Problem with Time Windows* (seleção de subconjunto e sequenciamento com budget de tempo e horários de funcionamento) em vez de TSP. Heurística construtiva gulosa (utilidade/custo) + busca local (2-opt/swap).
- **[ADR 0002: Stack Backend Python com FastAPI e Interface Simples](./adr/0002-stack-backend-python-fastapi.md)**: Foco no backend em Python, eliminando sobrecarga de SPA (sem React). Interface leve em HTML/Jinja2 + Vanilla JS + Leaflet.
- **[ADR 0003: Integração Google Maps com Padrão Cache-Aside](./adr/0003-integracao-google-maps-com-cache.md)**: Consumo exclusivo das APIs Google Maps Platform (Places, Routes/Distance Matrix, Geocoding) com persistência de cache local em SQLite.
- **[ADR 0004: Viagens Multicidades e Decomposição em Etapas Urbanas](./adr/0004-arquitetura-viagens-multicidades.md)**: Suporte a projetos multicidades (ex: São Paulo a Lima conectados por `flying`). Otimização urbana isolada conectada por limites temporais de voo, com suporte a alerta e ajuste em cascata caso um atraso urbano ameace a conexão interurbana.
- **[ADR 0005: Isolamento de Credenciais e Modo Offline Replay](./adr/0005-modo-offline-replay-credenciais.md)**: Proteção de chave de API privada (.env ignorado). Se executado sem chave (por exemplo, pela banca avaliadora), o sistema entra automaticamente em modo Replay com fixtures locais em SQLite para cidades de demonstração.
- **[ADR 0006: Navegação em Duas Camadas: Mapa Macro Geodésico e Detalhe Urbano](./adr/0006-navegacao-macro-mapa-e-detalhe-urbano.md)**: Visão macro na home (mapa com cidades interligadas apenas por retas/arcos geodésicos sem curvas de trânsito) e visão micro ao clicar na cidade (duas colunas: timeline com gatilhos de contingência à esquerda e mapa Leaflet à direita).
- **[ADR 0007: Gestão de Hospedagens, Curadoria Enriquecida e Estado Client-Side](./adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md)**: Decomposição em Dias de Viagem, hospedagem dinâmica por dia, slots contextuais de refeição/café, curadoria híbrida com parser seguro de links, ripple shift de calendário com confirmação, persistência local e emissão de Markdown estruturado.
- **[Especificação de Requisitos Funcionais](./especificacao-requisitos-funcionais.md)**: Detalhamento formal dos requisitos RF01 a RF08 alinhados às normas ISO/IEC 25010 e 29119.

---

## 3. Diretrizes de Qualidade e Normas ISO

- **ISO/IEC 25010 (Qualidade de Produto)**:
  - *Adequação Funcional*: Validada por suíte de testes unitários e de integração (`pytest`).
  - *Confiabilidade & Tolerância a Falhas*: Validada por Property-Based Testing (`hypothesis`) provando matematicamente que o roteiro nunca viola janelas de funcionamento ou disponibilidade, e pelos 4 Eventos de Contingência entregues (atraso, fechamento prematuro, cancelamento de parada e ajuste de Tempo de Permanência), com Replanejamento do Roteiro restante coberto por testes unitários e de integração.
  - *Manutenibilidade & Testabilidade*: Arquitetura Hexagonal (Ports & Adapters) garantindo desacoplamento do core algorítmico contra I/O, com os contratos `ARQ-1` (camadas) e `ARQ-2` (núcleo sem I/O/web) validados automaticamente por `import-linter`.
  - *Segurança*: varredura estática com `bandit` e auditoria de dependências com `pip-audit` (política de aviso em ambiente `self-hosted` com conectividade restrita).
- **ISO/IEC/IEEE 29119 (Testes de Software)**:
  - Estruturação do plano de testes e especificação formal de casos de teste no relatório técnico.
- **ISO/IEC 5055 (Métricas de Código Automatizadas)**:
  - Cobertura de código `pytest-cov ≥ 85%`.
  - Complexidade ciclomática `< 10` por função (`radon`).
  - Tipagem estática rigorosa (`mypy --strict`).
  - Linting e formatação PEP 8 / PEP 257 (`ruff`), incluindo `C901` e as regras selecionadas `PLR0911`/`PLR0912`/`PLR0913`.
  - Índice de manutenibilidade e volume de código (`radon mi` / `radon raw`) e detecção de código morto (`vulture`).
  - Relatório consolidado `reports/quality-metrics.json` / `.md` gerado por `scripts/collect_quality_metrics.py`, agrupando evidências por característica da ISO/IEC 25010 e métricas da ISO/IEC 5055; o mutation score é registrado apenas quando medido (`--full`).

---

## 4. Estado Atual do Repositório

O repositório `lispz1610/kairos` contém a aplicação implementada e a suíte de verificação:
```
kairos/
├── .github/workflows/          # automação de CI
├── AGENTS.md
├── GLOSSARY.md
├── README.md
├── verify_quality.sh           # gate de qualidade (ruff, mypy, radon, pytest, segurança, contratos e coletor ISO)
├── docs/
│   ├── HANDOFF.md
│   ├── adr/                    # ADR 0001 a 0007
│   ├── especificacao-requisitos-funcionais.md
│   └── testing/test-plan-29119.md
├── scripts/
│   ├── quality_cli_common.py       # leitura UTF-8, seções ##, caminhos e coleta RFxx
│   ├── collect_quality_metrics.py  # coletor JSON/Markdown ISO 25010 + ISO 5055
│   ├── validate_docs_as_code.py
│   ├── validate_traceability.py
│   └── generate_traceability_matrix.py
├── src/
│   ├── core/domain/events.py   # Eventos de Contingência tipados
│   ├── core/services/replanning.py
│   ├── core/solvers/optw.py
│   └── adapters/web/           # app.py, contingency.py e template HTML
└── tests/
    ├── unit/                   # inclusive test_events.py, test_replanning_service.py,
    │                           # test_docs_as_code_validator.py, test_hexagonal_contracts.py,
    │                           # test_collect_quality_metrics.py e test_traceability_matrix_generator.py
    ├── integration/            # inclusive test_trip_replan_endpoint.py
    └── property/
```

Os artefatos acima são os mesmos confrontados pelos validadores docs-as-code e de rastreabilidade; a matriz do Plano de Testes (§7) é gerada a partir dos marcadores `requirement` da suíte.

---

## 5. Estado Entregue e Rastreabilidade

1. **Configuração do Projeto Python**: `pyproject.toml` com dependências de execução (`fastapi`, `uvicorn`, `jinja2`, `pydantic`, `pydantic-settings`, `httpx`) e de desenvolvimento/teste (`pytest`, `pytest-cov`, `hypothesis`, `mutmut`, `mypy`, `ruff`, `radon`, `import-linter`, `bandit`, `pip-audit`, `vulture`).

2. **Domínio puro (`src/core/domain/`)**: modelos de Viagem, Etapa de Viagem, Dia de Viagem, Conexão Interurbana e Roteiro em `models.py`; os 4 Eventos de Contingência tipados em `events.py` (`DelayEvent`, `ClosureEvent`, `SkipStopEvent`, `DurationAdjustmentEvent`), com testes em `tests/unit/test_events.py` e `tests/unit/test_apply_contingency_event.py`.

3. **Solver OPTW e Replanejamento**: heurística construtiva de inserção gulosa ponderada pela Pontuação de Utilidade, busca local 2-opt/swap, `ScheduleService` para Deslocamento em Cascata e `ReplanningService.replan` para recalcular a janela restante do Roteiro a partir do horário/coordenada atuais, preservando histórico e Slots de Refeição futuros e emitindo alerta de risco da Conexão Interurbana (`tests/unit/test_replanning_service.py`, `tests/integration/test_trip_replan_endpoint.py`).

4. **Testes de Propriedades (`tests/property/`)**: estratégias `hypothesis` validando invariantes universais (nenhum Ponto de Interesse visitado fora da Janela de Funcionamento, tempo total dentro da Janela de Disponibilidade e propagação exata do Deslocamento em Cascata).

5. **Adaptadores (`src/adapters/`)**: portas abstratas, adaptador Google Maps com cache SQLite e Modo Offline Replay com fixtures pré-gravadas para São Paulo, Lima e Juiz de Fora.

6. **Aplicação web (`src/adapters/web/`)**: rotas FastAPI, incluindo `POST /api/trip/replan`, orquestração dos Eventos de Contingência em `contingency.py`, template Jinja2 com controles na timeline do Dia de Viagem e banner de impacto. A interação em navegador real permanece como lacuna parcial, registrada no §8 do Plano de Testes.

7. **Gate e validadores de qualidade entregues**: `verify_quality.sh` executa `ruff`, `mypy --strict`, `radon cc`, `pytest --cov`, `scripts/validate_traceability.py`, `scripts/generate_traceability_matrix.py --check`, `scripts/validate_docs_as_code.py`, `lint-imports`, `bandit`, `vulture`, `radon mi/raw`, `pip-audit` (aviso) e `scripts/collect_quality_metrics.py`, com estágio opcional de mutação. Os quatro CLIs importam `scripts/quality_cli_common.py` por importação normal (sem mutar o path de imports nem suprimir avisos de lint), reutilizando a mesma coleta de marcadores `requirement` e de títulos RFxx; funcionam tanto como `python scripts/<cli>.py ...` quanto como `python -m scripts.<cli> ...`. Qualquer divergência detectada bloqueia o gate, exceto `pip-audit`/`vulture`, que são informativos conforme política documentada; o coletor grava `reports/quality-metrics.json`/`.md` e registra mutação como `not run` fora do modo `--full`. Os testes de CLI estão em `tests/unit/test_docs_as_code_validator.py`, `tests/unit/test_traceability_validator.py`, `tests/unit/test_traceability_matrix_generator.py` e `tests/unit/test_collect_quality_metrics.py`; os contratos hexagonais em `tests/unit/test_hexagonal_contracts.py`; a integração dos validadores ao gate em `tests/unit/test_quality_gate_validators.py`; e o contrato de importação compartilhada em `tests/unit/test_quality_cli_shared_imports.py`.

---

## 6. Habilidades Sugeridas (Suggested Skills)

Para a continuidade dos trabalhos, o próximo agente deve utilizar:
- **`tdd`** (`/home/agent/.gemini/config/skills/tdd/SKILL.md`): Conduzir a implementação das entidades de domínio, validador de janelas e solver OPTW estritamente via Test-Driven Development (Red-Green-Refactor).
- **`domain-modeling`** (`/home/agent/.gemini/config/skills/domain-modeling/SKILL.md`): Manter o `GLOSSARY.md` e ADRs sincronizados caso surjam novos termos ou decisões técnicas durante a implementação.
- **`code-review`** (`/home/agent/.gemini/config/skills/code-review/SKILL.md`): Verificar a aderência do código às métricas da ISO 25010 e padrões PEP antes de consolidar marcos no Git.
