# Handoff — Projeto Kairos (Traçador Dinâmico de Rotas Turísticas)

**Data**: 2026-11-07 (atualizado em 2026-11-25)  
**Repositório Remoto**: `git@github.com:lispz1610/kairos.git` (branch `main`)  
**Disciplina**: DCC061 - Engenharia de Software (UFJF) — Prof. Fabrício Martins Mendonça  
**Documentação Relacionada**: [README.md](../README.md) · [GLOSSARY.md](../GLOSSARY.md) · [Especificação de Requisitos (RF01–RF14)](./especificacao-requisitos-funcionais.md) · [Plano de Testes 29119](./testing/test-plan-29119.md) · [Freshness](./documentation-freshness.md)  
**Status**: Sistema implementado, consolidado e verificado ponta a ponta. Concepção, glossário ubíquo e ADRs `0001`–`0007` concluídos; requisitos `RF01`–`RF14` entregues (incluindo `RF14` **Modal Urbano**), arquitetura hexagonal consolidada (`#103` / PR `#118`), correções de **Replanejamento** e isolamento de cache SQLite entregues (`#104` / PR `#117`), guia didático reestruturado no [README.md](../README.md), [Plano de Testes ISO/IEC/IEEE 29119](./testing/test-plan-29119.md) sincronizado e revisão auditável de frescor documental registrada para encerramento pós-merge das pendências `#50`, `#52` e `#53`. Restam declaradas apenas lacunas parciais de interação visual em navegador real (ver §8 do Plano de Testes, conforme [ADR 0002](./adr/0002-stack-backend-python-fastapi.md)).

---

## 1. Contexto Acadêmico & Requisitos (DCC061)

O trabalho prático da disciplina **DCC061 — Engenharia de Software (UFJF)** abrange:

1. **Escolha de 2 temas da disciplina**: O grupo selecionou **Testes de Software** e **Qualidade de Software**.
2. **Entregáveis (40 pontos)**:
   - **Documento-texto (20 pts)**: Monografia (DOCX/PDF) abordando definição, histórico, importância, ferramentas, normas, profissões, certificações e impactos de IA em Testes e Qualidade.
   - **Código-fonte no Git (20 pts)**: Sistema que demonstra na prática os princípios dos temas escolhidos com rastreabilidade automatizada.
   - **Apresentação em sala**: 15 a 20 minutos com slides em PDF.

O [README.md](../README.md) foi reestruturado como guia didático integrando diretamente as **Unidades 9, 10 e 11** de DCC061 aos artefatos verificáveis do repositório.

---

## 2. Decisões Arquiteturais, Guia Didático e Fundamentação Técnica

### 2.1 Glossário, ADRs e Especificação Funcional (`RF01`–`RF14`)

Toda a concepção do domínio e da arquitetura foi refinada por *Grilling* e *Domain Modeling* e registrada em artefatos versionados:

