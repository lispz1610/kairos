# Especificação de Requisitos Funcionais — Kairos

**Data de Aprovação**: 2026-11-07  
**Alinhamento de Normas**: ISO/IEC 25010 (Adequação Funcional, Segurança e Usabilidade) e ISO/IEC/IEEE 29119 (Especificação de Casos de Teste)  
**Vocabulário Canônico**: [GLOSSARY.md](../GLOSSARY.md)  
**Decisões Arquiteturais**: [ADR 0001](./adr/0001-formulacao-algoritmica-optw.md) a [ADR 0007](./adr/0007-gestao-de-hospedagens-curadoria-e-estado-client-side.md)

---

## 1. Visão Geral

O Kairos atua como um agregador e planejador ponta-a-ponta de viagens turísticas, fornecendo curadoria de rotas urbanas, hospedagens, restaurantes e pausas experienciais através da otimização algorítmica (*Orienteering Problem with Time Windows* - OPTW).

Esta especificação define os requisitos funcionais detalhados construídos a partir do processo de refinamento (*Grilling* e *Domain Modeling*), priorizando privacidade por design (*Client-First*, sem login nem persistência de dados sensíveis no backend), robustez temporal e alta usabilidade com exportação de guia de viagem estruturado em Markdown.

---

## 2. Requisitos Funcionais

### RF01 — Decomposição em Dias de Viagem e Hospedagem Dinâmica
- **Descrição**: O sistema deve permitir que uma *Etapa de Viagem* (cidade) seja decomposta em uma sequência contínua de *Dias de Viagem*.
- **Comportamento**:
  1. O usuário cadastra uma *Hospedagem Base* padrão para a etapa inteira.
  2. O sistema replica essa hospedagem para todos os *Dias de Viagem* da etapa por padrão.
  3. O usuário pode sobrescrever a hospedagem de dias específicos individualmente.
  4. Para cada *Dia de Viagem*, a hospedagem designada define as coordenadas geográficas do *Ponto de Partida/Retorno* utilizadas pela *Matriz de Deslocamento* no solver OPTW.

### RF02 — Gestão de Transição de Hospedagem (Dia de Troca)
- **Descrição**: O sistema deve tratar a mudança de hospedagem dentro da mesma etapa urbana sem quebrar a logística do dia.
- **Comportamento**:
  1. No dia de transição (ex: dormiu no Hotel A e dormirá no Hotel B), o *Roteiro* matinal obrigatoriamente inicia no Hotel A e o encerramento noturno ocorre no Hotel B.
  2. A interface deve sinalizar visualmente o dia com a etiqueta *"Dia de Troca de Hospedagem (Checkout / Check-in)"*.
  3. O sistema deve disponibilizar um interruptor opcional *"Incluir parada para check-in/malas à tarde"*, alocando um deslocamento e parada rápida no Hotel B entre as visitas da tarde.

### RF03 — Slots de Refeição e Pausas Experienciais Contextuais
- **Descrição**: O Roteiro diário deve alocar janelas dedicadas para refeições e pausas de lazer, sugerindo opções curadas com base na proximidade física das atrações turísticas.
- **Comportamento**:
  1. O sistema reserva por padrão os slots:
     - **Almoço**: 12:30 às 14:00;
     - **Jantar**: 19:30 às 21:00.
  2. Para cada slot, o sistema recomenda os **Top 3 estabelecimentos** mais bem ranqueados nas imediações do último POI visitado antes do horário da refeição.
  3. Cada sugestão exibe: Nome, distância a pé/carro, premiações reconhecidas (ex: Michelin, 50 Best), nota Google Places e faixa de preço (`$` a `$$$$`).
  4. O usuário pode selecionar a opção preferida para fixá-la no cronograma ou manter como recomendação flexível.

