"""Configuração compartilhada dos testes baseados em propriedades.

O gate completo executa a suíte dentro do mutmut, sob carga variável de CPU. O
prazo padrão de 200 ms do Hypothesis produz falhas de tempo intermitentes que
não indicam violação das invariantes; o perfil abaixo remove apenas esse prazo,
preservando todas as asserções dos testes de propriedade.
"""

from hypothesis import settings

settings.register_profile("kairos_sem_prazo", deadline=None)
settings.load_profile("kairos_sem_prazo")
