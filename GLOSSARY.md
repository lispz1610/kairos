# Kairos — Traçador Dinâmico de Rotas Turísticas

Sistema de recomendação e otimização de itinerários turísticos personalizados com restrições temporais e espaciais.

## Language

### Estrutura da Jornada

**Viagem**:
Planejamento global composto por uma sequência ordenada de Etapas de Viagem interligadas por Conexões Interurbanas.
_Avoid_: Roteiro global, itinerário completo, projeto de viagem

**Etapa de Viagem**:
Subconjunto temporal e geográfico de uma Viagem restrito a uma cidade ou região delimitada, contendo sua própria Janela de Disponibilidade e Pontos de Interesse elegíveis.
_Avoid_: Set, bloco de cidade, dia de viagem, trecho urbano

**Conexão Interurbana**:
Transição de longa distância conectando o término de uma Etapa de Viagem ao início da etapa subsequente, operando sob modais intermunicipais (como aéreo `flying` ou rodoviário).
_Avoid_: Voo, viagem entre cidades, transição

**Modal de Transporte**:
Meio físico utilizado para locomoção, distinguindo-se entre transporte urbano (`walking`, `driving`) e interurbano (`flying`, `transit`).
_Avoid_: Tipo de locomoção, meio de transporte

### Roteiro Urbano e Pontos de Interesse

**Ponto de Interesse (POI)**:
Local geográfico delimitado com relevância turística, cultural ou de lazer elegível para visitação, dotado de coordenadas e horário de funcionamento.
_Avoid_: Atração, parada, local turístico, parada turística

**Roteiro**:
Sequência cronológica ordenada de visitas a Pontos de Interesse programadas para ocorrer dentro da Janela de Disponibilidade de uma Etapa de Viagem.
_Avoid_: Itinerário, percurso, plano de viagem

**Ponto de Partida/Retorno**:
Coordenada geográfica fixa (como hotel, aeroporto ou estação) onde o Roteiro de uma Etapa de Viagem deve obrigatoriamente se iniciar e encerrar.
_Avoid_: Base, hotel, início da viagem

**Deslocamento**:
Trajeto físico e tempo de trânsito estimado para transitar entre dois Pontos de Interesse consecutivos no modal urbano escolhido.
_Avoid_: Viagem, rota, percurso

**Matriz de Deslocamento**:
Tabela pré-calculada contendo as durações de trânsito e distâncias estimadas entre cada par de Pontos de Interesse elegíveis de uma Etapa de Viagem.
_Avoid_: Matriz de distâncias, tabela de custos

### Janelas e Políticas Temporais

**Janela de Disponibilidade**:
Intervalo contínuo de horário de início e fim no qual o usuário está disponível para executar o Roteiro de uma Etapa de Viagem.
_Avoid_: Janela de tempo, tempo livre, tempo disponível

**Janela de Funcionamento**:
Intervalo oficial diário de abertura e fechamento de um Ponto de Interesse no qual visitas são permitidas.
_Avoid_: Horário de abertura, horário comercial

**Tempo de Permanência**:
Duração estimada ou configurada que o visitante despende no interior de um Ponto de Interesse.
_Avoid_: Tempo de visita, duração, estadia

**Pontuação de Utilidade**:
Métrica numérica que quantifica o valor de atratividade de um Ponto de Interesse para o usuário com base no Perfil de Preferência e avaliações.
_Avoid_: Score, relevância, peso do ponto

**Perfil de Preferência**:
Conjunto de categorias temáticas e pesos atribuídos pelo usuário para ranquear e selecionar Pontos de Interesse.
_Avoid_: Filtros, tags de usuário, estilo de viagem

### Adaptação Dinâmica

**Evento de Contingência**:
Ocorrência imprevista em tempo de execução (como atraso, fechamento prematuro ou cancelamento voluntário) que invalida a programação temporal restante do Roteiro.
_Avoid_: Imprevisto, erro de percurso, incidente

**Replanejamento**:
Recálculo algorítmico do Roteiro restante a partir da coordenada e horário atuais após a ocorrência de um Evento de Contingência.
_Avoid_: Re-roteamento, reajuste, recalcular tudo
