# Plano de Testes ISO/IEC/IEEE 29119 — Kairos

**Normas de referência**: ISO/IEC/IEEE 29119-2 (Processo de Teste de Software) e ISO/IEC/IEEE 29119-3 (Documentação de Teste).
**Alinhamento complementar**: ISO/IEC 25010 (Adequação Funcional, Confiabilidade, Segurança e Usabilidade), ISO/IEC 5055 (Qualidade Estrutural de Código).
**Vocabulário canônico**: [GLOSSARY.md](../../GLOSSARY.md). Todo termo de domínio abaixo (Viagem, Etapa de Viagem, Dia de Viagem, Hospedagem, Dia de Troca de Hospedagem, Conexão Interurbana, Ponto de Interesse, Roteiro, Janela de Disponibilidade, Janela de Funcionamento, Tempo de Permanência, Matriz de Deslocamento, Pontuação de Utilidade, Perfil de Preferência, Slot de Refeição, Estimativa de Gastos, Evento de Contingência, Replanejamento, Deslocamento em Cascata) é empregado no sentido definido no glossário.
**Requisitos rastreados**: [Especificação de Requisitos Funcionais](../especificacao-requisitos-funcionais.md), RF01–RF08.
**Decisões arquiteturais relacionadas**: [ADR 0001](../adr/0001-formulacao-algoritmica-optw.md) (OPTW), [ADR 0004](../adr/0004-arquitetura-viagens-multicidades.md), [ADR 0005](../adr/0005-modo-offline-replay-credenciais.md) (Offline Replay), [ADR 0007](../adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md).

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
- Gate de qualidade `verify_quality.sh` e validadores docs-as-code/de rastreabilidade (`scripts/`), com testes de CLI em `tests/unit/`.

**Fora de escopo (declarado)**

- Testes de interface gráfica em navegador real (Selenium/Playwright); a camada web é verificada por testes de integração HTTP sobre a aplicação FastAPI e por asserções sobre o HTML servido (ADR 0002). A interação real em navegador permanece registrada como lacuna parcial em §8.
- Testes de carga, desempenho e penetração automatizados.
- Execução da persistência client-side dentro do navegador; os contratos HTTP e a estrutura do HTML estão em escopo, e a observação do `localStorage` em navegador real é lacuna parcial (§8).

---

## 2. Estratégia em camadas

A estratégia segue o modelo em camadas da ISO/IEC/IEEE 29119-2, com pirâmide invertida em direção à maior retroalimentação:

| Camada | Diretório | Objetivo principal | Técnica dominante |
| --- | --- | --- | --- |
| **Unitário** | `tests/unit/` | Invariantes de domínio, regras de serviço e cálculos determinísticos isolados de I/O. | Particionamento em classes de equivalência, análise de valor limite, parametrização. |
| **Integração** | `tests/integration/` | Contratos HTTP da aplicação FastAPI (inclusive `POST /api/trip/replan` e Deslocamento em Cascata), composição solver + adaptadores + serviços, Offline Replay. | Casos de teste de interface (request/response), partições de entrada inválidas. |
| **Propriedade** | `tests/property/` | Invariantes universais que devem valer para qualquer entrada gerada. | Property-Based Testing com `hypothesis`. |
| **Mutação** | `src/core/` (alvo) | Avaliar a força das camadas anteriores por mutantes sobreviventes. | Teste de Mutação com `mutmut` (modo `--full`). |
| **Docs-as-code** | `scripts/` + `tests/unit/` | Verificar coerência entre documentação, código e matriz de rastreabilidade. | Testes de CLI com árvores isoladas (`tmp_path`) e execução dos validadores. |

A camada de mutação não produz casos de teste novos: ela pontua a qualidade das demais. Um mutante sobrevivente em `src/core/` é tratado como um defeito de cobertura a ser corrigido com um novo caso de teste nas camadas unitária ou de propriedade.

---

## 3. Critérios de entrada e saída

### 3.1 Critérios de entrada (entry criteria)

