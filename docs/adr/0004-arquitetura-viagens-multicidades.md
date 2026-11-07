# 4. Arquitetura de Viagens Multicidades com Decomposição em Etapas Urbanas

## Contexto
O usuário pode planejar jornadas que englobam mais de uma localidade (ex: São Paulo conectada a Lima via transporte aéreo). Modelar cidades distantes em uma única matriz global de roteamento OPTW seria inviável computacionalmente e incompatível com os modais urbanos (caminhada/carro), além de misturar horários de voos com janelas de visitação a museus e atrações.

## Decisão
Adotamos uma estrutura hierárquica composta por **Viagem**, **Etapas de Viagem** (locais por cidade) e **Conexões Interurbanas** (com suporte a modais como `flying`, `driving` de longa distância e `train`). A otimização via OPTW é aplicada de forma isolada e modular dentro de cada Etapa Urbana, enquanto as Conexões Interurbanas estabelecem os limites temporais rígidos de chegada e partida em cada destino.

## Consequências
- Alta modularidade e separação de preocupações: o motor de otimização urbana é desacoplado do planejamento logístico de voos/transporte intercidades.
- A adaptação dinâmica por contingência pode ser executada isoladamente dentro de uma etapa sem invalidar toda a viagem, a menos que um atraso urbano comprometa o horário da Conexão Interurbana (ex: perda de voo).
- Permite demonstrar testes sofisticados de propagação de atrasos entre etapas de viagem.
