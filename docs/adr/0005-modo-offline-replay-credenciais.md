# 5. Isolamento de Credenciais e Modo Offline Replay para Avaliação Acadêmica

## Contexto
O sistema consome APIs do Google Maps Platform sob um plano privado. O código-fonte deve ser entregue publicamente via repositório Git ou Classroom para avaliação da disciplina DCC061, onde nem a banca examinadora nem os colegas de turma possuirão credenciais próprias ou faturamento ativo na Google Cloud. Além disso, testes automatizados em pipelines de CI não devem depender de conectividade externa nem incorrer em custos.

## Decisão
Implementamos um mecanismo de **Fallback Transparente com Modo Offline Replay**. A chave de API é injetada estritamente via variável de ambiente (`GOOGLE_MAPS_API_KEY`) ignorada pelo controle de versão (`.gitignore`). Quando a variável estiver ausente, o sistema entra automaticamente em modo Replay, servindo dados reais pré-gravados em SQLite/JSON para as cidades de demonstração (ex: São Paulo, Lima, Juiz de Fora), simulando respostas completas do Google Places e Google Routes.

## Consequências
- A banca examinadora consegue clonar, executar a aplicação e rodar 100% da suíte de testes com zero configuração de credenciais.
- Protege a cota e o sigilo financeiro da chave Google Pro da equipe.
- Garante total conformidade com a ISO/IEC 25010 no quesito de Confiabilidade e Tolerância a Falhas de Ambiente.
