import plotly.express as px
import streamlit as st

from src.page_boot import boot
from src.theme import AZUL_MEDIO, AZUL_PRINCIPAL, plotly_layout

_, df = boot("Visão da Frota", icone="🚜")

st.subheader("Distribuição por classe operacional")
por_classe = df.groupby("CLASSE", as_index=False)["QTDE"].sum().sort_values("QTDE", ascending=True).tail(20)
fig_classe = px.bar(por_classe, x="QTDE", y="CLASSE", orientation="h", color_discrete_sequence=[AZUL_PRINCIPAL])
fig_classe.update_layout(**plotly_layout())
fig_classe.update_layout(height=500, yaxis_title="", xaxis_title="Pneus rodando")
st.plotly_chart(fig_classe, use_container_width=True)

st.subheader("Distribuição por fabricante / modelo")
por_modelo = (
    df.groupby(["FABRICANTE", "MODELO"], as_index=False)["QTDE"]
    .sum()
    .sort_values("QTDE", ascending=True)
    .tail(20)
)
por_modelo["FABRICANTE_MODELO"] = por_modelo["FABRICANTE"].fillna("N/D") + " — " + por_modelo["MODELO"].fillna("N/D")
fig_modelo = px.bar(por_modelo, x="QTDE", y="FABRICANTE_MODELO", orientation="h", color_discrete_sequence=[AZUL_PRINCIPAL])
fig_modelo.update_layout(**plotly_layout())
fig_modelo.update_layout(height=500, yaxis_title="", xaxis_title="Pneus rodando")
st.plotly_chart(fig_modelo, use_container_width=True)

st.divider()

st.subheader("Categorização técnica")
st.caption(
    "Veículo × Máquina e Radial × Diagonal são inferidos a partir do Subgrupo da Frota "
    "(ver mapeamento em src/calculations.py) — valide com a equipe de frota antes de usar em decisão de compra."
)
col1, col2 = st.columns(2)
with col1:
    tipo = df.groupby("TIPO_VEICULO", as_index=False)["QTDE"].sum()
    fig_tipo = px.pie(tipo, names="TIPO_VEICULO", values="QTDE", color_discrete_sequence=[AZUL_PRINCIPAL, AZUL_MEDIO], hole=0.5)
    fig_tipo.update_layout(**plotly_layout(titulo="Veículo × Máquina"))
    st.plotly_chart(fig_tipo, use_container_width=True)
with col2:
    montagem = df.groupby("MONTAGEM", as_index=False)["QTDE"].sum()
    fig_mont = px.pie(montagem, names="MONTAGEM", values="QTDE", color_discrete_sequence=[AZUL_PRINCIPAL, AZUL_MEDIO], hole=0.5)
    fig_mont.update_layout(**plotly_layout(titulo="Radial × Diagonal"))
    st.plotly_chart(fig_mont, use_container_width=True)

st.divider()

st.subheader("Auditoria por ativo")
por_ativo = df.groupby(["PREFIXO", "CLASSE"], as_index=False)["QTDE"].sum().rename(columns={"QTDE": "TOTAL_PNEUS"})

resumo_classe = por_ativo.groupby("CLASSE")["TOTAL_PNEUS"].agg(["mean", "max"]).reset_index()
resumo_classe.columns = ["Classe", "Média de pneus/ativo", "Máximo de pneus/ativo"]
resumo_classe["Média de pneus/ativo"] = resumo_classe["Média de pneus/ativo"].round(1)
st.dataframe(resumo_classe.sort_values("Máximo de pneus/ativo", ascending=False), use_container_width=True, hide_index=True)

st.markdown("**Cadastros estranhos** (ativo com 0 pneus ou 16+ pneus — confira o cadastro)")
estranhos = por_ativo[(por_ativo["TOTAL_PNEUS"] == 0) | (por_ativo["TOTAL_PNEUS"] >= 16)].sort_values(
    "TOTAL_PNEUS", ascending=False
)
st.dataframe(
    estranhos.rename(columns={"PREFIXO": "Prefixo", "CLASSE": "Classe", "TOTAL_PNEUS": "Total de pneus"}),
    use_container_width=True,
    hide_index=True,
)
