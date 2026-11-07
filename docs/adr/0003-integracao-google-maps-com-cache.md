# 3. Integração com APIs Google Maps e Camada Obrigatória de Cache

## Contexto
O cálculo de rotas turísticas globais depende de dados geográficos acurados, avaliações reais e matrizes de tempo de deslocamento. O Google Maps Platform fornece Places API, Distance Matrix/Routes API e Geocoding API de alta fidelidade, porém o consumo de rede em testes automatizados introduz não-determinismo, latência e consumo desnecessário de cotas.

## Decisão
Utilizamos exclusivamente a **Google Maps Platform** como provedor de dados geoespaciais e de roteamento, implementando obrigatoriamente o padrão **Cache-Aside** (com persistência local em SQLite/JSON). As chamadas de teste e demonstração priorizam o cache local, isolando os testes unitários e de integração de chamadas reais de rede por meio de stubs/mocks.

## Consequências
- Alta precisão de horários de funcionamento (`opening_hours`), notas de avaliação (`rating`) e tempos de deslocamento reais no mundo inteiro.
- Total determinismo na execução de suítes de testes (`pytest`), sem requisições HTTP externas durante o ciclo de CI/CD.
- Demonstração resiliente em sala de aula imune a eventuais falhas de internet.
