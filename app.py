import pandas as pd
import streamlit as st

from src.calculations import calcular_estoque
from src.page_boot import boot

df, df_filtrado = boot("Controle de Pneus (Rodantes)")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ativos no escopo", df_filtrado["PREFIXO"].nunique())
col2.metric("Pneus rodando", int(df_filtrado["QTDE"].sum()))
col3.metric("Obras no escopo", df_filtrado["OBRA_LOCAL"].nunique())
col4.metric("Medidas distintas", df_filtrado["MEDIDA"].replace("", pd.NA).nunique())

st.divider()

st.subheader("Estoque recomendado por Obra × Medida")
estoque = calcular_estoque(df_filtrado[df_filtrado["MEDIDA"] != ""], ["OBRA_LOCAL", "MEDIDA"])
estoque = estoque.sort_values("QTDE_RODANDO", ascending=False)
st.dataframe(
    estoque.rename(
        columns={
            "OBRA_LOCAL": "Obra",
            "MEDIDA": "Medida",
            "QTDE_RODANDO": "Pneus rodando",
            "ESTOQUE_SOLICITADO": "Estoque solicitado (10%)",
            "ESTOQUE_MINIMO": "Estoque mínimo (20% do solicitado)",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Use o menu à esquerda para navegar entre as visões: Geográfica, Medidas, Frota, "
    "Qualidade do Cadastro e Editar Equipamento."
)
