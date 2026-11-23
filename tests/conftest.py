"""Perfil opcional do Hypothesis para o gate de mutação.

Sob ``mutmut`` a CPU varia e o prazo padrão pode falhar sem indicar uma
invariante violada. Com ``KAIROS_MUTATION=1`` o perfil remove apenas esse prazo;
as demais execuções mantêm os prazos normais do Hypothesis.
"""

import os

from hypothesis import settings

if os.environ.get("KAIROS_MUTATION") == "1":
    settings.register_profile("kairos_sem_prazo", deadline=None)
    settings.load_profile("kairos_sem_prazo")
