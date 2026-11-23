# Kairos — Traçador Dinâmico de Rotas Turísticas

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Engenharia de Software](https://img.shields.io/badge/UFJF-DCC061-red.svg)](https://www.ufjf.br/)
[![Standards](https://img.shields.io/badge/standards-ISO%2FIEC%2025010%20%7C%2029119-green.svg)](https://www.iso.org/)

**Kairos** é um sistema de planejamento e otimização dinâmica de itinerários turísticos multicidades com restrições temporais e espaciais do mundo real.

Desenvolvido para o Trabalho Prático da disciplina **DCC061 - Engenharia de Software** do Departamento de Ciência da Computação da **Universidade Federal de Juiz de Fora (UFJF)**, com foco aprofundado nos temas de **Testes de Software** e **Qualidade de Software**.

---

## 🎯 Objetivos Centrais

- **Otimização de Roteiro via OPTW**: Modela o planejamento urbano como uma variação do *Orienteering Problem with Time Windows* (OPTW), maximizando o valor de atratividade turística dentro da janela de disponibilidade do usuário e horários de funcionamento das atrações.
- **Viagens Multicidades**: Estrutura jornadas hierárquicas compostas por etapas urbanas interligadas por conexões interurbanas (`flying`, `driving`).
- **Adaptação Dinâmica em Tempo Real**: Simulação de eventos de contingência (atrasos, fechamento repentino, pular atração, ajuste de permanência) com replanejamento automático e detecção de efeito cascata em voos.
- **Resiliência e Cache-Aside**: Integração exclusiva com Google Maps Platform (Places e Routes) com persistência em cache SQLite e modo Offline Replay transparente.

---

## 📚 Documentação e Decisões de Design

- 📖 **[GLOSSARY.md](./GLOSSARY.md)**: Vocabulário ubíquo e conceitos canônicos do domínio.
- 🏛️ **Decisões Arquiteturais (ADRs)**:
  - [ADR 0001: Formulação do Problema como OPTW](./docs/adr/0001-formulacao-algoritmica-optw.md)
  - [ADR 0002: Backend em Python com FastAPI e Interface Simples](./docs/adr/0002-stack-backend-python-fastapi.md)
  - [ADR 0003: Integração Google Maps com Padrão Cache-Aside](./docs/adr/0003-integracao-google-maps-com-cache.md)
  - [ADR 0004: Arquitetura de Viagens Multicidades e Etapas Urbanas](./docs/adr/0004-arquitetura-viagens-multicidades.md)
  - [ADR 0005: Isolamento de Credenciais e Modo Offline Replay](./docs/adr/0005-modo-offline-replay-credenciais.md)
  - [ADR 0006: Navegação em Duas Camadas: Mapa Macro Geodésico e Detalhe Urbano](./docs/adr/0006-navegacao-macro-mapa-e-detalhe-urbano.md)
  - [ADR 0007: Gestão de Hospedagens, Curadoria Enriquecida e Estado Client-Side](./docs/adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md)

---

## 🛡️ Engenharia de Qualidade e Normas ISO

O projeto adota práticas alinhadas a padrões internacionais de engenharia de software:
- **ISO/IEC 25010**: Avaliação de qualidade de produto (Adequação Funcional, Tolerância a Falhas e Testabilidade via Ports & Adapters).
- **ISO/IEC/IEEE 29119**: Estruturação de processos e casos de testes formais (Unitários, Integração e Property-Based Testing com `hypothesis`); o gate `./verify_quality.sh` verifica a rastreabilidade RF × teste, a matriz com `--check` e a coerência docs-as-code em cada execução, local e no CI.
- **ISO/IEC 5055**: Métricas estáticas automatizadas (cobertura `pytest-cov ≥ 85%`, complexidade ciclomática `< 10` com `radon`, tipagem estática rigorosa com `mypy --strict`, estilo/docstrings com `ruff` e teste de mutação com `mutmut` em `src/core/`), consolidadas pelo gate `./verify_quality.sh` (`--full` para incluir mutação).

Os três CLIs de qualidade (`scripts/validate_traceability.py`, `scripts/generate_traceability_matrix.py` e `scripts/validate_docs_as_code.py`) importam `scripts/quality_cli_common.py` por importação normal: leitura UTF-8, seções `##`, resolução de caminhos e coleta de marcadores `requirement`/títulos RFxx têm uma única implementação, sem mutar o path de imports nem suprimir avisos de lint. Cada CLI continua disponível como `python scripts/<cli>.py ...` e também como `python -m scripts.<cli> ...`.