### RF04 — Perfil de Preferência com Intensidade Graduada (0 a 10)
- **Descrição**: O sistema deve permitir a configuração de categorias temáticas com intensidades numéricas contínuas de 0 a 10, modulando tanto a utilidade de POIs quanto a ativação de pausas temáticas no Roteiro.
- **Comportamento**:
  1. O usuário ajusta controles deslizantes (0 a 10) para tags pré-configuradas:
     - *Coffee Lover*
     - *Wine Lover*
     - *Museum Lover*
     - *Nature Lover*
     - *Gastronomy & Fine Dining*
     - *Street Food*
  2. **Impacto na Utilidade**: POIs pertencentes à categoria com peso $w \in [0, 10]$ recebem um multiplicador de utilidade proporcional $U' = U \times (1 + w/10)$, maximizando sua chance de seleção pelo solver OPTW.
  3. **Gatilho de Slots Dedicados**:
     - *Coffee Lover $\ge 5$*: ativa automaticamente uma **Pausa para Café** (15:30 às 16:15) sugerindo cafeterias de especialidade próximas;
     - *Wine Lover $\ge 5$*: ativa automaticamente um slot de **Wine Bar / Degustação** (18:00 às 19:15).

### RF05 — Curadoria Híbrida Enriquecida e Parser Seguro de Links
- **Descrição**: O sistema deve agregar dados do Google Places com listas públicas sugeridas e possibilitar a criação de listas personalizadas pelo usuário, inclusive extraindo locais a partir de links externos.
- **Comportamento**:
  1. **Galeria de Listas Sugeridas**: O sistema oferece ativação com um clique de listas pré-mapeadas (*"Guia Michelin"*, *"Latin America's 50 Best"*, *"Especialidades de Café"*, *"TripAdvisor Travellers' Choice"*).
  2. **Criador de Listas Customizadas**: O usuário pode criar suas próprias listas (ex: *"Dicas de Amigos"*), buscando estabelecimentos por autocompletar do Google Places ou inserção manual.
  3. **Parser de Links e Textos**:
     - O usuário pode fornecer a URL de um artigo/blog ou colar diretamente o corpo do texto.
     - O backend FastAPI lê a URL através de um cliente HTTP seguro (validando esquemas `http/https`, bloqueando endereços IP locais/privados contra vulnerabilidades SSRF e impondo timeout de 5 segundos).
     - Um extrator identifica nomes de estabelecimentos citados e realiza busca no Google Places/Cache local.
     - A interface exibe cards de pré-visualização para o usuário revisar, confirmar ou descartar itens antes de salvá-los no `localStorage`.

### RF06 — Deslocamento em Cascata (Ripple Shift) com Confirmação Visual
- **Descrição**: O sistema deve propagar ajustes de calendário ao alterar a quantidade de dias de uma etapa, garantindo a integridade de toda a jornada.
- **Comportamento**:
  1. Ao alterar os dias de permanência de uma etapa (ex: São Paulo de 1–10 para 1–11):
     - A duração das etapas subsequentes (ex: Lima, 5 dias) é estritamente preservada;
     - As datas das etapas futuras e das *Conexões Interurbanas* (voos/transporte) são deslocadas em cascata (ex: Lima passa para 11–16).
     - Os Roteiros já calculados das etapas futuras preservam suas atrações, atualizando apenas o calendário.
     - A etapa ampliada ganha novos *Dias de Viagem* em branco para preenchimento.
  2. O sistema exibe obrigatoriamente um **Modal de Confirmação de Impacto** detalhando as novas datas de partida, chegada e transporte interurbano antes de aplicar a alteração no estado.

### RF07 — Estimativa Parametrizada de Gastos
- **Descrição**: O sistema deve calcular projeções orçamentárias de hospedagem e alimentação de forma automática e configurável.
- **Comportamento**:
  1. **Hospedagem**: Calculada com base na diária real inserida pelo usuário para cada hotel ou calculada pela média estimada da categoria do estabelecimento (Econômico: R\$ 200, Conforto: R\$ 450, Alto Padrão: R\$ 1.000+).
  2. **Alimentação**: Calculada com base no perfil de consumo diário selecionado (Econômico: R\$ 80/dia/pessoa, Moderado: R\$ 180/dia/pessoa, Alta Gastronomia: R\$ 400+/dia/pessoa) ou pela soma das estimativas dos restaurantes selecionados nos slots.
  3. **Resumo Orçamentário**: Painel exibindo a estimativa financeira discriminada por cidade e o total acumulado da viagem.