- **[GLOSSARY.md](../GLOSSARY.md)**: Vocabulário ubíquo oficial com 25 termos canônicos (*Viagem*, *Etapa de Viagem*, *Dia de Viagem*, *Hospedagem*, *Dia de Troca de Hospedagem*, *Conexão Interurbana*, *Margem de Embarque*, *Modal de Transporte*, *Modal Urbano*, *Ponto de Interesse (POI)*, *Lista de Curadoria*, *Roteiro*, *Ponto de Partida/Retorno*, *Deslocamento*, *Matriz de Deslocamento*, *Janela de Disponibilidade*, *Janela de Funcionamento*, *Tempo de Permanência*, *Slot de Refeição*, *Estimativa de Gastos*, *Pontuação de Utilidade*, *Perfil de Preferência*, *Evento de Contingência*, *Replanejamento*, *Deslocamento em Cascata*) e seus sinônimos proibidos (`_Avoid_`).
- **[ADR 0001: Formulação como OPTW](./adr/0001-formulacao-algoritmica-optw.md)**: Modelagem do planejamento diário como *Orienteering Problem with Time Windows* (seleção de subconjunto e sequenciamento sob **Janela de Disponibilidade** e **Janela de Funcionamento**) com heurística construtiva gulosa (**Pontuação de Utilidade** por custo marginal) e busca local (2-opt/swap).
- **[ADR 0002: Stack Backend Python com FastAPI e Interface Simples](./adr/0002-stack-backend-python-fastapi.md)**: Foco no backend em Python/FastAPI sob padrão **MVC Web**, eliminando sobrecarga de SPA (sem React ou etapa de *build* Node). Interface leve em HTML/Jinja2 + Vanilla JS + Leaflet.
- **[ADR 0003: Integração Google Maps com Padrão Cache-Aside](./adr/0003-integracao-google-maps-com-cache.md)**: Consumo de **Pontos de Interesse (POIs)** e **Listas de Curadoria** com camada obrigatória de cache local em SQLite (`places_cache`).
- **[ADR 0004: Viagens Multicidades e Decomposição em Etapas Urbanas](./adr/0004-arquitetura-viagens-multicidades.md)**: Suporte a **Viagens** multicidades (como São Paulo e Lima ligadas por **Conexão Interurbana** em `flying`, `transit`, `driving` ou `walking` via `TransportMode`), isolando o solver OPTW urbano por **Dia de Viagem** e aplicando `departure_datetime`, **Margem de Embarque** (`boarding_cutoff_minutes`), alerta de risco (`InterCityRiskAlert`) e **Deslocamento em Cascata**.
- **[ADR 0005: Isolamento de Credenciais e Modo Offline Replay](./adr/0005-modo-offline-replay-credenciais.md)**: Proteção da chave `GOOGLE_MAPS_API_KEY` fora do versionamento. Na ausência de credencial, `create_places_adapter()` ativa automaticamente o **Modo Offline Replay** via `OfflineReplayPlacesAdapter` sobre os catálogos determinísticos de **São Paulo** (3 **Listas de Curadoria**) e **Lima** (2 **Listas de Curadoria**) em [`src/adapters/places/fixtures/catalog.json`](../src/adapters/places/fixtures/catalog.json).
- **[ADR 0006: Navegação em Duas Camadas: Mapa Macro Geodésico e Detalhe Urbano](./adr/0006-navegacao-macro-mapa-e-detalhe-urbano.md)**: Visão macro da **Viagem** na página inicial (cidades ligadas por arcos geodésicos) e visão micro do **Dia de Viagem** (linha do tempo com controles de **Evento de Contingência** à esquerda e mapa Leaflet à direita).
- **[ADR 0007: Gestão de Hospedagens, Curadoria Enriquecida e Estado Client-Side](./adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md)**: Decomposição em **Dias de Viagem**, **Dia de Troca de Hospedagem**, **Slots de Refeição** contextuais, **Lista de Curadoria** híbrida com parser anti-SSRF, **Deslocamento em Cascata** com modal de impacto, persistência *client-side* em `localStorage` (`kairos_trip_v1` e `kairos_trip_state_v1`), validação estrita de backup JSON e exportação completa em Markdown.
- **[Especificação de Requisitos Funcionais](./especificacao-requisitos-funcionais.md)**: Detalhamento formal dos requisitos **RF01 a RF14** alinhados às normas ISO/IEC 25010 e ISO/IEC/IEEE 29119, com destaque para **RF14 (Modal Urbano)**: `TripDay.urban_mode` restrito a `UrbanMode` (`driving` a `25,0` km/h ou `walking` a `5,0` km/h), padrão `driving` retrocompatível em backups JSON legados, parâmetro opcional `urban_mode` em `POST /api/trip/optimize` (descartando **POIs** inviáveis em `walking`) e rejeição HTTP 422 para `flying`/`transit`.

### 2.2 Síntese do Guia Didático Integrado no `README.md` (DCC061 Unidades 9–11)

O [README.md](../README.md) documenta a correspondência direta entre os conteúdos teóricos de **DCC061** e o código consolidado:

