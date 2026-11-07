# 7. Gestão de Hospedagens, Curadoria Enriquecida e Estado Client-Side

## Contexto
O planejamento ponta-a-ponta de viagens multicidades exige organizar múltiplos dias de permanência por cidade, selecionar hospedagens dinâmicas (com trocas eventuais de hotel), recomendar gastronomia contextual e gerenciar orçamentos estimados. Além disso, o sistema deve evitar brechas de segurança e complexidade operacional com autenticação ou bancos de dados relacionais de usuários no servidor, mantendo portabilidade e facilidade de exportação em Markdown.

## Decisão
Adotamos as seguintes diretrizes arquiteturais e funcionais:
1. **Decomposição em Dias de Viagem e Hospedagem Dinâmica**: A *Etapa de Viagem* é estruturada em uma sequência de *Dias de Viagem*. O usuário define uma *Hospedagem Base* para a etapa, com permissão de sobreposição por dia. A hospedagem ativa no dia atua como o *Ponto de Partida/Retorno* para o solver OPTW daquele Roteiro.
2. **Slots de Refeição e Pausas Temáticas Contextuais**: O Roteiro aloca janelas dedicadas de refeição sugerindo os melhores estabelecimentos por proximidade com a atração anterior. Perfis de interesse (escala 0 a 10) com intensidade $\ge 5$ ativam automaticamente pausas temáticas específicas (ex: coffee break às 15h30 para *Coffee Lover* e wine bar às 18h para *Wine Lover*).
3. **Curadoria Híbrida Enriquecida**: Cruzamento de dados da Google Places API com listas públicas curadas (Michelin, 50 Best, Specialty Coffee) e listas próprias criadas pelo usuário via busca guiada ou parser seguro de links/textos no backend com proteção contra SSRF.
4. **Deslocamento em Cascata (Ripple Shift)**: Alterações na quantidade de dias de uma etapa preservam as durações relativas das etapas subsequentes, recalculando datas e alertando o usuário sobre o impacto nas Conexões Interurbanas através de confirmação visual.
5. **Estado Client-Side e Exportação em Markdown**: Todo o estado da jornada reside no `localStorage` do navegador, com capacidade de backup e restauração via JSON. O backend FastAPI permanece *stateless*. O sistema disponibiliza exportação completa do itinerário em Markdown estruturado com visualização, cópia direta e download `.md`.

## Consequências
- Elimina completamente vulnerabilidades e custos associados a bancos de dados de sessão, autenticação e armazenamento de dados sensíveis no backend.
- Permite que o viajante exporte um guia de viagem rico em Markdown compatível com qualquer leitor de notas (Obsidian, Notion, etc.).
- Requer que o cliente envie o contexto completo do dia (ou da etapa) nas requisições de otimização para os endpoints da API FastAPI.
