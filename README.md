# Kairos — Traçador Dinâmico de Rotas Turísticas

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Engenharia de Software](https://img.shields.io/badge/UFJF-DCC061-red.svg)](https://www.ufjf.br/)
[![Standards](https://img.shields.io/badge/standards-ISO%2FIEC%2025010%20%7C%205055%20%7C%2029119-green.svg)](https://www.iso.org/)

**Kairos** é um sistema de planejamento e otimização dinâmica de **Viagens** multicidades sob restrições temporais e espaciais do mundo real, estruturando cada **Etapa de Viagem** em **Dias de Viagem** e **Roteiros** sobre **Pontos de Interesse (POIs)** elegíveis.

Desenvolvido para o Trabalho Prático da disciplina **DCC061 — Engenharia de Software** do Departamento de Ciência da Computação da **Universidade Federal de Juiz de Fora (UFJF)** (Prof. Fabrício Martins Mendonça), com foco aprofundado em **Testes de Software** e **Qualidade de Software**, este documento atua como guia didático integrando as **Unidades 9, 10 e 11** da disciplina diretamente aos artefatos verificáveis do repositório:

- **Unidade 9 — Arquitetura de Software**: integração prática entre **Arquitetura em Camadas**, padrão **MVC Web** e **Arquitetura Hexagonal (Ports & Adapters)**, respaldada por contratos automatizados (`ARQ-1` e `ARQ-2`) e registros de decisão arquitetural (**ADRs 0001–0007**).
- **Unidade 10 — Padrões de Projeto e Manutenibilidade**: aplicação pragmática de Padrões de Projeto GoF com análise explícita de *trade-offs* contra *overengineering* e controle de complexidade.
- **Unidade 11 — Verificação, Validação e Normas ISO**: articulação entre Pirâmide de Testes, princípios FIRST, padrão AAA (*Arrange–Act–Assert*) e métricas das normas `ISO/IEC 25010`, `ISO/IEC 5055` e `ISO/IEC/IEEE 29119`.

---

## Sumário

- [Contexto Acadêmico e Objetivos Centrais](#contexto-acadêmico-e-objetivos-centrais)
- [Vocabulário Ubíquo e Domínio](#vocabulário-ubíquo-e-domínio)
- [Arquitetura em Camadas, MVC Web e Arquitetura Hexagonal](#arquitetura-em-camadas-mvc-web-e-arquitetura-hexagonal)
  - [Visão Integrada em Diagramas](#visão-integrada-em-diagramas)
  - [Arquitetura em Camadas (Layered Architecture)](#arquitetura-em-camadas-layered-architecture)
  - [Padrão MVC Web (Model–View–Controller)](#padrão-mvc-web-modelviewcontroller)
  - [Arquitetura Hexagonal e Contratos ARQ-1 e ARQ-2](#arquitetura-hexagonal-e-contratos-arq-1-e-arq-2)
- [Documentação e Decisões Arquiteturais (ADRs)](#documentação-e-decisões-arquiteturais-adrs)
- [Padrões de Projeto GoF e Análise Anti-Overengineering](#padrões-de-projeto-gof-e-análise-anti-overengineering)
- [Verificação & Validação, Pirâmide de Testes e Normas ISO](#verificação-validação-pirâmide-de-testes-e-normas-iso)

---

## Contexto Acadêmico e Objetivos Centrais

No contexto de **DCC061 (Unidades 9, 10 e 11)**, o Kairos demonstra como decisões arquiteturais explícitas viabilizam testabilidade rigorosa, isolamento de infraestrutura externa e conformidade contínua com normas internacionais de qualidade, sem sacrificar a simplicidade operacional:

- **Otimização de Roteiro via OPTW**: Modela o planejamento de cada **Dia de Viagem** como uma variação do *Orienteering Problem with Time Windows* (OPTW), maximizando a **Pontuação de Utilidade** acumulada a partir do **Perfil de Preferência** (intensidades de `0` a `10`) e das **Listas de Curadoria**, respeitando a **Janela de Disponibilidade** do usuário, a **Janela de Funcionamento** e o **Tempo de Permanência** de cada **Ponto de Interesse (POI)**, o **Ponto de Partida/Retorno** (**Hospedagem** ativa ou ponto de chegada/saída) e o **Modal Urbano** (`driving` a 25 km/h ou `walking` a 5 km/h) no **Deslocamento**.
- **Viagens Multicidades e Hierarquia Temporal**: Organiza a **Viagem** em **Etapas de Viagem** por cidade — decompostas em **Dias de Viagem** com suporte a **Dia de Troca de Hospedagem**, **Slots de Refeição** contextuais e **Estimativa de Gastos** — conectadas por **Conexões Interurbanas** (`flying`, `transit`, `driving`, `walking` via `TransportMode`) com horário de partida (`departure_datetime`) e **Margem de Embarque** (`boarding_cutoff_minutes`).
- **Adaptação Dinâmica em Tempo Real**: Trata **Eventos de Contingência** tipados (`DelayEvent`, `ClosureEvent`, `SkipStopEvent`, `DurationAdjustmentEvent`) com **Replanejamento** automático do **Roteiro** restante, preservação de **Slots de Refeição** já reservados, emissão de alerta de risco sobre a **Conexão Interurbana** (`InterCityRiskAlert`) e propagação de datas entre **Etapas de Viagem** por **Deslocamento em Cascata**.
- **Resiliência, Cache-Aside e Modo Offline Replay**: Consome **Pontos de Interesse (POIs)** e **Listas de Curadoria** via Google Maps Platform com persistência em SQLite (*Cache-Aside*) e fallback determinístico para **Modo Offline Replay** (`OfflineReplayPlacesAdapter`, alimentado por [`src/adapters/places/fixtures/catalog.json`](./src/adapters/places/fixtures/catalog.json) com catálogos de São Paulo e Lima), permitindo avaliação acadêmica completa sem credenciais externas ([ADR 0005](./docs/adr/0005-modo-offline-replay-credenciais.md)).
- **Estado Client-Side, Validação Estrita e Exportação**: Mantém o estado da **Viagem** no `localStorage` do navegador (`kairos_trip_v1` e `kairos_trip_state_v1`), com backend FastAPI *stateless*, validação estrita de backup JSON (`validate_backup_payload`) e exportação completa em Markdown estruturado ([ADR 0007](./docs/adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md)).

### Execução Rápida e Verificação Local

Os comandos abaixo reproduzem o ambiente de desenvolvimento e o pipeline de verificação definidos em [`pyproject.toml`](./pyproject.toml) e [`.github/workflows/quality.yml`](./.github/workflows/quality.yml):

```bash
pip install -e ".[dev]"
bash ./verify_quality.sh                # Gate rápido: lint, mypy --strict, pytest --cov, contratos ARQ-1/ARQ-2 e ISO
uvicorn src.adapters.web.app:app        # Servidor web local (opera automaticamente em Modo Offline Replay sem GOOGLE_MAPS_API_KEY)
```

---

## Vocabulário Ubíquo e Domínio

O modelo de domínio segue estritamente os termos canônicos definidos em [`GLOSSARY.md`](./GLOSSARY.md), evitando ambiguidades entre código, documentação e interface web:

| Conceito Canônico (`GLOSSARY.md`) | Papel no Domínio | Representação Principal em `src/core/` |
| --- | --- | --- |
| **Viagem** | Planejamento global formado por **Etapas de Viagem** e **Conexões Interurbanas** | `Trip` (`src/core/domain/models.py`) |
| **Etapa de Viagem** | Recorte geográfico e temporal restrito a uma cidade, decomposto em **Dias de Viagem** | `TripStage` (`src/core/domain/models.py`) |
| **Dia de Viagem** e **Dia de Troca de Hospedagem** | Recorte de um dia no calendário associado a **Hospedagem**, **Modal Urbano** e **Roteiro** | `TripDay`, `Accommodation` (`src/core/domain/models.py`) |
| **Conexão Interurbana** e **Margem de Embarque** | Ligação de longa distância entre cidades com **Modal de Transporte** e limite operacional | `InterCityConnection`, `TransportMode` (`src/core/domain/models.py`) |
| **Ponto de Interesse (POI)** e **Lista de Curadoria** | Local elegível com coordenadas, **Janela de Funcionamento**, **Tempo de Permanência** e bonificação de curadoria | `POI`, `CurationList`, `CurationService` |
| **Roteiro**, **Deslocamento** e **Matriz de Deslocamento** | Sequência cronológica viável dentro da **Janela de Disponibilidade**, com tempos calculados conforme o **Modal Urbano** | `Itinerary`, `RouteStop`, `OPTWSolver`, `UrbanMode` |
| **Ponto de Partida/Retorno** | Coordenada inicial e final obrigatória do **Roteiro** (em geral a **Hospedagem** do dia) | `start_location`, `end_location` (`OPTWSolver.solve`) |
| **Slot de Refeição**, **Estimativa de Gastos** e **Perfil de Preferência** | Pausas alimentares contextuais, projeção financeira e pesos temáticos (`0`–`10`) sobre a **Pontuação de Utilidade** | `MealSlot`, `DiningService`, `BudgetSummary`, `PreferencesProfile` |
| **Evento de Contingência**, **Replanejamento** e **Deslocamento em Cascata** | Ocorrências em execução, recálculo do **Roteiro** restante e propagação de datas entre etapas | `events.py`, `ReplanningService`, `ScheduleService` |

---

## Arquitetura em Camadas, MVC Web e Arquitetura Hexagonal

O Kairos combina três visões arquiteturais complementares sobre o mesmo código-fonte:

1. **Arquitetura em Camadas** separa o núcleo puro de domínio e otimização (`src/core/`) da camada de adaptadores e infraestrutura (`src/adapters/`).
2. **Padrão MVC Web** organiza a entrega HTML/HTTP dentro de `src/adapters/web/` em conjunto com o modelo de domínio em `src/core/`, eliminando a sobrecarga de uma SPA ([ADR 0002](./docs/adr/0002-stack-backend-python-fastapi.md)).
3. **Arquitetura Hexagonal (*Ports & Adapters*)** aplica a inversão de dependência (DIP): o núcleo define portas abstratas (`PlacesPort` e `UrlFetcherPort`) em `src/core/ports/`, enquanto adaptadores primários (*driving*) conduzem casos de uso e adaptadores secundários (*driven*) implementam persistência SQLite, chamadas HTTP protegidas e fixtures offline.

### Visão Integrada em Diagramas

#### Diagrama em Blocos (Camadas, MVC Web, Hexagonal e Contratos)

```text
+-----------------------------------------------------------------------------------+
|                   CAMADA DE ADAPTADORES  (src/adapters/)                          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Adaptadores Primários / Driving (Entrada HTTP e Interface Web — MVC)        |  |
|  |                                                                             |  |
|  |  [View]     src/adapters/web/templates/index.html                           |  |
|  |             (Jinja2 + Vanilla JS + Leaflet + localStorage client-side)      |  |
|  |                |  GET /  |  fetch(/api/...)                                 |  |
|  |                v         v                                                  |  |
|  |  [Ctrl]     src/adapters/web/app.py  (14 endpoints FastAPI + DTOs)          |  |
|  |             src/adapters/web/contingency.py (orchestrate_trip_replan)       |  |
|  |             src/adapters/web/backup.py      (validate_backup_payload)       |  |
|  +-----------------------------------+-----------------------------------------+  |
|                                      | dependência unidirecional (ARQ-1)          |
|                                      v                                            |
|  +-----------------------------------------------------------------------------+  |
|  |                 NÚCLEO DA APLICAÇÃO  (src/core/)  —  ARQ-2: sem I/O/web     |  |
|  |                                                                             |  |
|  |  [Portas]   src/core/ports/places.py   -> PlacesPort(ABC)                   |  |
|  |             src/core/ports/fetcher.py  -> UrlFetcherPort(ABC)               |  |
|  |                                                                             |  |
|  |  [Serviços] src/core/services/                                              |  |
|  |   (Model)   curation.py | dining_and_budget.py | link_parser.py             |  |
|  |             markdown_export.py | preferences.py | replanning.py             |  |
|  |             schedule.py                                                     |  |
|  |                                                                             |  |
|  |  [Solver]   src/core/solvers/optw.py -> OPTWSolver (guloso + 2-opt/swap)    |  |
|  |                                                                             |  |
|  |  [Domínio]  src/core/domain/models.py (Trip, TripStage, TripDay, POI, ...)  |  |
|  |   (Model)   src/core/domain/events.py (Delay, Closure, Skip, DurationAdj.)  |  |
|  +-----------------------------------+-----------------------------------------+  |
|                                      ^  implementam Portas (Inversão / DIP)       |
|                                      |                                            |
|  +-----------------------------------+-----------------------------------------+  |
|  | Adaptadores Secundários / Driven (Persistência Local, APIs Externas e HTTP) |  |
|  |                                                                             |  |
|  |  src/adapters/places/                                                       |  |
|  |   - __init__.py       -> create_places_adapter() (Factory)                  |  |
|  |   - cached_adapter.py -> CachedPlacesAdapter(PlacesPort) [SQLite + Google]  |  |
|  |   - offline_adapter.py-> OfflineReplayPlacesAdapter(PlacesPort) [fixtures]  |  |
|  |                                                                             |  |
|  |  src/adapters/http/                                                         |  |
|  |   - safe_fetcher.py   -> SafeHttpFetcher(UrlFetcherPort) [anti-SSRF/IP pin] |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Fluxo de Dependências e Comunicação Hexagonal

```mermaid
flowchart TB
    subgraph WEB["Adaptadores Primários — Web e MVC (src/adapters/web/)"]
        VIEW["View: templates/index.html (Jinja2, Vanilla JS, Leaflet, localStorage)"]
        CTRL["Controller: app.py + contingency.py + backup.py (FastAPI)"]
        VIEW -->|"fetch JSON (/api/...)"| CTRL
        CTRL -->|"renderiza HTML (GET /)"| VIEW
    end

    subgraph CORE["Núcleo Hexagonal — Model e Regras (src/core/) [ARQ-2: sem I/O/web]"]
        direction TB
        SVC["Serviços: Curation, Dining, LinkParser, MarkdownExport, Preferences, Replanning, Schedule"]
        SOLVER["Solver OPTW: OPTWSolver (src/core/solvers/optw.py)"]
        DOM["Domínio Puro: models.py + events.py (Trip, TripStage, TripDay, POI, Itinerary)"]
        PORTS["Portas Abstratas: PlacesPort e UrlFetcherPort (src/core/ports/)"]
        SVC --> SOLVER
        SVC --> DOM
        SOLVER --> DOM
        SVC --> PORTS
    end

    subgraph DRIVEN["Adaptadores Secundários — Driven (src/adapters/places/ e http/)"]
        FACTORY["create_places_adapter() (Raiz de Composição)"]
        CACHE["CachedPlacesAdapter (SQLite places_cache + Google Places)"]
        OFFLINE["OfflineReplayPlacesAdapter (fixtures/catalog.json)"]
        FETCHER["SafeHttpFetcher + PinnedIPTransport (anti-SSRF)"]
        FACTORY --> CACHE
        CACHE --> OFFLINE
    end

    CTRL -->|"ARQ-1: invoca serviços e solver"| SVC
    CTRL -->|"compõe e injeta dependências"| FACTORY
    CTRL -->|"compõe e injeta dependências"| FETCHER
    CACHE -.->|"implementa PlacesPort"| PORTS
    OFFLINE -.->|"implementa PlacesPort"| PORTS
    FETCHER -.->|"implementa UrlFetcherPort"| PORTS
```

### Arquitetura em Camadas (Layered Architecture)

Na macroestrutura de diretórios em `src/`, cada subcamada possui fronteira de responsabilidade explícita e baixa complexidade estrutural:

| Camada / Pacote | Módulos | Responsabilidades Principais |
| --- | --- | --- |
| **Domínio** (`src/core/domain/`) | `models.py`, `events.py` | Entidades e *value objects* validados via `KairosModel` (`Trip`, `TripStage`, `TripDay`, `Accommodation`, `InterCityConnection`, `TransportMode`, `UrbanMode`, `POI`, `CurationList`, `Itinerary`, `RouteStop`, `MealSlot`, `PreferencesProfile`, `Coordinates`, `TimeWindow`), `collect_unknown_fields` e os quatro **Eventos de Contingência** (`DelayEvent`, `ClosureEvent`, `SkipStopEvent`, `DurationAdjustmentEvent`). |
| **Portas** (`src/core/ports/`) | `places.py`, `fetcher.py` | Contratos abstratos (`ABC`) que blindam o núcleo contra bibliotecas externas: `PlacesPort` (`get_curated_lists`, `search_places`) e `UrlFetcherPort` (`fetch_url`, `validate_url_safety`, além de `SSRFValidationError`). |
| **Serviços** (`src/core/services/`) | `curation.py`, `dining_and_budget.py`, `link_parser.py`, `markdown_export.py`, `preferences.py`, `replanning.py`, `schedule.py` | Casos de uso coesos: bonificação por **Lista de Curadoria** (`CurationService`), **Slots de Refeição** e **Estimativa de Gastos** (`DiningService`), extração de POIs via link/texto (`LinkParserService`), exportação Markdown (`MarkdownExportService`), ponderação por **Perfil de Preferência** (`PreferencesService`), **Replanejamento** com `InterCityRiskAlert` (`ReplanningService`) e **Deslocamento em Cascata** (`ScheduleService`). |
| **Solver** (`src/core/solvers/`) | `optw.py` | Motor `OPTWSolver` (heurística construtiva gulosa + busca local 2-opt/swap e `replan_remaining`), cálculo geodésico (`haversine_distance_km`, `estimate_transit_minutes`) e velocidade por **Modal Urbano** (`urban_mode_speed_kmh`: `25.0` km/h para `driving`, `5.0` km/h para `walking`). |
| **Adaptador Primário Web** (`src/adapters/web/`) | `app.py`, `contingency.py`, `backup.py`, `templates/index.html` | Raiz de composição FastAPI, DTOs de requisição/resposta, tradução de **Eventos de Contingência** (`ContingencyEventInput`, `to_domain_event`, `apply_contingency_event`, `orchestrate_trip_replan`), validação estrita de backup (`validate_backup_payload`) e interface HTML/Jinja2/Leaflet. |
| **Adaptadores Secundários de Lugares** (`src/adapters/places/`) | `__init__.py`, `cached_adapter.py`, `offline_adapter.py`, `fixtures/mock_catalog.py`, `fixtures/catalog.json` | Fábrica `create_places_adapter` com resolução de `GOOGLE_MAPS_API_KEY`, cache SQLite `places_cache` (*Cache-Aside* em `CachedPlacesAdapter`) e fallback determinístico em `OfflineReplayPlacesAdapter` com catálogos de São Paulo e Lima. |
| **Adaptador Secundário HTTP** (`src/adapters/http/`) | `safe_fetcher.py` | Implementação de `UrlFetcherPort` via `SafeHttpFetcher`, `PinnedIPTransport` e `PinnedIPBackend`, bloqueando endereços privados/loopback/link-local e fixando o IP validado contra *DNS rebinding* (SSRF). |

### Padrão MVC Web (Model–View–Controller)

Por decisão explícita do [ADR 0002](./docs/adr/0002-stack-backend-python-fastapi.md) e do [ADR 0006](./docs/adr/0006-navegacao-macro-mapa-e-detalhe-urbano.md), o sistema evita o custo de compilação e manutenção de uma SPA (como React), concentrando lógica e testes no ecossistema Python e estruturando a camada web no padrão **MVC Web**:

- **Model (`src/core/domain/` + `src/core/services/` + `src/core/solvers/optw.py`)**: concentra estado validado, regras de negócio, invariantes temporais e algoritmos de otimização/replanejamento sem qualquer acoplamento com HTTP, sessão de servidor ou HTML.
- **View (`src/adapters/web/templates/index.html`)**: template Jinja2 servido por `GET /` com CSS nativo, Vanilla JS e mapa **Leaflet**, implementando a navegação em duas camadas do [ADR 0006](./docs/adr/0006-navegacao-macro-mapa-e-detalhe-urbano.md) (visão macro geodésica da **Viagem** e visão micro urbana do **Dia de Viagem** com controles de **Evento de Contingência** e **Deslocamento em Cascata**). Persiste o estado no navegador via `localStorage` (`kairos_trip_v1` e `kairos_trip_state_v1`, conforme [ADR 0007](./docs/adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md)) e interage com a API via `fetch`.
- **Controller (`src/adapters/web/app.py`, `contingency.py` e `backup.py`)**: recebe requisições HTTP, valida DTOs Pydantic (`OptimizeRequest`, `ReplanRequest`, `RippleShiftRequest`, `DiningRecommendRequest`, `ContextualDiningRequest`, `BudgetRequest`, `ImportLinkRequest` e `Trip`), delega ao núcleo e traduz exceções de domínio/validação em respostas HTTP (`200`, `400`, `422`).

| Grupo Funcional | Endpoints FastAPI (`src/adapters/web/app.py`) | Papel Controller → Model |
| --- | --- | --- |
| **View & Saúde** | `GET /`, `GET /health` | Renderiza `templates/index.html` via `Jinja2Templates` e expõe status operacional da aplicação. |
| **Otimização & Contingência** | `POST /api/trip/optimize`, `POST /api/trip/replan` | Executa `CurationService` + `OPTWSolver` com `urban_mode_speed_kmh`, ou `orchestrate_trip_replan` (`ReplanningService.replan`). |
| **Calendário, Gastos & Backup** | `POST /api/trip/ripple-shift/preview`, `POST /api/trip/ripple-shift/apply`, `POST /api/trip/budget`, `POST /api/trip/export-markdown`, `POST /api/trip/backup/validate` | Delega a `ScheduleService`, `DiningService`, `MarkdownExportService` e `validate_backup_payload` (HTTP 422 para campos extras ou tipos inválidos). |
| **Gastronomia & Curadoria** | `POST /api/dining/recommend`, `POST /api/dining/contextual-slots`, `GET /api/curation/suggested`, `GET /api/places/search`, `POST /api/curation/import-link` | Coordena `DiningService`, `CurationService` (`PlacesPort`) e `LinkParserService` (`UrlFetcherPort`). |

### Arquitetura Hexagonal e Contratos ARQ-1 e ARQ-2

Na **Arquitetura Hexagonal** (*Ports & Adapters*), todas as dependências apontam de fora para dentro do hexágono (`src/core/`):

- **Adaptadores Primários (*Driving / Primary*)**: residem em `src/adapters/web/`. Eles convertem eventos externos (requisições REST e ações na View HTML/JS) em chamadas sobre os serviços e solver de `src/core/`. Em `src/adapters/web/contingency.py`, o protocolo estrutural `ContingencyEventInput(Protocol)` isola a tradução dos eventos antes de alcançar `ReplanningService.replan`.
- **Portas (*Ports*)**: residem em `src/core/ports/`. `PlacesPort` abstrai fontes de **Pontos de Interesse (POIs)** e **Listas de Curadoria**; `UrlFetcherPort` abstrai busca e validação segura de URLs externas. Como os serviços (`CurationService` e `LinkParserService`) dependem apenas dessas abstrações via injeção no construtor, torna-se trivial substituir provedores reais por dublês determinísticos em testes unitários e de integração.
- **Adaptadores Secundários (*Driven / Secondary*)**: residem em `src/adapters/places/` e `src/adapters/http/`. `CachedPlacesAdapter` e `OfflineReplayPlacesAdapter` implementam `PlacesPort`; `SafeHttpFetcher` implementa `UrlFetcherPort`. A raiz de composição em `src/adapters/web/app.py` conecta os adaptadores concretos aos serviços de núcleo usando `create_places_adapter()` e `SafeHttpFetcher()`.

Essa fronteira arquitetural não é apenas conceitual — ela é **verificada automaticamente** por meio do `import-linter` (configurado em [`pyproject.toml`](./pyproject.toml)), exercitada em testes dedicados ([`tests/unit/test_hexagonal_contracts.py`](./tests/unit/test_hexagonal_contracts.py)) e imposta como bloqueio obrigatório no gate [`./verify_quality.sh`](./verify_quality.sh):

- **`ARQ-1: camadas hexagonais`** (`type = "layers"`, `containers = ["src"]`, `layers = ["adapters", "core"]`): impõe dependência estritamente unidirecional de `src.adapters` para `src.core`. Qualquer importação de `src.adapters` dentro de `src.core` viola o contrato e reprova o build.
- **`ARQ-2: núcleo sem dependências de I/O web`** (`type = "forbidden"`, `source_modules = ["src.core"]`, `forbidden_modules = ["fastapi", "uvicorn", "jinja2", "httpx", "httpcore", "requests", "sqlite3", "socket"]`, `allow_indirect_imports = false`): proíbe o uso direto ou indireto de frameworks web, clientes HTTP, sockets e SQLite dentro de `src.core`, preservando portabilidade e testabilidade pura em memória.

---

## Documentação e Decisões Arquiteturais (ADRs)

A rastreabilidade entre requisitos, vocabulário ubíquo e implementação é mantida por documentos vivos versionados no repositório:

- [`GLOSSARY.md`](./GLOSSARY.md): Vocabulário ubíquo e conceitos canônicos do domínio (25 termos oficiais e sinônimos evitados).
- [`docs/especificacao-requisitos-funcionais.md`](./docs/especificacao-requisitos-funcionais.md): Especificação formal de requisitos funcionais (`RF01` a `RF14`).
- [`docs/testing/test-plan-29119.md`](./docs/testing/test-plan-29119.md): Plano de Testes alinhado à norma ISO/IEC/IEEE 29119 e matriz de rastreabilidade.
- [`docs/HANDOFF.md`](./docs/HANDOFF.md): Documento de contexto acadêmico, estado entregue e rastreabilidade do repositório.

| ADR | Decisão Arquitetural | Alinhamento Verificado no Código (`src/`) |
| --- | --- | --- |
| [ADR 0001: Formulação do Problema como OPTW](./docs/adr/0001-formulacao-algoritmica-optw.md) | Modelagem de seleção e sequenciamento de **POIs** como OPTW em vez de TSP | `OPTWSolver` em `src/core/solvers/optw.py` (construtivo guloso + 2-opt/swap) e `POI`/`TimeWindow`/`Itinerary` em `src/core/domain/models.py` |
| [ADR 0002: Backend em Python com FastAPI e Interface Simples](./docs/adr/0002-stack-backend-python-fastapi.md) | Backend Python/FastAPI + HTML/Jinja2 + Vanilla JS + Leaflet, sem SPA | `src/adapters/web/app.py` e `src/adapters/web/templates/index.html` (MVC Web sem etapa de build Node/React) |
| [ADR 0003: Integração Google Maps com Padrão Cache-Aside](./docs/adr/0003-integracao-google-maps-com-cache.md) | Cache SQLite obrigatório isolando chamadas externas em testes e demonstrações | `PlacesPort` (`src/core/ports/places.py`) e `CachedPlacesAdapter` (`src/adapters/places/cached_adapter.py`, tabela `places_cache`) |
| [ADR 0004: Arquitetura de Viagens Multicidades e Etapas Urbanas](./docs/adr/0004-arquitetura-viagens-multicidades.md) | Hierarquia **Viagem** → **Etapas de Viagem** → **Conexões Interurbanas**, isolando OPTW urbano | `Trip`, `TripStage`, `InterCityConnection`, `TransportMode`, `UrbanMode` (`models.py`), `ScheduleService` e `InterCityRiskAlert` (`replanning.py`) |
| [ADR 0005: Isolamento de Credenciais e Modo Offline Replay](./docs/adr/0005-modo-offline-replay-credenciais.md) | Chave via `GOOGLE_MAPS_API_KEY` com fallback automático determinístico offline | `create_places_adapter` (`src/adapters/places/__init__.py`) e `OfflineReplayPlacesAdapter` (`offline_adapter.py` + `fixtures/catalog.json` para São Paulo e Lima) |
| [ADR 0006: Navegação em Duas Camadas: Mapa Macro Geodésico e Detalhe Urbano](./docs/adr/0006-navegacao-macro-mapa-e-detalhe-urbano.md) | Visão macro da **Viagem** com conexões geodésicas e visão micro urbana com timeline de contingência | `src/adapters/web/templates/index.html` + `POST /api/trip/replan` e `src/adapters/web/contingency.py` |
| [ADR 0007: Gestão de Hospedagens, Curadoria Enriquecida e Estado Client-Side](./docs/adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md) | **Dias de Viagem**, **Slots de Refeição**, parser anti-SSRF, **Deslocamento em Cascata**, `localStorage` e Markdown | `Accommodation`, `TripDay`, `MealSlot`, `CurationService`, `DiningService`, `LinkParserService`, `SafeHttpFetcher`, `ScheduleService`, `MarkdownExportService`, `validate_backup_payload` |

---

<!-- section:gof:start -->
## Padrões de Projeto GoF e Análise Anti-Overengineering

> **Seção preparada para detalhamento na entrega #120.**
>
> A arquitetura consolidada aplica cinco Padrões de Projeto GoF com foco em *Design for Change* e controle rigoroso de complexidade sintática e ciclomática (`< 10`): **Factory** (`create_places_adapter`, `TripStage.create`), **Proxy / Cache-Aside** (`CachedPlacesAdapter`), **Adapter** (`PlacesPort`, `UrlFetcherPort`, `OfflineReplayPlacesAdapter`, `SafeHttpFetcher` e adaptadores HTTP/web), **Facade** (`orchestrate_trip_replan`, `ReplanningService.replan`, `LinkParserService`, `MarkdownExportService`) e **Strategy** (seleção de velocidade por `UrbanMode` via tabela/injeção em `OPTWSolver` e implementações intercambiáveis das portas). O catálogo detalhado e a análise explícita de *trade-offs* contra *overengineering* serão expandidos nesta seção pela entrega `#120`.
<!-- section:gof:end -->

---

<!-- section:vv-iso:start -->
## Verificação & Validação, Pirâmide de Testes e Normas ISO

> **Nota:** Esta seção preserva os mecanismos automatizados de qualidade vigentes no repositório e será expandida com o guia didático completo de Verificação & Validação (V&V), Pirâmide de Testes, visões Caixa-Branca/Caixa-Preta, princípios FIRST e padrão AAA pela entrega `#121`.

O projeto adota práticas alinhadas a padrões internacionais de engenharia de software:
- **ISO/IEC 25010**: Avaliação de qualidade de produto (Adequação Funcional, Confiabilidade, Segurança, Manutenibilidade e Testabilidade via Ports & Adapters). Contratos `ARQ-1` (camadas hexagonais) e `ARQ-2` (núcleo sem dependências de I/O/web) são verificados por `import-linter`.
- **ISO/IEC/IEEE 29119**: Estruturação de processos e casos de testes formais (Unitários, Integração e Property-Based Testing com `hypothesis`); o gate `./verify_quality.sh` verifica a rastreabilidade RF × teste, a matriz com `--check` e a coerência docs-as-code em cada execução, local e no CI.
- **ISO/IEC 5055**: Métricas estáticas automatizadas (cobertura `pytest-cov ≥ 85%`, complexidade sintática `< 10` calculada por AST em `scripts/quality_cli_common.py`, complexidade ciclomática reportada por `radon`, `C901`/`PLR0911`/`PLR0912`/`PLR0913` no `ruff`, tipagem estática rigorosa com `mypy --strict`, segurança com `bandit`/`pip-audit`, volume e índice de manutenibilidade com `radon raw`/`radon mi`, código morto com `vulture` e teste de mutação com `mutmut` em `src/core/`). Inventário AST, parsers de saídas e limiares têm implementação única no módulo compartilhado; o coletor é a única fonte de cálculo.

O gate grava as saídas das ferramentas em um diretório temporário e o coletor `scripts/collect_quality_metrics.py` produz `reports/quality-metrics.json` e `reports/quality-metrics.md`, agrupando as evidências por característica da ISO/IEC 25010 e pelas métricas da ISO/IEC 5055 (quando executado isoladamente, o coletor usa `reports/tool-output/` como diretório padrão de entradas). O gate invoca o coletor com `--check`: o mesmo relatório alimenta o resumo de console e a verificação de limiares, sem parsers em `awk` ou cálculo duplicado em shell. No modo rápido o campo de mutação é registrado como **não executado**; `bash ./verify_quality.sh --full` mede o *mutation score* sem impor meta mínima nesta entrega. `pip-audit` segue política de aviso (não bloqueia o gate) para funcionar também em runner `self-hosted` com conectividade restrita; `vulture` é informativo. Os workflows de quality gate e o job `status-check` do CI Python executam em runners `[self-hosted, Linux, X64]`.

Os quatro CLIs de qualidade (`scripts/validate_traceability.py`, `scripts/generate_traceability_matrix.py`, `scripts/validate_docs_as_code.py` e `scripts/collect_quality_metrics.py`) importam `scripts/quality_cli_common.py` por importação normal: leitura UTF-8, seções `##`, resolução de caminhos, coleta de marcadores `requirement`/títulos RFxx, inventário estrutural por AST (módulos, classes, funções/métodos, docstrings e complexidade por camada), parsers das saídas estáticas, resumo e limiares têm uma única implementação, sem mutar o path de imports nem suprimir avisos de lint. Cada CLI continua disponível como `python scripts/<cli>.py ...` e também como `python -m scripts.<cli> ...`.
<!-- section:vv-iso:end -->