- **Unidade 9 — Arquitetura de Software**:
  - **Arquitetura em Camadas**: separação explícita entre o núcleo de domínio/serviços/solver (`src/core/`) e os adaptadores externos (`src/adapters/`).
  - **Padrão MVC Web**: `src/core/` atua como *Model*; `src/adapters/web/templates/index.html` (Jinja2 + Vanilla JS + Leaflet) atua como *View*; `src/adapters/web/app.py`, `contingency.py` e `backup.py` atuam como *Controller*.
  - **Arquitetura Hexagonal (*Ports & Adapters*)**: núcleo dependente apenas das portas abstratas `PlacesPort` e `UrlFetcherPort` (`src/core/ports/`), com dependência unidirecional e isolamento de I/O garantidos automaticamente por `import-linter` via contratos **`ARQ-1`** (`adapters` → `core`) e **`ARQ-2`** (`src.core` livre de `fastapi`, `uvicorn`, `jinja2`, `httpx`, `httpcore`, `requests`, `sqlite3` e `socket`).
- **Unidade 10 — Padrões de Projeto GoF e Análise Anti-Overengineering**:
  - Mapeamento concreto de 5 padrões GoF com justificativa de *Design for Change vs. Complexidade*: **Factory** (`create_places_adapter` e `TripStage.create`), **Proxy / Cache-Aside** (`CachedPlacesAdapter` sobre SQLite `places_cache` e `fallback_adapter`), **Adapter** (`PlacesPort`, `UrlFetcherPort`, `OfflineReplayPlacesAdapter`, `CachedPlacesAdapter`, `SafeHttpFetcher`/`PinnedIPTransport`/`PinnedIPBackend` e adaptadores primários Web), **Facade** (`orchestrate_trip_replan`, `ReplanningService.replan`, `LinkParserService`, `MarkdownExportService.export_trip_markdown`) e **Strategy** (`urban_mode_speed_kmh` / `_URBAN_MODE_SPEED_KMH` + `transit_speed_kmh` em `OPTWSolver`, algoritmos `solve` vs. `replan_remaining` e injeção polimórfica de `PlacesPort`, `UrlFetcherPort` e `PreferencesService`).
  - Evidências objetivas pós-`#103` (PR `#118`) contra *overengineering*: remoção de 8 classes espelho de backup em favor de `validate_backup_payload` (`src/adapters/web/backup.py`), unificação de `InterCityConnection.modal` via `TransportMode` (aceitando `"mode"` na entrada sem duplicar estado em `__dict__`), injeção de dependências explícita nos construtores (`CurationService`, `LinkParserService`, `OPTWSolver`), **0 ocorrências de `type: ignore` em `src/`** e teto de complexidade `< 10` (`radon cc` e análise AST).
- **Unidade 11 — Verificação & Validação, Pirâmide de Testes, FIRST, AAA e Normas ISO**:
  - Distinção aplicada entre **Verificação** (*produto conforme especificação e contratos*) e **Validação** (*adequação ao viajante e avaliação acadêmica em Modo Offline Replay*).
  - **Pirâmide de Testes** em cinco camadas (**Unidade**, **Integração** com `TestClient` + `node:vm`, **Propriedade/Contratos**, **Mutação** via `mutmut` no modo `--full` e **Validação Alfa** offline), **Caixa-Branca** vs. **Caixa-Preta** (Classes de Equivalência, Valor Limite, Property-Based Testing), princípios **FIRST** (incluindo isolamento SQLite via `tmp_path` e perfil `kairos_sem_prazo` restrito a `KAIROS_MUTATION=1`), anatomia **AAA (*Arrange–Act–Assert*)** e mapeamento às normas **ISO/IEC 25010**, **ISO/IEC 5055** e **ISO/IEC/IEEE 29119**.

---

## 3. Diretrizes de Qualidade, Normas ISO e Cadeia Automatizada

