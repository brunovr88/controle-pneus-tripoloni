"""Filtros globais (Obra, Modelo, Classe, Prefixo) com trava de RLS por obra."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import is_admin, obra_do_usuario
from src.calculations import aplicar_filtros


def render_filtros(df: pd.DataFrame) -> pd.DataFrame:
    obra_travada = obra_do_usuario()

    with st.sidebar:
        st.markdown("### Filtros")

        if obra_travada:
            st.caption(f"Obra: **{obra_travada}** (fixada pelo seu login)")
            obra_sel = obra_travada
        else:
            obras = sorted(df["OBRA_LOCAL"].dropna().unique().tolist())
            obra_sel = st.selectbox("Obra", ["(todas)"] + obras, key="filtro_obra")
            obra_sel = None if obra_sel == "(todas)" else obra_sel

        df_escopo = df if not obra_travada else df[df["OBRA_LOCAL"] == obra_travada]

        modelos = sorted(df_escopo["MODELO"].dropna().unique().tolist())
        modelo_sel = st.selectbox("Modelo do equipamento", ["(todos)"] + modelos, key="filtro_modelo")
        modelo_sel = None if modelo_sel == "(todos)" else modelo_sel

        classes = sorted(df_escopo["CLASSE"].dropna().unique().tolist())
        classe_sel = st.selectbox("Classe operacional", ["(todas)"] + classes, key="filtro_classe")
        classe_sel = None if classe_sel == "(todas)" else classe_sel

        prefixos = sorted(df_escopo["PREFIXO"].dropna().unique().tolist())
        prefixo_sel = st.selectbox("Equipamento (prefixo)", ["(todos)"] + prefixos, key="filtro_prefixo")
        prefixo_sel = None if prefixo_sel == "(todos)" else prefixo_sel

        placa_sel = st.text_input("Placa (busca parcial)", key="filtro_placa").strip() or None

    return aplicar_filtros(
        df, obra=obra_sel, modelo=modelo_sel, classe=classe_sel, prefixo=prefixo_sel, placa=placa_sel
    )
