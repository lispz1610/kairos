# Plano de Testes ISO/IEC/IEEE 29119 — Kairos

**Normas de referência**: ISO/IEC/IEEE 29119-2 (Processo de Teste de Software) e ISO/IEC/IEEE 29119-3 (Documentação de Teste).
**Alinhamento complementar**: ISO/IEC 25010 (Adequação Funcional, Confiabilidade, Segurança e Usabilidade), ISO/IEC 5055 (Qualidade Estrutural de Código).
**Vocabulário canônico**: [GLOSSARY.md](../../GLOSSARY.md). Todo termo de domínio abaixo (Viagem, Etapa de Viagem, Dia de Viagem, Hospedagem, Dia de Troca de Hospedagem, Conexão Interurbana, Ponto de Interesse, Roteiro, Janela de Disponibilidade, Janela de Funcionamento, Tempo de Permanência, Matriz de Deslocamento, Pontuação de Utilidade, Perfil de Preferência, Slot de Refeição, Estimativa de Gastos, Evento de Contingência, Replanejamento, Deslocamento em Cascata) é empregado no sentido definido no glossário.
**Requisitos rastreados**: [Especificação de Requisitos Funcionais](../especificacao-requisitos-funcionais.md), RF01–RF08.
**Decisões arquiteturais relacionadas**: [ADR 0001](../adr/0001-formulacao-algoritmica-optw.md) (OPTW), [ADR 0002](../adr/0002-stack-backend-python-fastapi.md) (FastAPI e HTML/Vanilla JS), [ADR 0004](../adr/0004-arquitetura-viagens-multicidades.md), [ADR 0005](../adr/0005-modo-offline-replay-credenciais.md) (Offline Replay), [ADR 0007](../adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md).

---

## 1. Escopo

Este plano cobre a verificação do Kairos nos níveis de teste automatizado presentes no repositório, com rastreabilidade explícita dos requisitos funcionais RF01–RF08 aos casos de teste reais em `tests/unit/`, `tests/integration/` e `tests/property/`.

**Em escopo**

- Domain model e invariantes temporais de Viagem, Etapa de Viagem, Dia de Viagem, Dia de Troca de Hospedagem e Conexão Interurbana (`src/core/domain/models.py`).
- Solver OPTW e a otimização do Roteiro dentro da Janela de Disponibilidade, respeitando Slots de Refeição e deslocamentos (`src/core/solvers/optw.py`).
- Serviços de Perfil de Preferência, Curadoria, Parser Seguro de Links, Refeições/Estimativa de Gastos, Deslocamento em Cascata, Replanejamento e Exportação em Markdown (`src/core/services/`).
- Eventos de Contingência tipados e a orquestração HTTP do Replanejamento (`src/core/domain/events.py`, `src/adapters/web/contingency.py`, `POST /api/trip/replan`).
- Adaptadores HTTP e de Ponto de Interesse, incluindo proteção SSRF, Modo Offline Replay e cache (`src/adapters/`).
- Interface web FastAPI e o template `src/adapters/web/templates/index.html`.
- Gate de qualidade `verify_quality.sh`, validadores docs-as-code/de rastreabilidade e coletor de métricas ISO (`scripts/`), com contratos arquiteturais verificados por `import-linter`, utilitário compartilhado `scripts/quality_cli_common.py` e testes de CLI em `tests/unit/`.

**Fora de escopo (declarado)**

- Testes de interface gráfica em navegador real (Selenium/Playwright); conforme ADR 0002, a camada web é verificada por contratos HTTP (`TestClient`) e por asserções sobre a estrutura do HTML servido, sem automação E2E.
- Testes de carga, desempenho e penetração automatizados.
- Execução da persistência client-side (leitura/escrita em `localStorage`) dentro do navegador. Estão em escopo os contratos HTTP e a estrutura HTML que declara chaves, controles, ações, endpoints e mensagens dos fluxos de Deslocamento em Cascata e Backup JSON; nenhum teste lê ou escreve `localStorage` (§5.5, §8). A interação real em navegador permanece registrada como lacuna parcial em §8.

---

## 2. Estratégia em camadas

A estratégia segue o modelo em camadas da ISO/IEC/IEEE 29119-2, com pirâmide invertida em direção à maior retroalimentação:

| Camada | Diretório | Objetivo principal | Técnica dominante |
| --- | --- | --- | --- |
| **Unitário** | `tests/unit/` | Invariantes de domínio, regras de serviço e cálculos determinísticos isolados de I/O. | Particionamento em classes de equivalência, análise de valor limite, parametrização. |
| **Integração** | `tests/integration/` | Contratos HTTP da aplicação FastAPI (inclusive `POST /api/trip/replan`, prévia/aplicação do Deslocamento em Cascata e `POST /api/trip/backup/validate`), contratos estruturais do HTML servido, composição solver + adaptadores + serviços, Offline Replay. | Casos de teste de interface (request/response), asserções de estrutura HTML, partições de entrada inválidas. |
| **Propriedade** | `tests/property/` | Invariantes universais que devem valer para qualquer entrada gerada. | Property-Based Testing com `hypothesis`. |
| **Mutação** | `src/core/` (alvo) | Avaliar a força das camadas anteriores por mutantes sobreviventes. | Teste de Mutação com `mutmut` (modo `--full`). |
| **Qualidade estática** | `scripts/` + `pyproject.toml` | Medir cobertura, complexidade, manutenibilidade, segurança e contratos arquiteturais, consolidando evidências ISO 25010/5055. | `ruff`/`mypy`/`radon`/`bandit`/`vulture`/`pip-audit`/`import-linter` e coletor JSON/Markdown. |
| **Docs-as-code** | `scripts/` + `tests/unit/` | Verificar coerência entre documentação, código e matriz de rastreabilidade. | Testes de CLI com árvores isoladas (`tmp_path`) e execução dos validadores. |

