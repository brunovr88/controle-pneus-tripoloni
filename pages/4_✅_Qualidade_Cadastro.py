import plotly.express as px
import streamlit as st

from src.page_boot import boot
from src.theme import STATUS_BOM, STATUS_CRITICO, plotly_layout

_, df = boot("Qualidade do Cadastro", icone="✅")

ativos = df.drop_duplicates(subset=["PREFIXO"])[["PREFIXO", "OBRA_LOCAL", "STATUS_CADASTRO", "CLASSE"]].copy()
ativos["STATUS_CADASTRO"] = ativos["STATUS_CADASTRO"].fillna("NAO IDENTIFICADO").str.upper()

st.subheader("Painel de qualidade")
col1, col2 = st.columns([1, 2])

with col1:
    geral = ativos["STATUS_CADASTRO"].value_counts().reset_index()
    geral.columns = ["STATUS_CADASTRO", "QTDE"]
    fig_donut = px.pie(
        geral,
        names="STATUS_CADASTRO",
        values="QTDE",
        hole=0.55,
        color="STATUS_CADASTRO",
        color_discrete_map={"IDENTIFICADO": STATUS_BOM, "NAO IDENTIFICADO": STATUS_CRITICO},
    )
    fig_donut.update_layout(**plotly_layout(titulo="Geral (escopo filtrado)"))
    st.plotly_chart(fig_donut, use_container_width=True)

with col2:
    por_obra = ativos.groupby(["OBRA_LOCAL", "STATUS_CADASTRO"]).size().reset_index(name="QTDE")
    total_obra = por_obra.groupby("OBRA_LOCAL")["QTDE"].transform("sum")
    por_obra["PCT"] = por_obra["QTDE"] / total_obra * 100

    fig_barras = px.bar(
        por_obra,
        x="PCT",
        y="OBRA_LOCAL",
        color="STATUS_CADASTRO",
        orientation="h",
        color_discrete_map={"IDENTIFICADO": STATUS_BOM, "NAO IDENTIFICADO": STATUS_CRITICO},
        text=por_obra["QTDE"],
    )
    fig_barras.update_layout(**plotly_layout(titulo="% identificado × não identificado por obra"))
    fig_barras.update_layout(barmode="stack", xaxis_title="%", yaxis_title="", height=max(300, 28 * por_obra["OBRA_LOCAL"].nunique()))
    st.plotly_chart(fig_barras, use_container_width=True)

st.divider()

st.subheader("Inconsistências para correção")
st.caption("Ativos sem obra vinculada, sem medida cadastrada em alguma posição com pneu, ou marcados N/T.")

sem_obra = df[df["OBRA_LOCAL"].isna() | (df["OBRA_LOCAL"] == "")]["PREFIXO"].unique()
sem_medida = df[(df["QTDE"] > 0) & ((df["MEDIDA"] == "") | df["MEDIDA"].isna())]["PREFIXO"].unique()
marcado_nt = df[df["MEDIDA"].astype(str).str.upper().str.contains("N/T", na=False)]["PREFIXO"].unique()

inconsistentes = sorted(set(sem_obra) | set(sem_medida) | set(marcado_nt))
detalhe = []
for p in inconsistentes:
    motivos = []
    if p in sem_obra:
        motivos.append("sem obra vinculada")
    if p in sem_medida:
        motivos.append("sem medida cadastrada")
    if p in marcado_nt:
        motivos.append('marcado "N/T"')
    detalhe.append({"PREFIXO": p, "MOTIVO": ", ".join(motivos)})

st.dataframe(
    detalhe, use_container_width=True, hide_index=True, column_config={"PREFIXO": "Prefixo", "MOTIVO": "Motivo"}
)

if inconsistentes:
    prefixo_corrigir = st.selectbox("Corrigir um destes agora", inconsistentes)
    if st.button("Abrir na tela de edição do equipamento →"):
        # Não dá para setar st.session_state["filtro_prefixo"] aqui: o widget com essa
        # mesma key já foi criado nesta execução (dentro do boot() lá em cima). Por isso
        # usamos uma chave de handoff separada, que a página 5 consome antes de criar
        # o próprio widget de filtro.
        st.session_state["prefixo_para_corrigir"] = prefixo_corrigir
        st.switch_page("pages/5_🔧_Editar_Equipamento.py")
else:
    st.success("Nenhuma inconsistência encontrada no escopo filtrado.")
