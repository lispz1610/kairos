# 6. Navegação em Duas Camadas: Mapa Macro Geodésico e Detalhe Urbano

## Contexto
Em viagens multicidades (ex: São Paulo a Lima), rotas terrestres completas entre continentes ou países são inviáveis ou desprovidas de sentido turístico. Além disso, sobrecarregar o mapa principal com centenas de curvas e paradas urbanas simultâneas de diferentes países degrada a usabilidade e a clareza da interface.

## Decisão
Adotamos uma navegação em duas camadas na interface web:
1. **Visão Macro (Página Principal)**: Exibe um mapa global contendo marcadores das cidades que possuem projetos cadastrados, conectadas exclusivamente por linhas retas/geodésicas indicando o fluxo da Viagem e os modais interurbanos (`flying`).
2. **Visão Micro (Detalhe da Etapa Urbana)**: Ao selecionar uma cidade, o usuário entra na visão detalhada com o mapa local (Leaflet), a rota urbana otimizada pelo solver OPTW e a linha do tempo com os botões de simulação de contingência.

## Consequências
- Interface limpa e responsiva, sem poluição visual no mapa global.
- Desacoplamento claro entre a logística global da viagem e a roteirização pontual de cada destino.
