"""Boilerplate comum a toda pagina: login, CSS, logo, dataset e filtros."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import exigir_login, logout, usuario_logado
from src.dataset import carregar_dataset
from src.filtros import render_filtros
from src.theme import CUSTOM_CSS


def boot(titulo: str, icone: str = "🛞") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (df_completo, df_filtrado). Para o app se nao logado ou sem dados."""
    st.set_page_config(page_title=f"{titulo} — Tripoloni", page_icon=icone, layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    exigir_login()
    user = usuario_logado()

    with st.sidebar:
        try:
            st.image("LOGO-HORIZONTAL-BRANCA.png", use_container_width=True)
        except Exception:
            st.markdown("### TRIPOLONI")
        st.markdown(f"**{user['NOME']}**  \n_{user['PERFIL']}_")
        if st.button("Sair"):
            logout()

    st.title(titulo)

    df = carregar_dataset()
    if df.empty:
        st.warning("Sem dados no Google Sheets ainda. Rode a migração inicial (scripts/migrar_para_sheets.py).")
        st.stop()

    df_filtrado = render_filtros(df)
    return df, df_filtrado