### RF08 — Persistência Client-Side e Exportação em Markdown
- **Descrição**: Todo o estado da jornada deve permanecer no lado do cliente, fornecendo mecanismos de backup e emissão de relatório completo em Markdown.
- **Comportamento**:
  1. O estado da *Viagem*, *Etapas*, *Hospedagens*, *Listas de Curadoria* e *Roteiros* é persistido de forma reativa no `localStorage` do navegador.
  2. O sistema disponibiliza botões para **Exportar Backup JSON** e **Restaurar Backup JSON**, permitindo transferir o itinerário entre navegadores sem depender de contas ou servidores de banco de dados.
  3. O sistema disponibiliza um painel de **Exportação de Roteiro em Markdown**, contendo:
     - Pré-visualização renderizada com tipografia legível;
     - Botão de **Copiar Markdown** (cópia direta para a área de transferência);
     - Botão de **Baixar Arquivo (`viagem-kairos.md`)**.
  4. O documento Markdown gerado deve conter:
     - **Sumário Executivo**: Título, viajantes, datas e Conexões Interurbanas;
     - **Quadro Orçamentário**: Tabela consolidada de estimativas financeiras;
     - **Caderno Diário**: Cronograma horário detalhado dia a dia, com hospedagens, paradas em POIs (com tempo de permanência), tempos de deslocamento e slots de refeição com sugestões curadas e faixas de preço;
     - **Apêndice de Curadoria**: Relação de estabelecimentos premiados e notas do usuário.

### RF09 — Conexão Interurbana: Departure Datetime e Margem de Embarque
- **Descrição**: O sistema deve representar a *Conexão Interurbana* com partida obrigatória com data e hora e um limite de embarque configurável por modal, alinhado ao modelo temporal do Dia de Viagem.
- **Comportamento**:
  1. `InterCityConnection` (Conexão Interurbana): campo obrigatório `departure_datetime: datetime` (partida com data e hora).
  2. `boarding_cutoff_minutes: int` (Margem de Embarque): padrão `120` para modal `flying`, `30` para modal `driving` e `transit`.
  3. `ScheduleService`: valida que o Roteiro do Dia de Viagem respeita os Horários de Funcionamento dos Pontos de Interesse e permanece dentro da Janela de Disponibilidade, reportando desvios quando houver.
  4. Testes unitários de contrato (ISO/IEC/IEEE 29119):
     - Padrão do modal: `boarding_cutoff_minutes` padrão `120` (modal `flying`) e `30` (modais `driving`/`transit`).
     - Visita fora do horário de funcionamento (desvio reportado): `ScheduleService` reporta o desvio.
     - Janela de Disponibilidade violada (desvio reportado): `ScheduleService` reporta o desvio.

---

## 3. Diretrizes de Qualidade e Casos de Teste (ISO/IEC 25010 & 29119)

1. **Adequação Funcional (OPTW com Hospedagens Variáveis)**:
   - Teste de propriedade (`hypothesis`): Provar que para qualquer combinação de Hotel A (partida) e Hotel B (retorno), a soma dos tempos de deslocamento, permanências nos POIs e slots de refeição nunca ultrapassa a Janela de Disponibilidade diária.
2. **Confiabilidade (Ripple Shift Invariants)**:
   - Teste unitário: Garantir que estender uma etapa em $+N$ dias propaga exatamente $+N$ dias para todas as Conexões Interurbanas e etapas posteriores, sem duplicar POIs ou corromper roteiros existentes.
3. **Segurança (Parser de Links e SSRF)**:
   - Teste de integração: Validar que requisições para IPs de loopback (`127.0.0.1`, `localhost`), redes privadas (`10.0.0.0/8`, `192.168.0.0/16`) ou protocolos diferentes de `http/https` são estritamente rejeitadas pelo endpoint do parser de curadoria.
4. **Portabilidade & Integridade de Dados (Import/Export JSON)**:
   - Teste de serialização: Garantir que um estado exportado para JSON e reimportado recupera 100% dos dados de forma idêntica (round-trip idempotente).
