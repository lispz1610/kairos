# Kairos — Traçador Dinâmico de Rotas Turísticas

Sistema de recomendação e otimização de itinerários turísticos personalizados com restrições temporais e espaciais.

## Language

### Estrutura da Jornada

**Viagem**:
Planejamento global composto por uma sequência ordenada de Etapas de Viagem interligadas por Conexões Interurbanas.
_Avoid_: Roteiro global, itinerário completo, projeto de viagem

**Etapa de Viagem**:
Subconjunto temporal e geográfico de uma Viagem restrito a uma cidade ou região delimitada, decomposta em Dias de Viagem e Pontos de Interesse elegíveis.
_Avoid_: Set, bloco de cidade, trecho urbano

**Dia de Viagem**:
Unidade diária que compõe uma Etapa de Viagem, associada a uma data de calendário, a uma Hospedagem e a um Roteiro urbano dedicado.
_Avoid_: Diária, dia de passeio, bloco diário

**Hospedagem**:
Estabelecimento hoteleiro ou residencial que atua como Ponto de Partida/Retorno obrigatório para os Roteiros de um ou mais Dias de Viagem.
_Avoid_: Hotel, base, pousada, dormitório

**Dia de Troca de Hospedagem**:
Dia de Viagem no qual ocorre transição entre estabelecimentos hoteleiros distintos dentro da mesma Etapa de Viagem. O Roteiro matinal parte da Hospedagem anterior e o encerramento noturno dá-se na nova Hospedagem, com suporte opcional a parada intermediária para check-in e depósito de bagagens à tarde.
_Avoid_: Troca de hotel, dia de checkout, transição hoteleira

**Conexão Interurbana**:
Transição de longa distância conectando o término de uma Etapa de Viagem ao início da etapa subsequente, operando sob modais intermunicipais (como aéreo `flying` ou rodoviário), com horário de partida e limite operacional (Margem de Embarque e teto de replanejamento).
_Avoid_: Voo, viagem entre cidades, transição

**Margem de Embarque**:
Margem operacional usada pelas Conexões Interurbanas, derivada do `departure_datetime` e do `boarding_cutoff_minutes` do modal; diferença entre o horário efetivo de embarque da Conexão Interurbana e o horário de partida, que define o limite operacional do ponto de partida.
_Avoid_: Janela de partida, tempo de espera, intervalo de embarque

**Modal de Transporte**:
Meio físico utilizado para locomoção, distinguindo-se entre transporte urbano (`walking`, `driving`) e interurbano (`flying`, `transit`).
_Avoid_: Tipo de locomoção, meio de transporte

### Roteiro Urbano e Pontos de Interesse

**Ponto de Interesse (POI)**:
Local geográfico delimitado com relevância turística, cultural ou de lazer elegível para visitação, dotado de coordenadas e horário de funcionamento.
_Avoid_: Atração, parada, local turístico, parada turística

**Lista de Curadoria**:
Catálogo temático de estabelecimentos e atrações chancelados por premiações públicas, guias especializados ou curadoria personalizada do usuário, que confere bonificação à Pontuação de Utilidade.
_Avoid_: Lista de recomendações, ranking, lista de favoritos

**Roteiro**:
Sequência cronológica ordenada de visitas a Pontos de Interesse programadas para ocorrer dentro da Janela de Disponibilidade de um Dia de Viagem.
_Avoid_: Itinerário, percurso, plano de viagem

**Ponto de Partida/Retorno**:
Coordenada geográfica fixa (geralmente a Hospedagem daquele dia, ou aeroporto/estação em dias de trânsito) onde o Roteiro deve obrigatoriamente se iniciar e encerrar.
_Avoid_: Base, hotel, início da viagem

**Deslocamento**:
Trajeto físico e tempo de trânsito estimado para transitar entre dois Pontos de Interesse consecutivos no modal urbano escolhido.
_Avoid_: Viagem, rota, percurso

**Matriz de Deslocamento**:
Tabela pré-calculada contendo as durações de trânsito e distâncias estimadas entre cada par de Pontos de Interesse elegíveis de uma Etapa de Viagem.
_Avoid_: Matriz de distâncias, tabela de custos

### Janelas e Políticas Temporais

**Janela de Disponibilidade**:
Intervalo contínuo de horário de início e fim no qual o usuário está disponível para executar o Roteiro de um Dia de Viagem.
_Avoid_: Janela de tempo, tempo livre, tempo disponível

**Janela de Funcionamento**:
Intervalo oficial diário de abertura e fechamento de um Ponto de Interesse no qual visitas são permitidas.
_Avoid_: Horário de abertura, horário comercial

**Tempo de Permanência**:
Duração estimada ou configurada que o visitante despende no interior de um Ponto de Interesse.
_Avoid_: Tempo de visita, duração, estadia

**Slot de Refeição**:
Janela temporal reservada no Roteiro dedicada a pausas alimentares (como almoço, café ou jantar), associada a recomendações contextuais de estabelecimentos e estimativa de gastos.
_Avoid_: Horário de almoço, parada para comer, intervalo de refeição

**Estimativa de Gastos**:
Projeção financeira calculada com base na categoria de custo da Hospedagem e no padrão orçamentário selecionado para os Slots de Refeição e deslocamentos.
_Avoid_: Orçamento, previsão de custo, gasto diário

**Pontuação de Utilidade**:
Métrica numérica que quantifica o valor de atratividade de um Ponto de Interesse para o usuário com base no Perfil de Preferência e avaliações.
_Avoid_: Score, relevância, peso do ponto

**Perfil de Preferência**:
Conjunto de categorias temáticas e intensidades numéricas (escala de 0 a 10) atribuídas pelo usuário para modular a Pontuação de Utilidade e disparar slots temáticos no Roteiro.
_Avoid_: Filtros, tags de usuário, estilo de viagem

### Adaptação Dinâmica

**Evento de Contingência**:
Ocorrência imprevista em tempo de execução (como atraso, fechamento prematuro ou cancelamento voluntário) ou *ajuste de permanência* (alteração da duração do Ponto de Interesse atual ou futuro) que invalida a programação temporal restante do Roteiro.
_Avoid_: Imprevisto, erro de percurso, incidente

**Replanejamento**:
Recálculo algorítmico do Roteiro restante a partir da coordenada e horário atuais após a ocorrência de um Evento de Contingência.
_Avoid_: Re-roteamento, reajuste, recalcular tudo

**Deslocamento em Cascata**:
Propagação automática de alterações na duração de uma Etapa de Viagem sobre o calendário das etapas e Conexões Interurbanas subsequentes, preservando suas durações relativas.
_Avoid_: Efeito dominó, shift de datas, replanejamento global