- **ISO/IEC 25010 (Qualidade de Produto)**:
  - *Adequação Funcional*: verificada por `275` casos `pytest` em `38` arquivos Python e `3` verificações JavaScript (`node:test`) em `tests/integration/web_replan_behavior.cjs`, com cobertura medida de **`96.0%`** (mínimo `>= 85%`) e rastreabilidade `RF01`–`RF14`.
  - *Confiabilidade & Tolerância a Falhas*: `mypy --strict src` com `0` erros em `30` arquivos (`0` `type: ignore`), invariantes `hypothesis` (`tests/property/`), preservação de histórico e **Slots de Refeição** reservados no **Replanejamento** dos 4 **Eventos de Contingência** (`DelayEvent`, `ClosureEvent`, `SkipStopEvent`, `DurationAdjustmentEvent`), além de avaliação por mutação em `src/core/` (`--full`).
  - *Manutenibilidade & Testabilidade*: contratos hexagonais `ARQ-1` e `ARQ-2` mantidos pelo `import-linter` (`0` violações), `ruff` com `0` violações (`C901`, `PLR0911`, `PLR0912`, `PLR0913`) e `vulture` com `0` achados informativos.
  - *Segurança*: proteção anti-SSRF com fixação de IP em `SafeHttpFetcher` (`PinnedIPTransport`/`PinnedIPBackend`), `bandit -q -r src -ll -s B104` com `0` achados e `pip-audit` com política documentada de aviso em *runner* `self-hosted` com conectividade restrita (`0` vulnerabilidades observadas localmente).
- **ISO/IEC/IEEE 29119 (Testes de Software)**:
  - Estratégia, critérios de entrada/saída, técnicas formais, resumo de casos e matriz de rastreabilidade (`RF01`–`RF08` automatizada e `RF09`–`RF14` em §7.1) sincronizados em [docs/testing/test-plan-29119.md](./testing/test-plan-29119.md).
- **ISO/IEC 5055 (Qualidade Estrutural de Código)**:
  - Complexidade ciclomática (`radon cc -s src`) e sintática (AST em `scripts/quality_cli_common.py`) com máximo **`9 < 10`** (`core`: máx `9`, média `3.1`; `adapters`: máx `7`, média `2.5`; global: média `2.9`, `0` funções em `10+`).
  - Inventário estrutural AST de `29` módulos (`58` classes, `50` funções, `143` métodos, `68.9%` de cobertura de docstrings), índice de manutenibilidade `radon mi` (média `68.92`, mínimo `7.46`) e volume bruto `radon raw` (`3130` SLOC, `4053` LOC, `2223` LLOC).
  - Coleta centralizada em [`scripts/collect_quality_metrics.py`](../scripts/collect_quality_metrics.py) sobre [`scripts/quality_cli_common.py`](../scripts/quality_cli_common.py), gerando `reports/quality-metrics.json` e `reports/quality-metrics.md`. O gate [`verify_quality.sh`](../verify_quality.sh) executa 13 etapas no modo rápido (registrando mutação como `"not run"` / `"não executado"`) ou 14 etapas em `--full` (com `mutmut` restrito a `src/core/`) e valida limiares via `--check`, sem *parsers* duplicados em shell.

---

## 4. Estrutura Atual do Repositório

