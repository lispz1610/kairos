# 1. Formulação do Problema como Orienteering Problem with Time Windows (OPTW)

## Contexto
O planejamento de roteiros turísticos precisa lidar com múltiplos Pontos de Interesse (POIs) e janelas temporais restritas dos usuários e dos estabelecimentos. A abordagem clássica do Problema do Caixeiro Viajante (TSP) exige visitar todos os pontos fornecidos, tornando a rota inviável quando o tempo total excede a Janela de Disponibilidade do usuário.

## Decisão
Modelamos o núcleo de roteirização como uma variação do **Orienteering Problem with Time Windows (OPTW)** em vez de TSP. O sistema seleciona e sequencia um subconjunto viável de POIs que maximiza a Pontuação de Utilidade acumulada, respeitando os horários de abertura e fechamento dos locais e a Janela de Disponibilidade global do visitante.

## Consequências
- Permite que o usuário defina cidades com centenas de POIs sem que o sistema falhe por sobrecarga temporal.
- Exige algoritmos heurísticos/meta-heurísticos (inserção gulosa com busca local ou GRASP) capazes de avaliar tanto a seleção de subconjunto quanto o sequenciamento sob restrições de tempo.
