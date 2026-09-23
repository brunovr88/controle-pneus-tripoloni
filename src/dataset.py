"""Ponto unico para carregar e juntar Pneus + Frota + Local a partir do Sheets."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.calculations import montar_dataset
from src.sheets_client import ABA_FROTA, ABA_LOCAL, ABA_PNEUS, carregar_aba


@st.cache_data(ttl=120, show_spinner="Montando visão consolidada...")
def carregar_dataset() -> pd.DataFrame:
    df_pneus = carregar_aba(ABA_PNEUS)
    df_frota = carregar_aba(ABA_FROTA)
    df_local = carregar_aba(ABA_LOCAL)

    if df_pneus.empty or df_frota.empty:
        return pd.DataFrame()

    df_pneus["QTDE"] = pd.to_numeric(df_pneus["QTDE"], errors="coerce").fillna(0).astype(int)
    return montar_dataset(df_pneus, df_frota, df_local)
