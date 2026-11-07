# 2. Adoção de Backend em Python com FastAPI e Interface Simples

## Contexto
O trabalho prático da disciplina DCC061 exige foco profundo em **Testes de Software e Qualidade de Software**, com ênfase na implementação e demonstração de técnicas formais. O desenvolvimento de uma SPA complexa (ex: React) adicionaria sobrecarga desnecessária de manutenção e dispersaria o esforço da equipe longe dos objetivos de testes e qualidade.

## Decisão
Implementamos o sistema em **Python** utilizando **FastAPI**, servindo uma interface web leve em HTML/Jinja2 com JavaScript puro (Vanilla JS) e Leaflet para renderização do mapa. Toda a lógica de negócio, modelo de domínio, heurísticas de roteamento e pipeline de qualidade residem no ecossistema Python.

## Consequências
- Foco concentrado na suíte de testes (`pytest`, `hypothesis`, `pytest-cov`, `mutmut`).
- Aplicação de padrões de qualidade e análise estática alinhados às normas ISO/IEC 25010 e ISO/IEC 5055 via ferramentas como `mypy` (tipagem estática rigorosa), `ruff` e `radon` (complexidade ciclomática).
- Interface web simples de carregar e sem etapa pesada de build (`npm build`).