A camada de mutação não produz casos de teste novos: ela pontua a qualidade das demais. Um mutante sobrevivente em `src/core/` é tratado como um defeito de cobertura a ser corrigido com um novo caso de teste nas camadas unitária ou de propriedade.

---

## 3. Critérios de entrada e saída

### 3.1 Critérios de entrada (entry criteria)

- Código-fonte e testes presentes no worktree, com dependências de desenvolvimento instaladas (`pytest`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`, `radon`, `mutmut`, `import-linter`, `bandit`, `pip-audit`, `vulture`).
- Requisitos RF01–RF08 e vocabulário canônico disponíveis para derivação de casos de teste.
- Variável `GOOGLE_MAPS_API_KEY` **ausente** para execução determinística em Modo Offline Replay (ADR 0005); quando presente, a suíte deve continuar independente de rede via injeção de portas.
- Ambiente Python 3.12 (alvo de `ruff`/`mypy`) e `PYTHONPATH` com a raiz do repositório.

### 3.2 Critérios de saída (exit criteria)

O gate unificado `verify_quality.sh` define a condição de conclusão:

1. `ruff check src tests` sem violações (estilo, imports e docstrings PEP 257).
2. `mypy --strict src` sem erros de tipagem.
3. `radon cc src` como artefato e inventário AST do coletor sem função/método com complexidade sintática `> 9` (limite `< 10`), avaliado por `scripts/collect_quality_metrics.py --check`.
4. `pytest --cov=src --cov-report=term-missing --cov-fail-under=85` com cobertura `>= 85%`.
5. No modo `--full`, `mutmut` executado sobre `src/core/`, com mutation score consolidado e contagem de mutantes sobreviventes. Critério de monitoramento/evidência, não uma checagem automática: o `verify_quality.sh --full` reporta o score e os sobreviventes sem impor threshold; a equipe registra na revisão a justificativa de cada sobrevivente e decide pela conversão em novos casos de teste (§5.4).
6. Rastreabilidade RF × teste (§7) com RF01–RF08 integralmente cobertos por ao menos um caso de teste existente, verificada pelo gate com `python scripts/validate_traceability.py --spec docs/especificacao-requisitos-funcionais.md --root .` e pela matriz com `python scripts/generate_traceability_matrix.py --plan docs/testing/test-plan-29119.md --spec docs/especificacao-requisitos-funcionais.md --root . --check`. Validador e gerador compartilham a coleta de marcadores e títulos em `scripts/quality_cli_common.py`, por importação normal do módulo.
7. Coerência docs-as-code, verificada pelo gate com `python scripts/validate_docs_as_code.py --plan docs/testing/test-plan-29119.md --handoff docs/HANDOFF.md --root .`, com Eventos de Contingência, Replanejamento e `verify_quality.sh` descritos como entregues.
8. `lint-imports` sem contratos rompidos: `ARQ-1` proíbe `src.core` → `src.adapters` e `ARQ-2` proíbe dependências de I/O/web no núcleo.
9. `bandit -q -r src -ll -s B104` sem achados de severidade média ou alta (o B104 é documentado como denylist anti-SSRF); `pip-audit -l` segue política de aviso, não bloqueio, em runner `self-hosted` com conectividade restrita.
10. `vulture` e `radon mi`/`radon raw` executados: `vulture` é informativo e o coletor registra saídas ausentes como `unavailable`, em vez de inventar zeros.
11. `scripts/collect_quality_metrics.py` gera `reports/quality-metrics.json` e `reports/quality-metrics.md`, agrupando evidências por característica da ISO/IEC 25010 e métrica da ISO/IEC 5055, com inventário estrutural por AST (módulos, classes, funções/métodos, docstrings e complexidade por camada) e parsers de saídas centralizados em `scripts/quality_cli_common.py`. O gate chama o coletor com `--check`, que imprime o resumo consolidado e aplica os limiares a partir do mesmo relatório, sem regex/awk duplicados. No modo rápido o mutation score é registrado como `not run`; no modo `--full` é preenchido somente quando o `mutmut` foi medido, sem threshold fixo.

O gate `verify_quality.sh` está entregue e é executado antes de cada commit/PR; os validadores dos itens 6 e 7 passaram a integrar o gate rápido na issue #86, os itens 8–11 integram a issue #65 e a consolidação do inventário AST, dos parsers, do resumo e dos limiares no módulo compartilhado/coletor integra a issue #106. Todas as etapas são executadas uma única vez, também pelo workflow de quality gate em cada pull request. Qualquer falha nas verificações automatizadas acima bloqueia o merge, conforme o gate de qualidade do issue-pai #19; o item 5, a parte de `pip-audit` do item 9 e o item 10 são monitoramento/evidência, sem threshold automático.

---

## 4. Ambiente Offline Replay

Conforme ADR 0005, a chave `GOOGLE_MAPS_API_KEY` é injetada apenas por variável de ambiente. Na ausência dela, o adaptador de Ponto de Interesse entra em **Modo Offline Replay**, servindo dados pré-gravados para as cidades de demonstração (São Paulo, Lima, Juiz de Fora). Isso garante que:

- a suíte rode com **zero credenciais** e **zero conectividade externa**;
- a banca examinadora reproduza os mesmos resultados da CI;
- nenhuma cota ou custo de API seja consumido durante os testes.

Evidências do modo nos testes: `tests/unit/test_curation_service.py` (`test_offline_replay_adapter_curated_lists`, `test_offline_replay_adapter_search_places`, `test_cached_places_adapter_cache_aside_sqlite`, `test_create_places_adapter_factory`) e `tests/integration/test_curation_api.py` (`test_cache_persistence_and_offline_replay`).

**Nota de isolamento**: o cache SQLite do adaptador é global por padrão em produção. Os testes de integração do adaptador de lugares injetam um banco em `tmp_path` exclusivo por caso, preservando a repetibilidade (FIRST).

---

## 5. Especificação formal de casos de teste e técnicas aplicadas

A especificação abaixo documenta as técnicas exigidas pela ISO/IEC/IEEE 29119-3 com exemplos concretos do Kairos. Cada caso identifica a técnica, a entrada, o resultado esperado e o arquivo de teste que o materializa.

### 5.1 Particionamento em classes de equivalência

Técnica que divide o domínio de entrada em classes cujos elementos produzem o mesmo comportamento, reduzindo a infinitude de entradas a representantes testáveis.

**Exemplo Kairos — perfis alimentares (RF07).** O domínio `food_profile` é particionado em três classes válidas (`budget`, `moderate`, `fine_dining`), cada uma com valor diário esperado distinto (R$ 80, R$ 180, R$ 400), mais a classe dos membros `enum` equivalentes. O caso `test_budget_calculation_varies_by_food_profile` em `tests/unit/test_dining_and_budget.py` parametriza as seis variantes (enum e string), confirmando que cada representante da classe produz o mesmo total — e que classes diferentes produzem totais diferentes.

**Exemplo Kairos — categorias de Perfil de Preferência (RF04).** `test_all_six_preference_categories_modulate_utility` em `tests/unit/test_preferences_service.py` cobre as seis classes temáticas canônicas (Coffee, Wine, Museum, Nature, Gastronomy & Fine Dining, Street Food), verificando que cada categoria modula a Pontuação de Utilidade.

**Exemplo Kairos — URLs proibidas (RF05).** `test_import_link_ssrf_protection_returns_400` em `tests/integration/test_import_link_api.py` e `test_ssrf_validator_blocks_forbidden_urls` em `tests/unit/test_link_parser_service.py` agrupam em uma classe de equivalência os esquemas e hosts proibidos (`file://`, `ftp://`, loopback `127.0.0.1`/`localhost`, redes privadas `10.0.0.0/8`, `192.168.0.0/16`), esperando rejeição HTTP 400/validação negativa para todos os representantes.

### 5.2 Análise de valor limite

Técnica que testa os valores nas fronteiras das classes de equivalência (mínimo, máximo, imediatamente abaixo/acima), onde defeitos de offset são mais prováveis.

**Exemplo Kairos — intensidade do Perfil de Preferência (RF04).** A escala canônica é 0–10, com gatilho de slot temático em `>= 5`. A fronteira 5 é o ponto crítico: `test_contextual_dining_slots_includes_thematic_slots_at_intensity_five` em `tests/integration/test_dining_api.py` verifica o disparo da Pausa para Café e do slot de Wine Bar exatamente no limite. `test_preference_intensity_modulates_utility` complementa com o comportamento nos extremos da escala.

**Exemplo Kairos — quantidade de POIs e variáveis climáticas (RF03/RF01).** Em `tests/property/test_optw_properties.py`, as estratégias `st.integers(min_value=1, max_value=8)` fixam o limite inferior (1 POI) e superior (8 POIs) do domínio gerado, enquanto `st.floats(min_value=-23.6, max_value=-23.5)` delimita as coordenadas da amostra de São Paulo. `test_budget_calculation_varies_by_travelers_count` em `tests/unit/test_dining_and_budget.py` parametriza `{1, 2, 4}` viajantes, cobrindo o mínimo e valores acima dele.

**Exemplo Kairos — tamanho da Janela de Disponibilidade.** A asserção `itinerary.total_duration_minutes <= window.duration_minutes` em `test_optw_itinerary_never_exceeds_availability_window` (`tests/property/test_optw_properties.py`) verifica explicitamente o limite superior da janela (9h = 540 min), além dos limites de chegada (`>= start_time`) e partida (`<= end_time`).

### 5.3 Property-Based Testing (`hypothesis`)

Técnica que gera entradas arbitrárias e verifica invariantes que devem valer para **todas** elas, muito mais forte que exemplos pontuais para lógica temporal e de otimização.

**Exemplo Kairos — invariantes do solver OPTW (RF03/RF01).** `tests/property/test_optw_properties.py` contém dois casos formais:

- `test_optw_itinerary_never_exceeds_availability_window`: para quaisquer coordenadas de partida/retorno e de 1 a 8 POIs, o Roteiro nunca excede a Janela de Disponibilidade e nenhuma visita a Ponto de Interesse fica fora dela.
- `test_optw_itinerary_never_collides_with_reserved_slots`: com combinações booleanas de café/vinho e Slots de Refeição reservados, prova que nenhuma visita a Ponto de Interesse sobrepõe um slot reservado — a invariante é expressa como `max(início_visita, início_slot) < min(fim_visita, fim_slot)` deve ser sempre falsa.

**Exemplo Kairos — monotonicidade do Perfil de Preferência (RF04).** `test_preference_monotonicity_property` em `tests/property/test_preferences_properties.py` estabelece que aumentar a intensidade de uma categoria nunca diminui a Pontuação de Utilidade correspondente.

**Exemplo Kairos — invariantes do Deslocamento em Cascata e round-trip (RF06/RF01/RF08).** `test_ripple_shift_invariants` e `test_trip_json_round_trip_idempotence` em `tests/property/test_ripple_shift_properties.py` provam, respectivamente, que estender uma Etapa de Viagem em $+N$ dias propaga exatamente $+N$ para etapas e Conexões Interurbanas subsequentes sem duplicar POIs, e que serializar/desserializar uma Viagem é idempotente.

### 5.4 Teste de Mutação (`mutmut`)

Técnica de avaliação da eficácia dos testes: `mutmut` aplica mutações no código de produção (troca de operadores, constantes, condicionais) e verifica se a suíte "mata" o mutante (falha). Mutantes sobreviventes indicam lacunas de asserção invisíveis à cobertura de linhas.

**Aplicação no Kairos.** Executado no modo `--full` do gate sobre `src/core/` — o núcleo de domínio, solver OPTW e serviços. Os alvos de maior valor são justamente os pontos com asserções de invariante: `src/core/solvers/optw.py` (comparações de tempo, cálculo de janela, bloqueio de slots) e `src/core/services/schedule.py` (cálculo de deslocamento em cascata). Cada mutante sobrevivente nestes módulos deve ser convertido em um novo caso de teste nas camadas unitária/de propriedade descritas acima, fechando o ciclo red→green.

### 5.5 Contratos HTTP e de estrutura HTML (RF06/RF08)

Para os fluxos de Deslocamento em Cascata e Backup JSON, a verificação combina requisições `TestClient` (status 200/400/422, datas anteriores e recalculadas, rejeição de campos desconhecidos e escalares com tipo incompatível, normalização de strings ISO e idempotência da Viagem) com asserções sobre o HTML servido: presença do painel de planejamento, do Modal de Confirmação de Impacto e dos controles de Backup JSON; atributos estáveis (`data-action`, `data-endpoint`, `data-persist-trip`, `data-impact-field`, `data-role`); rótulos visíveis canônicos e o catálogo de mensagens exibidas no banner. O teste de vocabulário inspeciona esses rótulos e mensagens contra o `GLOSSARY.md`. A técnica observa apenas contratos externos — não variáveis internas, ordem de instruções JavaScript, detalhes de manipulação de DOM ou conteúdo de `localStorage` — e não depende de navegador real (ADR 0002); a lacuna parcial correspondente está em §8.

### 5.6 Eventos de Contingência e Replanejamento

Técnica: classes de equivalência sobre os quatro tipos de Evento (`delay`, `closure`, `skip`, `duration_adjustment`) e contratos HTTP de `POST /api/trip/replan`. Os Eventos de Domínio em `src/core/domain/events.py` são validados em `tests/unit/test_events.py`; a conversão para entradas de Replanejamento é exercitada em `tests/unit/test_apply_contingency_event.py` e `tests/unit/test_adapters_web_app.py`; o recálculo do Roteiro restante a partir da coordenada/horário atuais, a preservação de paradas passadas e de Slots de Refeição futuros, o teto da Conexão Interurbana e o alerta de risco são verificados em `tests/unit/test_replanning_service.py` e `tests/integration/test_trip_replan_endpoint.py`. A interação dos controles na timeline em navegador real é registrada como lacuna parcial em §8.

### 5.7 Validação docs-as-code e gate de qualidade

Técnica: testes de CLI com documentos e árvore de código isolados por `tmp_path`, além de teste de integração do gate com ferramentas externas simuladas. `tests/unit/test_docs_as_code_validator.py` verifica que o validador aceita lacunas parciais de navegador e rejeita afirmações de ausência total quando os artefatos estão presentes; `tests/unit/test_traceability_matrix_generator.py` verifica geração/verificação da matriz a partir dos marcadores `requirement`; `tests/unit/test_quality_gate_validators.py` comprova que divergências propositais em marcadores, matriz, documentação e limiares derrubam o gate sem alterar o repositório; `tests/unit/test_quality_cli_shared_imports.py` cobre a importação compartilhada, a não mutação de path/supressão de lint, a unicidade de parsers/limiares e a execução dos quatro CLIs como script e como módulo. `tests/unit/test_quality_metric_contracts.py` exercita o inventário AST e os parsers/limiares com código e saídas sintéticas; `tests/unit/test_collect_quality_metrics.py` valida o coletor JSON/Markdown, o resumo/limiares de `--check`, incluindo mutação `not run` no modo rápido, ausências `unavailable` e leitura do JSON do mutmut no modo `--full`; `tests/unit/test_hexagonal_contracts.py` monta uma árvore mínima com casos válidos e violações de `ARQ-1`/`ARQ-2` para o `import-linter`. O script `verify_quality.sh` automatiza `ruff`, `mypy --strict`, `radon cc`, `pytest --cov`, os validadores de rastreabilidade (incluindo `--check` da matriz), o validador docs-as-code, os contratos arquiteturais, `bandit`, `vulture`, `radon mi/raw`, `pip-audit` (aviso) e a coleta ISO 25010/5055 com `--check` (resumo, inventário AST e limiares), com estágio opcional de mutação, sendo executado como gate antes de commits e PRs e no CI.

---

## 6. Casos de teste — resumo por técnica

| ID do caso | Técnica | Requisito | Arquivo / função |
| --- | --- | --- | --- |
| CT-DOM-01 | Classes de equivalência | RF01 | `tests/unit/test_domain_trip.py::test_trip_stage_days_generation_with_base_hotel` |
| CT-DOM-02 | Valor limite / transição | RF02 | `tests/unit/test_domain_trip.py::test_trip_stage_custom_hotel_override_and_transition_detection` |
| CT-OPTW-01 | Property-Based | RF03 | `tests/property/test_optw_properties.py::test_optw_itinerary_never_exceeds_availability_window` |
| CT-OPTW-02 | Property-Based | RF03 | `tests/property/test_optw_properties.py::test_optw_itinerary_never_collides_with_reserved_slots` |
| CT-PREF-01 | Valor limite (`>= 5`) | RF04 | `tests/unit/test_preferences_service.py::test_thematic_slots_generation_for_coffee_and_wine_lovers` |
| CT-PREF-02 | Property-Based (monotonicidade) | RF04 | `tests/property/test_preferences_properties.py::test_preference_monotonicity_property` |
| CT-CUR-01 | Classes de equivalência | RF05 | `tests/integration/test_import_link_api.py::test_import_link_ssrf_protection_returns_400` |
| CT-RIPPLE-01 | Invariante / Property-Based | RF06 | `tests/property/test_ripple_shift_properties.py::test_ripple_shift_invariants` |
| CT-RIPPLE-02 | Contrato HTTP (prévia, datas anteriores/recalculadas, deltas ±) | RF06 | `tests/integration/test_schedule_api.py::test_ripple_shift_preview_endpoint`, `::test_ripple_shift_preview_exposes_old_and_new_dates_for_negative_delta`, `::test_ripple_shift_apply_matches_preview_dates_for_positive_delta` |
| CT-RIPPLE-03 | Contrato HTTP (aplicação, persistência no servidor e rejeições) | RF06 | `tests/integration/test_schedule_api.py::test_ripple_shift_apply_endpoint`, `::test_ripple_shift_apply_rejects_unknown_stage_without_server_state`, `::test_ripple_shift_apply_rejects_shrink_that_eliminates_stage` |
| CT-RIPPLE-04 | Contrato HTML (prévia, modal, ações, persistência declarada, banner) | RF06 | `tests/integration/test_web_app.py::test_index_page_exposes_trip_planning_section`, `::test_index_page_exposes_impact_confirmation_modal`, `::test_index_page_declares_ripple_actions_and_persistence_intent`, `::test_index_page_declares_user_facing_error_messages` |
| CT-RIPPLE-05 | Contrato HTTP (corpo único de prévia/aplicação, identificação da Conexão e hora de partida) | RF06 | `tests/integration/test_schedule_api.py::test_ripple_shift_preview_and_apply_share_one_request_shape` |
| CT-BUD-01 | Classes de equivalência | RF07 | `tests/unit/test_dining_and_budget.py::test_budget_calculation_varies_by_food_profile` |
| CT-EXP-01 | Round-trip / serialização | RF08 | `tests/property/test_ripple_shift_properties.py::test_trip_json_round_trip_idempotence` |
| CT-BKP-01 | Contrato HTTP (200/422, campos desconhecidos, tipos estritos, strings ISO e idempotência) | RF08 | `tests/integration/test_trip_backup_api.py::test_backup_validate_returns_validated_trip_and_is_idempotent`, `::test_backup_validate_rejects_unknown_fields_and_untyped_numbers`, `::test_backup_validate_rejects_payload_without_required_trip_id`, `::test_backup_validate_rejects_incomplete_stage_and_connection`, `::test_backup_validate_rejects_invalid_field_types`, `::test_backup_validate_rejects_non_object_body` |
| CT-BKP-02 | Contrato HTML (exportar/restaurar, endpoint, mensagens no banner) | RF08 | `tests/integration/test_web_app.py::test_index_page_exposes_json_backup_controls`, `::test_backup_restore_controls_declare_picker_and_change_trigger`, `::test_backup_restore_success_contract_uses_validated_trip_and_render_targets`, `::test_backup_restore_failure_contract_keeps_trip_and_reports_in_banner`, `::test_index_page_declares_user_facing_error_messages` |
| CT-VOC-01 | Estrutura / vocabulário canônico | RF06, RF08 | `tests/unit/test_index_html_vocabulary.py::test_index_html_new_flow_sections_use_canonical_vocabulary`, `::test_index_html_new_flow_scripts_use_canonical_vocabulary` (e `::test_index_html_card_title_uses_canonical_vocabulary`, #59) |
| CT-CONT-01 | Classes de equivalência / contrato HTTP | Extensão dinâmica (RF10/RF13) | `tests/unit/test_events.py`, `tests/unit/test_apply_contingency_event.py`, `tests/unit/test_adapters_web_app.py` |
| CT-REPL-01 | Invariante / contrato HTTP | Extensão dinâmica (RF12/RF13) | `tests/unit/test_replanning_service.py`, `tests/integration/test_trip_replan_endpoint.py` |
| CT-QUAL-01 | Docs-as-code / matriz / gate | Qualidade | `tests/unit/test_docs_as_code_validator.py`, `tests/unit/test_traceability_matrix_generator.py`, `tests/unit/test_quality_gate_validators.py`, `verify_quality.sh` |
| CT-QUAL-02 | Contratos arquiteturais / coleta ISO 25010 + ISO 5055 | Qualidade | `tests/unit/test_hexagonal_contracts.py`, `tests/unit/test_collect_quality_metrics.py`, `tests/unit/test_quality_metric_contracts.py`, `tests/unit/test_quality_cli_shared_imports.py`, `scripts/collect_quality_metrics.py`, `scripts/quality_cli_common.py` |

---

## 7. Matriz de Rastreabilidade RF01–RF08 × testes

Cada requisito é ligado a arquivos e casos de teste **existentes** no worktree. Caminhos em `tests/` e `src/` foram verificados quanto à existência.
A matriz é gerada por `python scripts/generate_traceability_matrix.py --plan docs/testing/test-plan-29119.md --spec docs/especificacao-requisitos-funcionais.md --root .` (equivalente a `python -m scripts.generate_traceability_matrix` com os mesmos argumentos); o gerador reutiliza a coleta de marcadores do módulo compartilhado e o gate rápido executa essa geração com `--check`, sem gravar (issues #83, #86 e #94).

| RF | Requisito | Testes unitários | Testes de integração | Testes de propriedade | Código de produção relacionado |
| --- | --- | --- | --- | --- | --- |
| **RF01** | Decomposição em Dias de Viagem e Hospedagem Dinâmica | `tests/unit/test_domain_trip.py` — `test_accommodation_creation_and_coordinates`, `test_deserialized_trip_relinks_previous_day_accommodations_for_transition_detection`, `test_trip_stage_custom_hotel_override_and_transition_detection`, `test_trip_stage_days_generation_with_base_hotel`; `tests/unit/test_optw_solver.py` — `test_optw_solver_respects_time_budget_and_depots` | — | `tests/property/test_ripple_shift_properties.py` — `test_ripple_shift_invariants`, `test_trip_json_round_trip_idempotence` | `src/core/domain/models.py` |
| **RF02** | Gestão de Transição de Hospedagem (Dia de Troca) | `tests/unit/test_domain_trip.py` — `test_deserialized_trip_relinks_previous_day_accommodations_for_transition_detection`, `test_trip_stage_custom_hotel_override_and_transition_detection`; `tests/unit/test_markdown_export.py` — `test_markdown_export_relinks_deserialized_trip_accommodations`, `test_markdown_export_service_structure` | — | `tests/property/test_ripple_shift_properties.py` — `test_trip_json_round_trip_idempotence` | `TripDay.is_transition_day` em `src/core/domain/models.py` |
| **RF03** | Slots de Refeição e Pausas Experienciais Contextuais | `tests/unit/test_dining_and_budget.py` — `test_dining_service_proximity_recommendations`; `tests/unit/test_optw_solver.py` — `test_optw_solver_blocks_attractions_during_reserved_slots`, `test_optw_solver_respects_time_budget_and_depots`; `tests/unit/test_replanning_service.py` — `test_replan_does_not_overlap_future_reserved_meal_slot` | `tests/integration/test_dining_api.py` — `test_contextual_dining_slots_endpoint`, `test_contextual_dining_slots_includes_thematic_slots_at_intensity_five`, `test_dining_recommend_endpoint`; `tests/integration/test_optimize_api.py` — `test_optimize_endpoint_respects_reserved_slots`; `tests/integration/test_trip_replan_endpoint.py` — `test_future_meal_slot_blocks_replanned_visit_without_selected_place`; `tests/integration/test_web_replan_behavior.py` — `test_browser_replanning_flow` | `tests/property/test_optw_properties.py` — `test_optw_itinerary_never_collides_with_reserved_slots`, `test_optw_itinerary_never_exceeds_availability_window` | `src/core/solvers/optw.py`, `src/core/services/dining_and_budget.py` |
| **RF04** | Perfil de Preferência com Intensidade Graduada (0 a 10) | `tests/unit/test_curation_service.py` — `test_apply_curation_boost_to_matching_pois`; `tests/unit/test_preferences_service.py` — `test_all_six_preference_categories_modulate_utility`, `test_preference_intensity_modulates_utility` | `tests/integration/test_curation_api.py` — `test_optimize_endpoint_applies_curation_boost`, `test_optimize_endpoint_respects_inactive_curation_list`; `tests/integration/test_dining_api.py` — `test_contextual_dining_slots_endpoint`, `test_contextual_dining_slots_includes_thematic_slots_at_intensity_five` | `tests/property/test_optw_properties.py` — `test_optw_itinerary_never_collides_with_reserved_slots`; `tests/property/test_preferences_properties.py` — `test_preference_monotonicity_property` | `src/core/services/preferences.py`, `src/core/services/curation.py` |
| **RF05** | Curadoria Híbrida Enriquecida e Parser Seguro de Links | `tests/unit/test_curation_service.py` — `test_cached_places_adapter_cache_aside_sqlite`, `test_cached_places_adapter_with_external_api_mock`, `test_create_places_adapter_factory`, `test_curation_service_requires_places_port`, `test_curation_service_with_injected_port`, `test_offline_replay_adapter_curated_lists`, `test_offline_replay_adapter_search_places`; `tests/unit/test_link_parser_service.py` — `test_dns_rebinding_ip_pinning_transport_connects_only_to_validated_ip`, `test_dns_rebinding_simulation_dual_homed_host_is_rejected`, `test_fetch_url_content_size_limit_exceeded`, `test_fetch_url_content_valid_simulation`, `test_fetch_url_rejects_http_redirects`, `test_link_parser_service_delegates_to_fetcher_port`, `test_link_parser_service_requires_explicit_dependencies`, `test_pinned_ip_transport_initializes_with_backend`, `test_ssrf_validator_blocks_forbidden_urls`, `test_text_extraction_identifies_matching_places` | `tests/integration/test_curation_api.py` — `test_cache_persistence_and_offline_replay`, `test_concurrent_places_caches_remain_isolated`, `test_dining_recommend_with_curation_boost`, `test_places_cache_is_independent_between_cases`, `test_places_search_autocomplete_endpoint`, `test_suggested_curation_endpoint`; `tests/integration/test_import_link_api.py` — `test_import_link_ssrf_protection_returns_400`, `test_import_link_with_raw_text_succeeds`, `test_import_link_with_valid_url_succeeds` | — | `src/core/services/curation.py`, `src/core/services/link_parser.py`, `src/adapters/http/safe_fetcher.py`, `src/adapters/places/offline_adapter.py`, `src/adapters/places/cached_adapter.py` |
| **RF06** | Deslocamento em Cascata (Ripple Shift) com Confirmação Visual | `tests/unit/test_index_html_vocabulary.py` — `test_index_html_new_flow_scripts_use_canonical_vocabulary`, `test_index_html_new_flow_sections_use_canonical_vocabulary`; `tests/unit/test_schedule_service.py` — `test_ripple_shift_extends_stage_and_shifts_subsequent_stages_and_connections` | `tests/integration/test_schedule_api.py` — `test_ripple_shift_apply_endpoint`, `test_ripple_shift_apply_matches_preview_dates_for_positive_delta`, `test_ripple_shift_apply_preserves_target_start_and_updates_end`, `test_ripple_shift_apply_rejects_shrink_that_eliminates_stage`, `test_ripple_shift_apply_rejects_unknown_stage_without_server_state`, `test_ripple_shift_preview_and_apply_share_one_request_shape`, `test_ripple_shift_preview_endpoint`, `test_ripple_shift_preview_exposes_old_and_new_dates_for_negative_delta`, `test_ripple_shift_preview_exposes_unchanged_target_start_for_positive_delta`, `test_ripple_shift_preview_preserves_target_start_for_negative_delta`; `tests/integration/test_web_app.py` — `test_index_page_declares_ripple_actions_and_persistence_intent`, `test_index_page_declares_target_stage_start_label`, `test_index_page_declares_user_facing_error_messages`, `test_index_page_exposes_impact_confirmation_modal`, `test_index_page_exposes_trip_planning_section` | `tests/property/test_ripple_shift_properties.py` — `test_ripple_shift_invariants` | `src/core/services/schedule.py`, `src/adapters/web/app.py`, `src/adapters/web/templates/index.html` — Modal de Confirmação de Impacto com início/término da Etapa de Viagem alvo e horário de partida da Conexão Interurbana, ações declaradas no HTML, aplicação persistida na Viagem mais recente e banner de erro; interação em navegador real não automatizada (§8) |
| **RF07** | Estimativa Parametrizada de Gastos | `tests/unit/test_dining_and_budget.py` — `test_budget_calculation_consolidates_lodging_and_food`, `test_budget_calculation_scales_meal_slots_by_travelers`, `test_budget_calculation_varies_by_food_profile`, `test_budget_calculation_varies_by_travelers_count` | `tests/integration/test_dining_api.py` — `test_trip_budget_endpoint`, `test_trip_budget_endpoint_with_custom_food_profile_and_multiple_travelers` | — | `src/core/services/dining_and_budget.py` |
| **RF08** | Persistência Client-Side e Exportação em Markdown | `tests/unit/test_domain_trip.py` — `test_trip_full_json_serialization_round_trip`; `tests/unit/test_index_html_vocabulary.py` — `test_index_html_new_flow_scripts_use_canonical_vocabulary`, `test_index_html_new_flow_sections_use_canonical_vocabulary`; `tests/unit/test_markdown_export.py` — `test_markdown_export_relinks_deserialized_trip_accommodations`, `test_markdown_export_service_structure`, `test_markdown_uses_effective_stop_duration_and_connection_modal` | `tests/integration/test_export_markdown_api.py` — `test_export_markdown_api_endpoint`; `tests/integration/test_trip_backup_api.py` — `test_backup_validate_rejects_empty_identifiers`, `test_backup_validate_rejects_incomplete_stage_and_connection`, `test_backup_validate_rejects_invalid_field_types`, `test_backup_validate_rejects_non_object_body`, `test_backup_validate_rejects_payload_without_required_trip_id`, `test_backup_validate_rejects_unknown_field_in_legacy_connection`, `test_backup_validate_rejects_unknown_fields_and_untyped_numbers`, `test_backup_validate_returns_validated_trip_and_is_idempotent`, `test_legacy_mode_only_preserves_intercity_modal_and_boarding_margin`; `tests/integration/test_web_app.py` — `test_backup_restore_controls_declare_picker_and_change_trigger`, `test_backup_restore_failure_contract_keeps_trip_and_reports_in_banner`, `test_backup_restore_success_contract_uses_validated_trip_and_render_targets`, `test_health_check`, `test_index_page_declares_user_facing_error_messages`, `test_index_page_exposes_json_backup_controls`, `test_index_page_renders_html`; `tests/integration/test_web_replan_behavior.py` — `test_browser_replanning_flow` | `tests/property/test_ripple_shift_properties.py` — `test_trip_json_round_trip_idempotence` | `src/core/services/markdown_export.py`, `src/core/domain/models.py`, `src/adapters/web/app.py` (`POST /api/trip/backup/validate`), `src/adapters/web/templates/index.html` — controles de Exportar/Restaurar Backup JSON e validação HTTP 200/422 com normalização documentada; download/upload em navegador real não automatizado (§8) |
| **Extensão dinâmica** | Evento de Contingência / Replanejamento (extensão prevista na especificação, sem RF próprio) | `tests/unit/test_events.py`, `tests/unit/test_apply_contingency_event.py`, `tests/unit/test_replanning_service.py`, `tests/unit/test_adapters_web_app.py` | `tests/integration/test_trip_replan_endpoint.py`, `tests/integration/test_web_app.py` (`test_index_page_keeps_day_contingency_controls`) | — | `src/adapters/web/app.py` (`POST /api/trip/replan`), `src/adapters/web/contingency.py`, `src/core/services/replanning.py`, `src/core/domain/events.py`, `src/adapters/web/templates/index.html` — controles do Dia de Viagem preservados; interação em navegador real não automatizada (§8) |

**Extensão dinâmica (contingências)**: requisito sem RF próprio que possui implementação e testes unitários/de integração (§6/§7); resta sem automação apenas a interação em navegador real (§8).

---

## 8. Lacunas conhecidas

Registro honesto do que **ainda não** possui cobertura automatizada. Os itens 1–3 são **lacunas parciais**: os contratos HTTP e a estrutura HTML estão implementados e testados (§7), e permanece sem automação apenas a interação em navegador real (ADR 0002); não devem ser lidos como ausência de código ou de testes. Os itens 4–6 registram limitações de fidelidade e isolamento da suíte.

1. **Interação em navegador real — Backup/restauração JSON (RF08, lacuna parcial)**: o contrato HTTP de `POST /api/trip/backup/validate` cobre respostas 200 (Viagem normalizada) e 422 (schema inválido), a idempotência (`test_backup_validate_returns_validated_trip_and_is_idempotent`) e o round-trip (`test_trip_json_round_trip_idempotence`); a estrutura HTML cobre os botões *Exportar Backup JSON* / *Restaurar Backup JSON*, o seletor de arquivo, o endpoint chamado e o banner para arquivo não-JSON ou incompatível (`tests/integration/test_web_app.py`). Restam sem automação apenas o download do `.json`, a escolha de arquivo no seletor nativo e a observação do `localStorage` em navegador real — nenhuma automação E2E é introduzida, conforme ADR 0002.
2. **Interação em navegador real — Modal de Confirmação de Impacto (RF06, lacuna parcial)**: os contratos HTTP de `preview`/`apply` (inclusive datas anteriores e recalculadas, rejeições e persistência no servidor) e as invariantes de propagação são testados; o modal existe em `src/adapters/web/templates/index.html` e seus contratos estruturais são verificados em `tests/integration/test_web_app.py` (datas anteriores/recalculadas, horário de partida, ações, endpoints, intenção de persistência e banner de erro). Não há automação E2E para abrir o modal por clique, avaliar layout/visibilidade, observar escritas no `localStorage` ou conferir a Viagem reatualizada após a confirmação (ADR 0002).
3. **Interação em navegador real — Eventos de Contingência e Replanejamento (extensão dinâmica, lacuna parcial)**: há implementação e testes unitários/de integração (§7), incluindo a preservação da seção do Dia de Viagem e da chave `kairos_trip_state_v1`. Resta sem automação apenas a manipulação dos controles em navegador real (ADR 0002).
4. **Matriz de Deslocamento aproximada por haversine**: as durações/distâncias de deslocamento entre Pontos de Interesse usam aproximação por haversine, não a API de rotas do Google Maps em todos os cenários. Testes de propriedade validam invariantes temporais, mas não a fidelidade geodésica da Matriz de Deslocamento.
5. **Teste SSRF com DNS real**: a proteção SSRF é testada com urls proibidas e com simulação de DNS rebinding/ip-pinning (`test_dns_rebinding_simulation_dual_homed_host_is_rejected`, `test_dns_rebinding_ip_pinning_transport_connects_only_to_validated_ip`). Não há teste de integração que resolva um hostname com DNS real; a garantia contra rebinding depende da simulação.

---

## 9. Riscos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Instabilidade de entradas geradas por `hypothesis` (floats/coordenadas extremos) produzindo falsos negativos | Médio | Restringir estratégias a domínios geográficos válidos (São Paulo/Lima) e fixar sementes quando necessário. |
| Mutantes sobreviventes em `src/core/` não detectados pelas camadas atuais | Alto | Executar `mutmut` no modo `--full` e converter cada sobrevivente em novo caso de teste (§5.4). |
| Contaminação do cache SQLite global entre testes | Médio | Manter o adaptador de integração em `tmp_path` por caso (§4). |
| Falsa sensação de cobertura de SSRF sem DNS real | Alto | Manter explícita a limitação da simulação de DNS rebinding (lacuna §8.5) e revisar mudanças no validador com atenção. |
| Lacunas parciais de interação em navegador real (Modal de Confirmação de Impacto do Deslocamento em Cascata, Eventos de Contingência/Replanejamento, Backup/restauração JSON) | Médio | Manter os contratos HTTP e os testes de estrutura HTML registrados na matriz (§7) e as limitações explícitas em §8; não introduzir automação E2E, conforme ADR 0002. |
| Dependência involuntária de credenciais/rede | Médio | Garantir `GOOGLE_MAPS_API_KEY` ausente na CI e uso do Modo Offline Replay (§4, ADR 0005). |
| Deriva de vocabulário em rótulos visíveis e nomes de casos de teste | Baixo | Manter `tests/unit/test_index_html_vocabulary.py` cobrindo os novos fluxos de Deslocamento em Cascata e Backup JSON e revisar nomes/termos contra o `GLOSSARY.md` antes do merge. |

---

## 10. Referências

- ISO/IEC/IEEE 29119-2:2013 — Software and systems engineering — Software testing — Part 2: Test processes.
- ISO/IEC/IEEE 29119-3:2013 — Part 3: Test documentation.
- ISO/IEC 25010:2011 — Systems and software quality models.
- ISO/IEC 5055:2021 — Information technology — Automated source code quality measures.
- [Especificação de Requisitos Funcionais](../especificacao-requisitos-funcionais.md) e [GLOSSARY.md](../../GLOSSARY.md) deste repositório.