```text
kairos/
├── .github/
│   ├── documentation-freshness.json  # escopo alvo declarado para auditoria de frescor
│   └── workflows/                    # quality.yml / ci.yml ([self-hosted, Linux, X64]) e documentation-freshness.yml
├── AGENTS.md
├── GLOSSARY.md                       # 25 termos canônicos e sinônimos _Avoid_
├── README.md                         # guia didático DCC061 (Unidades 9, 10 e 11)
├── pyproject.toml                    # dependências, ruff, mypy, import-linter, pytest, coverage e vulture
├── verify_quality.sh                 # gate unificado (modo rápido e --full com mutmut em src/core/)
├── docs/
│   ├── HANDOFF.md
│   ├── documentation-freshness.md    # regras de ciclo de vida da auditoria e encerramento pelo mantenedor
│   ├── especificacao-requisitos-funcionais.md  # RF01 a RF14
│   ├── adr/                          # ADR 0001 a 0007
│   └── testing/test-plan-29119.md    # Plano de Testes 29119 sincronizado e matriz RF01–RF14
├── scripts/
│   ├── quality_cli_common.py         # utilitário compartilhado (UTF-8, seções ##, RFxx, AST, parsers e limiares)
│   ├── collect_quality_metrics.py    # coletor ISO 25010 + ISO 5055 (--check)
│   ├── validate_traceability.py      # validador offline RF × testes
│   ├── generate_traceability_matrix.py  # gerador/verificador (--check) da matriz RF01–RF08
│   ├── validate_docs_as_code.py      # validador docs-as-code (Plano 29119 + HANDOFF × árvore)
│   ├── check_markdown_links.py       # auditoria de links e âncoras Markdown
│   ├── documentation_freshness.py    # auditoria local de frescor documental (--target)
│   └── documentation_audit_runner.py # runner de relatório CI para Documentation Freshness
├── src/
│   ├── core/
│   │   ├── domain/                   # models.py (Trip, TripStage, TripDay, UrbanMode, TransportMode, ...) e events.py
│   │   ├── ports/                    # places.py (PlacesPort) e fetcher.py (UrlFetcherPort)
│   │   ├── services/                 # curation, dining_and_budget, link_parser, markdown_export, preferences, replanning, schedule
│   │   └── solvers/optw.py           # OPTWSolver e urban_mode_speed_kmh (25.0 driving / 5.0 walking)
│   └── adapters/
│       ├── http/safe_fetcher.py      # SafeHttpFetcher, PinnedIPTransport e PinnedIPBackend (anti-SSRF)
│       ├── places/                   # create_places_adapter, cached_adapter, offline_adapter e fixtures/catalog.json (São Paulo e Lima)
│       └── web/                      # app.py, backup.py (validate_backup_payload), contingency.py e templates/index.html
└── tests/
    ├── conftest.py                   # perfil kairos_sem_prazo ativo apenas com KAIROS_MUTATION=1
    ├── unit/                         # 23 arquivos, 183 casos
    ├── integration/                  # 10 arquivos Python (74 casos) + web_replan_behavior.cjs (3 casos node:test)
    ├── property/                     # 3 arquivos, 5 propriedades (hypothesis)
    ├── test_requirement_marker_spec.py  # 6 casos
    └── test_ticket_34_spec.py        # 7 casos
```

---

## 5. Estado Entregue e Rastreabilidade Consolidada (`RF01`–`RF14`, `#102`, `#103` e `#104`)

1. **Configuração e Governança Python (`pyproject.toml`)**: dependências de execução (`fastapi`, `uvicorn`, `jinja2`, `pydantic`, `pydantic-settings`, `httpx`) e qualidade (`pytest`, `pytest-cov`, `hypothesis`, `mutmut`, `mypy`, `ruff`, `radon`, `import-linter`, `bandit`, `pip-audit`, `vulture`), além dos contratos `ARQ-1` e `ARQ-2`, `max-complexity = 9` e `mypy --strict`.
2. **Domínio Puro e Consolidação Pós-`#103` (`src/core/domain/`, PR `#118`)**:
   - `models.py`: `KairosModel`, tipos estritos `IsoDate`/`IsoDatetime`/`IsoTime`, `collect_unknown_fields`, `Trip`, `TripStage` (`TripStage.create`), `TripDay` com `urban_mode: UrbanMode` (`driving`/`walking`), `Accommodation`, **Dia de Troca de Hospedagem**, `InterCityConnection` com `modal` canônico (`TransportMode`) e alias legado `"mode"` tratado em `_apply_modal_default` sem duplicar estado em `__dict__` (`tests/unit/test_models.py`, 16 casos; `tests/unit/test_domain_trip.py`, 10 casos).
   - `events.py`: os 4 **Eventos de Contingência** tipados (`DelayEvent`, `ClosureEvent`, `SkipStopEvent`, `DurationAdjustmentEvent`), testados em `tests/unit/test_events.py` (10 casos) e `tests/unit/test_apply_contingency_event.py` (4 casos).
