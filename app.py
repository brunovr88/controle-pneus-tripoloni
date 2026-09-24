import pandas as pd
import streamlit as st

from src.page_boot import boot

df, df_filtrado = boot("Controle de Pneus (Rodantes)")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ativos no escopo", df_filtrado["PREFIXO"].nunique())
col2.metric("Pneus rodando", int(df_filtrado["QTDE"].sum()))
col3.metric("Obras no escopo", df_filtrado["OBRA_LOCAL"].nunique())
col4.metric("Medidas distintas", df_filtrado["MEDIDA"].replace("", pd.NA).nunique())

st.divider()

st.caption(
    "Use o menu à esquerda para navegar entre as visões: Geográfica, Medidas, Frota, "
    "Qualidade do Cadastro, **Estoque** (estoque solicitado/mínimo/físico por obra e medida), "
    "Editar Equipamento e Edição em Massa."
)