- Código-fonte e testes presentes no worktree, com dependências de desenvolvimento instaladas (`pytest`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`, `radon`, `mutmut`).
- Requisitos RF01–RF08 e vocabulário canônico disponíveis para derivação de casos de teste.
- Variável `GOOGLE_MAPS_API_KEY` **ausente** para execução determinística em Modo Offline Replay (ADR 0005); quando presente, a suíte deve continuar independente de rede via injeção de portas.
- Ambiente Python 3.12 (alvo de `ruff`/`mypy`) e `PYTHONPATH` com a raiz do repositório.

### 3.2 Critérios de saída (exit criteria)

O gate unificado `verify_quality.sh` define a condição de conclusão:

1. `ruff check src tests` sem violações (estilo, imports e docstrings PEP 257).
2. `mypy --strict src` sem erros de tipagem.
3. `radon cc src` sem função/método com complexidade ciclomática `>= 10`.
4. `pytest --cov=src --cov-report=term-missing --cov-fail-under=85` com cobertura `>= 85%`.
5. No modo `--full`, `mutmut` executado sobre `src/core/`, com mutation score consolidado e contagem de mutantes sobreviventes. Critério de monitoramento/evidência, não uma checagem automática: o `verify_quality.sh --full` reporta o score e os sobreviventes sem impor threshold; a equipe registra na revisão a justificativa de cada sobrevivente e decide pela conversão em novos casos de teste (§5.4).
6. Rastreabilidade RF × teste (§7) com RF01–RF08 integralmente cobertos por ao menos um caso de teste existente, verificada pelo gate com `python scripts/validate_traceability.py --spec docs/especificacao-requisitos-funcionais.md --root .` e pela matriz com `python scripts/generate_traceability_matrix.py --plan docs/testing/test-plan-29119.md --spec docs/especificacao-requisitos-funcionais.md --root . --check`.
7. Coerência docs-as-code, verificada pelo gate com `python scripts/validate_docs_as_code.py --plan docs/testing/test-plan-29119.md --handoff docs/HANDOFF.md --root .`, com Eventos de Contingência, Replanejamento e `verify_quality.sh` descritos como entregues.

O gate `verify_quality.sh` está entregue e é executado antes de cada commit/PR; os validadores dos itens 6 e 7 passaram a integrar o gate rápido na issue #86 e são executados uma única vez, também pelo workflow de quality gate em cada pull request. Qualquer falha nas verificações automatizadas acima bloqueia o merge, conforme o gate de qualidade do issue-pai #19; o item 5 é monitoramento/evidência, sem threshold automático.

---

## 4. Ambiente Offline Replay

Conforme ADR 0005, a chave `GOOGLE_MAPS_API_KEY` é injetada apenas por variável de ambiente. Na ausência dela, o adaptador de Ponto de Interesse entra em **Modo Offline Replay**, servindo dados pré-gravados para as cidades de demonstração (São Paulo, Lima, Juiz de Fora). Isso garante que:

- a suíte rode com **zero credenciais** e **zero conectividade externa**;
- a banca examinadora reproduza os mesmos resultados da CI;
- nenhuma cota ou custo de API seja consumido durante os testes.

Evidências do modo nos testes: `tests/unit/test_curation_service.py` (`test_offline_replay_adapter_curated_lists`, `test_offline_replay_adapter_search_places`, `test_cached_places_adapter_cache_aside_sqlite`, `test_create_places_adapter_factory`) e `tests/integration/test_curation_api.py` (`test_cache_persistence_and_offline_replay`).

**Nota de isolamento**: o cache SQLite do adaptador é global por padrão; testes que o exercitam devem usar `tmp_path` ou limpar o cache para evitar contaminação entre casos (ver lacuna em §8).

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

**Exemplo Kairos — intensidade do Perfil de Preferência (RF04).** A escala canônica é 0–10, com gatilho de slot temático em `>= 5`. A fronteira 5 é o ponto crítico: `test_thematic_slots_generation_for_coffee_and_wine_lovers` em `tests/unit/test_preferences_service.py` verifica o disparo da Pausa para Café e do slot de Wine Bar exatamente no limite. `test_preference_intensity_modulates_utility` complementa com o comportamento nos extremos da escala.

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

### 5.5 Eventos de Contingência e Replanejamento

Técnica: classes de equivalência sobre os quatro tipos de Evento (`delay`, `closure`, `skip`, `duration_adjustment`) e contratos HTTP de `POST /api/trip/replan`. Os Eventos de Domínio em `src/core/domain/events.py` são validados em `tests/unit/test_events.py`; a conversão para entradas de Replanejamento é exercitada em `tests/unit/test_apply_contingency_event.py` e `tests/unit/test_adapters_web_app.py`; o recálculo do Roteiro restante a partir da coordenada/horário atuais, a preservação de paradas passadas e de Slots de Refeição futuros, o teto da Conexão Interurbana e o alerta de risco são verificados em `tests/unit/test_replanning_service.py` e `tests/integration/test_trip_replan_endpoint.py`. A interação dos controles na timeline em navegador real é registrada como lacuna parcial em §8.

### 5.6 Validação docs-as-code e gate de qualidade

Técnica: testes de CLI com documentos e árvore de código isolados por `tmp_path`, além de teste de integração do gate com ferramentas externas simuladas. `tests/unit/test_docs_as_code_validator.py` verifica que o validador aceita lacunas parciais de navegador e rejeita afirmações de ausência total quando os artefatos estão presentes; `tests/unit/test_traceability_matrix_generator.py` verifica geração/verificação da matriz a partir dos marcadores `requirement`; `tests/unit/test_quality_gate_validators.py` comprova que divergências propositais em marcadores, matriz e documentação derrubam o gate sem alterar o repositório. O script `verify_quality.sh` automatiza `ruff`, `mypy --strict`, `radon`, `pytest --cov`, os validadores de rastreabilidade (incluindo `--check` da matriz) e o validador docs-as-code (com estágio opcional de mutação), sendo executado como gate antes de commits e PRs e no CI.

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
| CT-BUD-01 | Classes de equivalência | RF07 | `tests/unit/test_dining_and_budget.py::test_budget_calculation_varies_by_food_profile` |
| CT-EXP-01 | Round-trip / serialização | RF08 | `tests/property/test_ripple_shift_properties.py::test_trip_json_round_trip_idempotence` |
| CT-CONT-01 | Classes de equivalência / contrato HTTP | Extensão dinâmica (RF10/RF13) | `tests/unit/test_events.py`, `tests/unit/test_apply_contingency_event.py`, `tests/unit/test_adapters_web_app.py` |
| CT-REPL-01 | Invariante / contrato HTTP | Extensão dinâmica (RF12/RF13) | `tests/unit/test_replanning_service.py`, `tests/integration/test_trip_replan_endpoint.py` |
| CT-QUAL-01 | Docs-as-code / matriz / gate | Qualidade | `tests/unit/test_docs_as_code_validator.py`, `tests/unit/test_traceability_matrix_generator.py`, `tests/unit/test_quality_gate_validators.py`, `verify_quality.sh` |

---

## 7. Matriz de Rastreabilidade RF01–RF08 × testes

Cada requisito é ligado a arquivos e casos de teste **existentes** no worktree. Caminhos em `tests/` e `src/` foram verificados quanto à existência.
A matriz é gerada por `python scripts/generate_traceability_matrix.py --plan docs/testing/test-plan-29119.md --spec docs/especificacao-requisitos-funcionais.md --root .`; o gate rápido executa essa geração com `--check`, sem gravar (issues #83 e #86).

| RF | Requisito | Testes unitários | Testes de integração | Testes de propriedade | Código de produção relacionado |
| --- | --- | --- | --- | --- | --- |
| **RF01** | Decomposição em Dias de Viagem e Hospedagem Dinâmica | `tests/unit/test_domain_trip.py` — `test_accommodation_creation_and_coordinates`, `test_deserialized_trip_relinks_previous_day_accommodations_for_transition_detection`, `test_trip_stage_custom_hotel_override_and_transition_detection`, `test_trip_stage_days_generation_with_base_hotel`; `tests/unit/test_optw_solver.py` — `test_optw_solver_respects_time_budget_and_depots` | — | `tests/property/test_ripple_shift_properties.py` — `test_ripple_shift_invariants`, `test_trip_json_round_trip_idempotence` | `src/core/domain/models.py` |
| **RF02** | Gestão de Transição de Hospedagem (Dia de Troca) | `tests/unit/test_domain_trip.py` — `test_deserialized_trip_relinks_previous_day_accommodations_for_transition_detection`, `test_trip_stage_custom_hotel_override_and_transition_detection`; `tests/unit/test_markdown_export.py` — `test_markdown_export_relinks_deserialized_trip_accommodations`, `test_markdown_export_service_structure` | — | `tests/property/test_ripple_shift_properties.py` — `test_trip_json_round_trip_idempotence` | `TripDay.is_transition_day` em `src/core/domain/models.py` |
| **RF03** | Slots de Refeição e Pausas Experienciais Contextuais | `tests/unit/test_dining_and_budget.py` — `test_dining_service_proximity_recommendations`; `tests/unit/test_optw_solver.py` — `test_optw_solver_blocks_attractions_during_reserved_slots`, `test_optw_solver_respects_time_budget_and_depots`; `tests/unit/test_preferences_service.py` — `test_thematic_slots_generation_for_coffee_and_wine_lovers` | `tests/integration/test_dining_api.py` — `test_contextual_dining_slots_endpoint`, `test_dining_recommend_endpoint`; `tests/integration/test_optimize_api.py` — `test_optimize_endpoint_respects_reserved_slots` | `tests/property/test_optw_properties.py` — `test_optw_itinerary_never_collides_with_reserved_slots`, `test_optw_itinerary_never_exceeds_availability_window` | `src/core/solvers/optw.py`, `src/core/services/dining_and_budget.py` |
| **RF04** | Perfil de Preferência com Intensidade Graduada (0 a 10) | `tests/unit/test_curation_service.py` — `test_apply_curation_boost_to_matching_pois`; `tests/unit/test_preferences_service.py` — `test_all_six_preference_categories_modulate_utility`, `test_preference_intensity_modulates_utility`, `test_thematic_slots_generation_for_coffee_and_wine_lovers` | `tests/integration/test_curation_api.py` — `test_optimize_endpoint_applies_curation_boost`, `test_optimize_endpoint_respects_inactive_curation_list`; `tests/integration/test_dining_api.py` — `test_contextual_dining_slots_endpoint` | `tests/property/test_optw_properties.py` — `test_optw_itinerary_never_collides_with_reserved_slots`; `tests/property/test_preferences_properties.py` — `test_preference_monotonicity_property` | `src/core/services/preferences.py`, `src/core/services/curation.py` |
| **RF05** | Curadoria Híbrida Enriquecida e Parser Seguro de Links | `tests/unit/test_curation_service.py` — `test_cached_places_adapter_cache_aside_sqlite`, `test_cached_places_adapter_with_external_api_mock`, `test_create_places_adapter_factory`, `test_curation_service_requires_places_port`, `test_curation_service_with_injected_port`, `test_offline_replay_adapter_curated_lists`, `test_offline_replay_adapter_search_places`; `tests/unit/test_link_parser_service.py` — `test_dns_rebinding_ip_pinning_transport_connects_only_to_validated_ip`, `test_dns_rebinding_simulation_dual_homed_host_is_rejected`, `test_fetch_url_content_size_limit_exceeded`, `test_fetch_url_content_valid_simulation`, `test_fetch_url_rejects_http_redirects`, `test_link_parser_service_delegates_to_fetcher_port`, `test_link_parser_service_requires_curation_service_for_extraction`, `test_link_parser_service_requires_fetcher_for_network_calls`, `test_pinned_ip_transport_initializes_with_backend`, `test_ssrf_validator_blocks_forbidden_urls`, `test_text_extraction_identifies_matching_places` | `tests/integration/test_curation_api.py` — `test_cache_persistence_and_offline_replay`, `test_dining_recommend_with_curation_boost`, `test_places_search_autocomplete_endpoint`, `test_suggested_curation_endpoint`; `tests/integration/test_import_link_api.py` — `test_import_link_ssrf_protection_returns_400`, `test_import_link_with_raw_text_succeeds`, `test_import_link_with_valid_url_succeeds` | — | `src/core/services/curation.py`, `src/core/services/link_parser.py`, `src/adapters/http/safe_fetcher.py`, `src/adapters/places/offline_adapter.py`, `src/adapters/places/cached_adapter.py` |
| **RF06** | Deslocamento em Cascata (Ripple Shift) com Confirmação Visual | `tests/unit/test_schedule_service.py` — `test_ripple_shift_extends_stage_and_shifts_subsequent_stages_and_connections` | `tests/integration/test_schedule_api.py` — `test_ripple_shift_apply_endpoint`, `test_ripple_shift_preview_endpoint` | `tests/property/test_ripple_shift_properties.py` — `test_ripple_shift_invariants` | `src/core/services/schedule.py`, `src/adapters/web/app.py` — confirmação visual do Modal de Confirmação de Impacto com interação em navegador fora da automação (ver §8) |
| **RF07** | Estimativa Parametrizada de Gastos | `tests/unit/test_dining_and_budget.py` — `test_budget_calculation_consolidates_lodging_and_food`, `test_budget_calculation_scales_meal_slots_by_travelers`, `test_budget_calculation_varies_by_food_profile`, `test_budget_calculation_varies_by_travelers_count` | `tests/integration/test_dining_api.py` — `test_trip_budget_endpoint`, `test_trip_budget_endpoint_with_custom_food_profile_and_multiple_travelers` | — | `src/core/services/dining_and_budget.py` |
| **RF08** | Persistência Client-Side e Exportação em Markdown | `tests/unit/test_domain_trip.py` — `test_trip_full_json_serialization_round_trip`; `tests/unit/test_markdown_export.py` — `test_markdown_export_relinks_deserialized_trip_accommodations`, `test_markdown_export_service_structure` | `tests/integration/test_export_markdown_api.py` — `test_export_markdown_api_endpoint`; `tests/integration/test_web_app.py` — `test_health_check`, `test_index_page_renders_html` | `tests/property/test_ripple_shift_properties.py` — `test_trip_json_round_trip_idempotence` | `src/core/services/markdown_export.py`, `src/core/domain/models.py`, `src/adapters/web/templates/index.html` — **backup/restauração JSON no navegador não automatizado (ver §8)** |
| **Extensão dinâmica** | Evento de Contingência / Replanejamento (extensão prevista na especificação, sem RF próprio) | `tests/unit/test_events.py`, `tests/unit/test_apply_contingency_event.py`, `tests/unit/test_replanning_service.py`, `tests/unit/test_adapters_web_app.py` | `tests/integration/test_trip_replan_endpoint.py` | Invariantes do Roteiro exercitadas nas linhas RF01/RF08 | `src/core/domain/events.py`, `src/adapters/web/contingency.py`, `src/core/services/replanning.py`, `src/adapters/web/app.py` (`POST /api/trip/replan`) — interação dos controles em navegador fora da automação (§8) |

**Extensão dinâmica (contingências)**: o requisito de Evento de Contingência/Replanejamento é uma extensão prevista na especificação (RF10–RF13) sem RF próprio nesta matriz (RF01–RF08), mas com implementação e casos de teste entregues nas camadas unitária e de integração, conforme a linha de extensão dinâmica. A limitação registrada é apenas a automação da interação em navegador real (§8).

---

## 8. Lacunas conhecidas

Registro honesto das lacunas parciais de automação em navegador real e das limitações de fidelidade/isolamento da suíte. Os itens 1–3 são **lacunas parciais**: os contratos HTTP e os testes unitários/de integração estão entregues (§7); permanece fora da automação apenas a interação em navegador real (ADR 0002). Nenhum deles deve ser lido como ausência de código ou de testes.

1. **Backup/restauração JSON no navegador (RF08, lacuna parcial)**: a persistência em `localStorage` e os fluxos de *Exportar Backup JSON* / *Restaurar Backup JSON* não são exercitados por automação de navegador. A rastreabilidade cobre o round-trip de serialização da Viagem (`test_trip_full_json_serialization_round_trip`, `test_trip_json_round_trip_idempotence`) e a exportação Markdown via API. Restam fora de automação o download do `.json`, a escolha de arquivo no seletor nativo e a observação do estado no navegador real.
2. **Modal de Confirmação de Impacto do Deslocamento em Cascata (RF06, lacuna parcial)**: os endpoints `preview`/`apply` e as invariantes de propagação estão entregues e testados. A confirmação visual via Modal de Confirmação de Impacto não possui automação de interação em navegador real (abertura por clique, visibilidade/layout, confirmação e cancelamento); a verificação atual é HTTP e estrutural, conforme ADR 0002.
3. **Eventos de Contingência e Replanejamento (extensão dinâmica, lacuna parcial)**: a extensão possui implementação (`POST /api/trip/replan`, orquestração em `src/adapters/web/contingency.py`, serviço em `src/core/services/replanning.py` e Eventos em `src/core/domain/events.py`) e testes unitários/de integração para atraso, fechamento prematuro, cancelamento de parada, ajuste de Tempo de Permanência, Slots de Refeição reservados, alerta de risco da Conexão Interurbana e recálculo do Roteiro restante a partir da coordenada/horário atuais. Resta fora de automação apenas a manipulação dos controles na timeline em navegador real.
4. **Matriz de Deslocamento aproximada por haversine**: as durações/distâncias de deslocamento entre Pontos de Interesse usam aproximação por haversine, não a API de rotas do Google Maps em todos os cenários. Testes de propriedade validam invariantes temporais, mas não a fidelidade geodésica da Matriz de Deslocamento.
5. **Teste SSRF com DNS real**: a proteção SSRF é testada com urls proibidas e com simulação de DNS rebinding/ip-pinning (`test_dns_rebinding_simulation_dual_homed_host_is_rejected`, `test_dns_rebinding_ip_pinning_transport_connects_only_to_validated_ip`). Não há teste de integração que resolva um hostname com DNS real; a garantia contra rebinding depende da simulação.
6. **Cache SQLite global compartilhado entre testes**: o adaptador com cache `cache-aside` usa um banco SQLite global por padrão. Casos que o exercitam (`test_cached_places_adapter_cache_aside_sqlite`, `test_cache_persistence_and_offline_replay`) podem compartilhar estado entre execuções; recomenda-se isolar com `tmp_path` ou limpeza explícita para garantir repetibilidade.

---

## 9. Riscos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| Instabilidade de entradas geradas por `hypothesis` (floats/coordenadas extremos) produzindo falsos negativos | Médio | Restringir estratégias a domínios geográficos válidos (São Paulo/Lima) e fixar sementes quando necessário. |
| Mutantes sobreviventes em `src/core/` não detectados pelas camadas atuais | Alto | Executar `mutmut` no modo `--full` e converter cada sobrevivente em novo caso de teste (§5.4). |
| Contaminação do cache SQLite global entre testes | Médio | Isolar com `tmp_path`/limpeza explícita (lacuna §8.6). |
| Falsa sensação de cobertura de SSRF sem DNS real | Alto | Manter explícita a limitação da simulação de DNS rebinding (lacuna §8.5) e revisar mudanças no validador com atenção. |
| Lacunas parciais de interação em navegador real (Modal de Confirmação de Impacto do Deslocamento em Cascata, Eventos de Contingência/Replanejamento, Backup/restauração JSON) | Médio | Manter os contratos HTTP e os testes registrados na matriz (§7) e as limitações explícitas em §8; não introduzir automação E2E, conforme ADR 0002. |
| Dependência involuntária de credenciais/rede | Médio | Garantir `GOOGLE_MAPS_API_KEY` ausente na CI e uso do Modo Offline Replay (§4, ADR 0005). |
| Deriva de vocabulário em nomes de casos de teste | Baixo | Revisar novos testes contra o `GLOSSARY.md` antes do merge. |

---

## 10. Referências

- ISO/IEC/IEEE 29119-2:2013 — Software and systems engineering — Software testing — Part 2: Test processes.
- ISO/IEC/IEEE 29119-3:2013 — Part 3: Test documentation.
- ISO/IEC 25010:2011 — Systems and software quality models.
- ISO/IEC 5055:2021 — Information technology — Automated source code quality measures.
- [Especificação de Requisitos Funcionais](../especificacao-requisitos-funcionais.md) e [GLOSSARY.md](../../GLOSSARY.md) deste repositório.