3. **Motor OPTW (`RF11`, `RF14`) e Replanejamento Pós-`#104` (`RF12`, PR `#117`)**:
   - `OPTWSolver` (`src/core/solvers/optw.py`): heurística construtiva gulosa + busca local 2-opt/swap, `replan_remaining`, `urban_mode_speed_kmh` (`25.0` km/h em `driving`, `5.0` km/h em `walking`) com descarte de **POIs** que excedam a **Janela de Disponibilidade**, e adoção padrão de `POI.stay_duration_minutes` como **Tempo de Permanência** quando não há `DurationAdjustmentEvent` para o **POI**.
   - `ScheduleService` (`src/core/services/schedule.py`): **Deslocamento em Cascata** e validação de **Janela de Funcionamento** e **Janela de Disponibilidade** (`tests/unit/test_schedule_service.py`, 8 casos).
   - `ReplanningService.replan` (`src/core/services/replanning.py`): bloqueio direto de **Slots de Refeição** futuros reservados — inclusive sem estabelecimento selecionado — via `reserved_meal_slots` e `reserved_future_stops` em `_free_windows`, preservação de visitas concluídas, teto seguro frente à **Margem de Embarque** e emissão de `InterCityRiskAlert` (`tests/unit/test_replanning_service.py`, 14 casos; `tests/integration/test_trip_replan_endpoint.py`, 8 casos; `tests/integration/test_optimize_api.py`, 8 casos).
4. **Testes de Propriedade (`tests/property/`)**: 5 invariantes `hypothesis` (`test_optw_properties.py`, `test_preferences_properties.py`, `test_ripple_shift_properties.py`) comprovando respeito à **Janela de Disponibilidade** e aos **Slots de Refeição** reservados, monotonicidade do **Perfil de Preferência**, invariantes do **Deslocamento em Cascata** e idempotência de serialização JSON da **Viagem**.
5. **Adaptadores Secundários, Cache Isolado (`#104`) e Injeção Explícita (`#103`)**:
   - `create_places_adapter`, `CachedPlacesAdapter` e `OfflineReplayPlacesAdapter` implementam `PlacesPort` servindo exclusivamente os catálogos de **São Paulo** e **Lima** em [`src/adapters/places/fixtures/catalog.json`](../src/adapters/places/fixtures/catalog.json).
   - `SafeHttpFetcher` (`PinnedIPTransport` e `PinnedIPBackend`, com `0` `type: ignore`) implementa `UrlFetcherPort` para `LinkParserService(fetcher, curation_service)`.
   - Em [`tests/integration/test_curation_api.py`](../tests/integration/test_curation_api.py), a *fixture* `isolated_places_adapter(monkeypatch, tmp_path)` (`autouse=True`) garante banco SQLite exclusivo por caso em `tmp_path / "places.db"` com fechamento de `_conn` no *teardown*, validada por `test_places_cache_is_independent_between_cases` e `test_concurrent_places_caches_remain_isolated`.
6. **Adaptador Primário Web, Validação de Backup (`#103`) e Runtime JS (`#104`)**:
   - *Endpoints* FastAPI em [`src/adapters/web/app.py`](../src/adapters/web/app.py), fachada [`orchestrate_trip_replan`](../src/adapters/web/contingency.py) e validação estrita [`validate_backup_payload`](../src/adapters/web/backup.py) (`tests/integration/test_trip_backup_api.py`, 13 casos, sem classes espelho de backup).
   - Comportamento JavaScript da *timeline* verificado em [`tests/integration/test_web_replan_behavior.py`](../tests/integration/test_web_replan_behavior.py) + [`tests/integration/web_replan_behavior.cjs`](../tests/integration/web_replan_behavior.cjs) (`3` testes `node:test` via `node:vm`: vinculação ao `TripDay`, envio de `reserved_meal_slots`/`reserved_future_stops` com persistência no dia original, e preservação de horário local sob `TZ=America/Sao_Paulo`).
   - Conformidade vocabular da interface garantida por `tests/unit/test_index_html_vocabulary.py` e contratos HTTP/HTML por `tests/integration/test_web_app.py`. A interação visual por cliques em navegador real permanece fora do escopo E2E e documentada como lacuna parcial em §8 do [Plano de Testes](./testing/test-plan-29119.md) (conforme [ADR 0002](./adr/0002-stack-backend-python-fastapi.md)).
