"""Lista de medidas de pneu padronizadas (aba Medidas_Padrao no Sheets).

Usada para popular a lista suspensa de medida em pages/5 (Editar Equipamento)
-- campo de texto livre permitia grafias diferentes pra mesma medida (ex.:
"1000R20" vs "10.00R20" vs "10.00 R20"), problema que a propria planilha
original ja sinalizava (aba PADRONIZACAO MEDIDAS do Consolidado Pneus).
Editavel na tela de Administracao.
"""

from __future__ import annotations

import pandas as pd


def seed_inicial(df_pneus: pd.DataFrame) -> pd.DataFrame:
    """Ponto de partida: todas as medidas ja usadas nos dados atuais. Nao e uma
    lista "correta" de fabrica -- e so o que ja existe, pronta pra ser limpa
    (fundir grafias duplicadas, remover erro de digitacao) na tela de Admin."""
    medidas = sorted({str(m).strip() for m in df_pneus["MEDIDA"].dropna() if str(m).strip()})
    return pd.DataFrame({"MEDIDA": medidas})
