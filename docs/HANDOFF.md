# Handoff — Projeto Kairos (Traçador Dinâmico de Rotas Turísticas)

**Data**: 2026-11-07  
**Repositório Remoto**: `git@github.com:lispz1610/kairos.git` (branch `main`)  
**Workspace Local**: `/home/agent/.gemini/antigravity-cli/scratch/kairos`  
**Disciplina**: DCC061 - Engenharia de Software (UFJF) — Prof. Fabrício Martins Mendonça  
**Status**: Fase de Concepção e Design Concluída (Grilling + Domain Modeling finalizados; ADRs e Glossário versionados e sincronizados no GitHub).

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
  - *Confiabilidade & Tolerância a Falhas*: Validada por Property-Based Testing (`hypothesis`) provando matematicamente que o roteiro nunca viola janelas de funcionamento ou disponibilidade, e pelos 4 eventos de contingência (atraso, fechamento, pular parada, alteração de permanência).
  - *Manutenibilidade & Testabilidade*: Arquitetura Hexagonal (Ports & Adapters) garantindo desacoplamento do core algorítmico contra I/O.
- **ISO/IEC/IEEE 29119 (Testes de Software)**:
  - Estruturação do plano de testes e especificação formal de casos de teste no relatório técnico.
- **ISO/IEC 5055 (Métricas de Código Automatizadas)**:
  - Cobertura de código `pytest-cov ≥ 85%`.
  - Complexidade ciclomática `< 10` por função (`radon`).
  - Tipagem estática rigorosa (`mypy --strict`).
  - Linting e formatação PEP 8 / PEP 257 (`ruff`).

---

## 4. Estado Atual do Repositório

O repositório `lispz1610/kairos` na branch `main` contém:
```
kairos/
├── .gitignore
├── README.md
├── GLOSSARY.md
└── docs/
    ├── HANDOFF.md
    └── adr/
        ├── 0001-formulacao-algoritmica-optw.md
        ├── 0002-stack-backend-python-fastapi.md
        ├── 0003-integracao-google-maps-com-cache.md
        ├── 0004-arquitetura-viagens-multicidades.md
        ├── 0005-modo-offline-replay-credenciais.md
        └── 0006-navegacao-macro-mapa-e-detalhe-urbano.md
```

---

## 5. Próximos Passos Imediatos para o Próximo Agente

1. **Configuração do Projeto Python**:
   - Inicializar ambiente com `pyproject.toml` (Poetry) ou `requirements.txt` + `requirements-dev.txt`.
   - Dependências principais: `fastapi`, `uvicorn`, `jinja2`, `sqlmodel` (ou `sqlalchemy`), `pydantic`, `pydantic-settings`, `httpx`.
   - Dependências de teste e qualidade: `pytest`, `pytest-cov`, `hypothesis`, `mutmut`, `mypy`, `ruff`, `radon`.

2. **Implementação do Domínio Puro (`src/core/domain/`) via TDD**:
   - `models.py`: `POI`, `TimeWindow`, `Itinerary`, `Trip`, `TripStage`, `InterCityConnection`, `UserPreferences`.
   - `events.py`: Modelos dos 4 eventos de contingência (`DelayEvent`, `ClosureEvent`, `SkipStopEvent`, `DurationAdjustmentEvent`).

3. **Implementação do Solver OPTW (`src/core/solvers/`)**:
   - Heurística construtiva de inserção gulosa ponderada pela `Pontuação de Utilidade` / `Custo Marginal de Tempo`.
   - Busca local 2-opt e swap de paradas.
   - Motor de contingência: recálculo a partir do ponto/horário corrente e alerta de risco de voo.

4. **Testes de Propriedades (`tests/property/`)**:
   - Estratégias `hypothesis` validando invariantes universais (nenhum ponto visitado fora do horário, tempo total dentro da janela).

5. **Adapters Google Maps & Cache (`src/adapters/`)**:
   - Porta `GeoRoutingPort` abstrata.
   - Adaptador real Google Maps com cache SQLite.
   - Adaptador `MockReplay` com fixtures pré-gravadas para São Paulo, Lima e Juiz de Fora.

6. **Web App & UI Simples (`src/adapters/web/`)**:
   - FastAPI rotas e templates Jinja2.
   - Tela 1: Mapa macro (Leaflet) com cidades cadastradas conectadas por linhas geodésicas retas.
   - Tela 2: Detalhe urbano em 2 colunas (Timeline com botões de contingência à esquerda + Rota Leaflet à direita).

7. **Script de Automação de Qualidade**:
   - `verify_quality.sh` executando `ruff`, `mypy --strict`, `radon cc`, `pytest --cov` e gerando relatório de conformidade ISO.

---

## 6. Habilidades Sugeridas (Suggested Skills)

Para a continuidade dos trabalhos, o próximo agente deve utilizar:
- **`tdd`** (`/home/agent/.gemini/config/skills/tdd/SKILL.md`): Conduzir a implementação das entidades de domínio, validador de janelas e solver OPTW estritamente via Test-Driven Development (Red-Green-Refactor).
- **`domain-modeling`** (`/home/agent/.gemini/config/skills/domain-modeling/SKILL.md`): Manter o `GLOSSARY.md` e ADRs sincronizados caso surjam novos termos ou decisões técnicas durante a implementação.
- **`code-review`** (`/home/agent/.gemini/config/skills/code-review/SKILL.md`): Verificar a aderência do código às métricas da ISO 25010 e padrões PEP antes de consolidar marcos no Git.