7. **Cadeia Completa de Qualidade e Rastreabilidade Documental**:
   - Os quatro CLIs de qualidade importam `scripts/quality_cli_common.py` normalmente (validado por `tests/unit/test_quality_cli_shared_imports.py`) e são verificados ponta a ponta por:
     - `python scripts/validate_traceability.py --spec docs/especificacao-requisitos-funcionais.md --root .`
     - `python scripts/generate_traceability_matrix.py --plan docs/testing/test-plan-29119.md --spec docs/especificacao-requisitos-funcionais.md --root . --check`
     - `python scripts/validate_docs_as_code.py --plan docs/testing/test-plan-29119.md --handoff docs/HANDOFF.md --root .`
     - `python scripts/check_markdown_links.py --root .`
     - `python scripts/documentation_freshness.py --root . --target`
     - `bash ./verify_quality.sh`

---

## 6. Auditoria de Frescor Documental e Resolução das Pendências (`#50`, `#52` e `#53`)

Esta seção registra a revisão formal do mantenedor sobre as três *issues* gerenciadas pelo fluxo [`.github/workflows/documentation-freshness.yml`](../.github/workflows/documentation-freshness.yml) e por [`scripts/documentation_audit_runner.py`](../scripts/documentation_audit_runner.py), conforme a política de ciclo de vida definida em [`docs/documentation-freshness.md`](./documentation-freshness.md).

### 6.1 Diagnóstico e Revisão de Cada Achado Aberto (`needs-triage`)

| Issue | Escopo / Revisão Origem | Código do Achado | Causa Raiz Verificada | Conclusão da Revisão do Mantenedor |
| --- | --- | --- | --- | --- |
| **`#50`** *(Documentation freshness: default branch)* | Run `44870959517` (`5ba59f36`, PR `#49` que instalou *workflows* e configuração de frescor) | `documentation-scope-review-required` em `.github/documentation-freshness.json:0` | O auditor emite revisão obrigatória de escopo sempre que `.github/documentation-freshness.json` figura entre os arquivos modificados. | **Aprovado e justificado**: [`.github/documentation-freshness.json`](../.github/documentation-freshness.json) declara `schema: "sciflow-cicd/documentation-freshness/v1"`, `managed_by: "sciflow-cicd"` e `paths: ["docs/documentation-freshness.md"]`, enquanto a documentação do projeto (`README.md`, `test-plan-29119.md`, `HANDOFF.md`) foi sincronizada integralmente na entrega da `#105`. |
| **`#52`** *(Documentation freshness: PR `#43`)* | Run `44871035461` (`acd5e416`, PR `#43`: *bump `actions/checkout` `4.2.2` → `7.0.1`*, mesclado) | `semantic-review-required` em `README.md:0` | O PR `#43` alterou apenas `.github/workflows/ci.yml`. A regex `BEHAVIOR` de `scripts/documentation_audit_runner.py` casa com `.github/workflows/*.yml`, disparando revisão semântica por não haver mudança simultânea no escopo documental. | **Aprovado e justificado**: atualização rotineira do Dependabot na ação `actions/checkout` do CI sem impacto funcional no Kairos; além disso, `README.md` e `docs/HANDOFF.md` foram atualizados refletindo o estado consolidado do CI. |
| **`#53`** *(Documentation freshness: PR `#42`)* | Run `44871033572` (`8c8e2a96`, PR `#42`: *bump `actions/setup-python` `6.3.0` → `7.1.0`*, mesclado) | `semantic-review-required` em `README.md:0` | O PR `#42` alterou apenas `.github/workflows/ci.yml`, acionando a mesma regra `BEHAVIOR` de `scripts/documentation_audit_runner.py` sobre alteração em *workflow*. | **Aprovado e justificado**: atualização rotineira do Dependabot na ação `actions/setup-python` do CI mantendo Python `3.12` sem impacto no comportamento do sistema ou quebra documental. |

### 6.2 Verificação Local Limpa vs. Falha de Faturamento no Runner Hospedado do GitHub

1. **Resultado limpo da auditoria local na revisão atual**:
   - `python scripts/check_markdown_links.py --root .` → código de saída `0` (`Markdown link audit passed (0 broken links).` em todos os arquivos `.md` do repositório).
   - `python scripts/documentation_freshness.py --root . --target` → código de saída `0` (`Documentation freshness audit passed.` validando `.agents/skills/manifest.json` e o escopo declarado em `.github/documentation-freshness.json`).
2. **Motivo exato das falhas do *workflow* `Documentation Freshness Audit` no GitHub Actions (ex.: run `45526227231`)**:
   - Os três *jobs* (`audit`, `report` e `refresh`) de [`.github/workflows/documentation-freshness.yml`](../.github/workflows/documentation-freshness.yml) utilizam `runs-on: ubuntu-24.04` (*runner* hospedado pelo GitHub), ao contrário de [`.github/workflows/quality.yml`](../.github/workflows/quality.yml) e [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), configurados com `runs-on: [self-hosted, Linux, X64]`.
   - Na execução `45526227231` (*push* em `main` `26505b4b556f2f1773d9cf2e25b124fbb10b314d`, *check-run* `138910172516`) e em execuções adjacentes no mesmo *runner* (`45529372488`, `45526212568`, `45525785220`, `45524964314`, `45524957966`), o *job* `audit` concluiu como `failure` antes mesmo de iniciar qualquer passo (`steps` vazios; `report` e `refresh` `skipped`) com a anotação da plataforma GitHub: *"The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings"*.
   - Portanto, a falha observada no GitHub Actions decorre exclusivamente do bloqueio de faturamento/limite de gastos da conta nos *runners* hospedados `ubuntu-24.04`, e **não** de erro de sintaxe, link quebrado ou inconsistência documental no repositório.

### 6.3 Procedimento Explícito de Encerramento Pós-Merge (`docs/documentation-freshness.md`)

Conforme estabelecido em [`docs/documentation-freshness.md`](./documentation-freshness.md):
- Novas execuções limpas atualizam o relatório de uma *issue* gerenciada aberta, **mas nunca fecham a *issue* automaticamente** (enquanto a *issue* permanecer aberta, o status `documentation-freshness` permanece intencionalmente em `failure` para exigir revisão humana).
- **Ação explícita pós-merge do mantenedor**: após o *merge* do PR da issue `#105` (consolidando esta revisão auditável, `README.md` e `docs/testing/test-plan-29119.md`) e confirmação dos resultados limpos de `check_markdown_links.py` e `documentation_freshness.py --target`, **o mantenedor deve fechar manualmente as *issues* `#50`, `#52` e `#53`** no GitHub (referenciando este registro). Quando os *runners* hospedados estiverem desbloqueados, o evento `issues: [closed, reopened]` aciona o *job* `refresh` de `documentation-freshness.yml` para atualizar o status correspondente.

---

## 7. Referências Operacionais para Manutenção Contínua

Para futuras evoluções ou revisões sobre este repositório, consulte:
- **[AGENTS.md](../AGENTS.md)** e **[docs/agents/domain.md](./agents/domain.md)**: obrigatoriedade de executar `./verify_quality.sh` (ou `./verify_quality.sh --full` ao alterar `src/core/`) e de respeitar estritamente `GLOSSARY.md` e `docs/adr/`.
- **[docs/agents/issue-tracker.md](./agents/issue-tracker.md)** e **[docs/agents/triage-labels.md](./agents/triage-labels.md)**: convenções de rastreamento de *issues* via `gh` CLI e vocabulário padrão de rótulos (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).
- **Práticas de engenharia adotadas**: **TDD** (*Red–Green–Refactor*), **Domain Modeling** (preservação do vocabulário ubíquo e ADRs) e **Code Review** (verificação de aderência às normas ISO 25010, ISO 5055 e ISO/IEC/IEEE 29119).
