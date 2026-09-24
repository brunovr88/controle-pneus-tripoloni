import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.page_boot import boot
from src.theme import AZUL_ESCURO_2, AZUL_MEDIO, AZUL_PRINCIPAL, CORES_POSICAO, plotly_layout

_, df = boot("Visão de Medidas", icone="📏")
df_medidas = df[df["MEDIDA"] != ""].copy()

st.subheader("Ranking de medidas por posição")
ranking = df_medidas.groupby(["MEDIDA", "POSICAO"], as_index=False)["QTDE"].sum()
ordem_medidas = ranking.groupby("MEDIDA")["QTDE"].sum().sort_values(ascending=False).index.tolist()

fig = px.bar(
    ranking,
    x="MEDIDA",
    y="QTDE",
    color="POSICAO",
    color_discrete_map=CORES_POSICAO,
    category_orders={"MEDIDA": ordem_medidas, "POSICAO": ["DIANTEIRO", "TRASEIRO", "STEP"]},
)
fig.update_layout(**plotly_layout())
fig.update_layout(xaxis_tickangle=-45, height=450)
st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Concentração por medida (Pareto — quais medidas respondem por 80% do volume)")
st.caption("Ajuda a decidir em quais medidas concentrar o estoque físico primeiro.")
pareto_medida = df_medidas.groupby("MEDIDA", as_index=False)["QTDE"].sum().sort_values("QTDE", ascending=False)
pareto_medida["PCT_ACUMULADO"] = pareto_medida["QTDE"].cumsum() / pareto_medida["QTDE"].sum() * 100

fig_pareto_medida = go.Figure()
fig_pareto_medida.add_bar(
    x=pareto_medida["MEDIDA"], y=pareto_medida["QTDE"], name="Pneus rodando", marker_color=AZUL_PRINCIPAL
)
fig_pareto_medida.add_trace(
    go.Scatter(
        x=pareto_medida["MEDIDA"],
        y=pareto_medida["PCT_ACUMULADO"],
        name="% acumulado",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=AZUL_ESCURO_2, width=2),
    )
)
fig_pareto_medida.add_hline(y=80, yref="y2", line_dash="dash", line_color=AZUL_MEDIO, annotation_text="80%")
layout_pareto_medida = plotly_layout()
layout_pareto_medida["yaxis"].update(title="Pneus rodando")
layout_pareto_medida["xaxis"].update(title="", tickangle=-45)
layout_pareto_medida["yaxis2"] = dict(title="% acumulado", overlaying="y", side="right", range=[0, 105])
layout_pareto_medida["height"] = 460
fig_pareto_medida.update_layout(**layout_pareto_medida)
st.plotly_chart(fig_pareto_medida, use_container_width=True)

n_medidas_80 = int((pareto_medida["PCT_ACUMULADO"] <= 80).sum()) + 1
st.caption(f"{n_medidas_80} de {len(pareto_medida)} medidas concentram 80% do volume de pneus.")

st.divider()

st.subheader("Alerta de medidas críticas")
st.caption(
    "Medidas com poucos ativos rodando (risco alto em caso de quebra, sem substituto imediato "
    "no estoque local). Ajuste o limite conforme a realidade operacional."
)
limite = st.slider("Considerar crítica quando nº de ativos com a medida for ≤", 1, 10, 3)

por_medida = (
    df_medidas.groupby("MEDIDA")
    .agg(ATIVOS=("PREFIXO", "nunique"), QTDE_TOTAL=("QTDE", "sum"), CLASSES=("CLASSE", lambda s: ", ".join(sorted(set(s.dropna())))))
    .reset_index()
    .sort_values("ATIVOS")
)
criticas = por_medida[por_medida["ATIVOS"] <= limite]
st.dataframe(
    criticas.rename(
        columns={"MEDIDA": "Medida", "ATIVOS": "Ativos que usam", "QTDE_TOTAL": "Pneus rodando", "CLASSES": "Classes afetadas"}
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Oportunidade de padronização")
st.caption("Modelos de equipamento rodando com mais de uma medida de pneu — candidatos a unificação.")
por_modelo = df_medidas.groupby("MODELO")["MEDIDA"].nunique().reset_index(name="QTD_MEDIDAS_DISTINTAS")
modelos_divergentes = por_modelo[por_modelo["QTD_MEDIDAS_DISTINTAS"] > 1]["MODELO"]

detalhe = (
    df_medidas[df_medidas["MODELO"].isin(modelos_divergentes)]
    .groupby(["MODELO", "MEDIDA"])
    .agg(ATIVOS=("PREFIXO", "nunique"), QTDE=("QTDE", "sum"))
    .reset_index()
    .sort_values(["MODELO", "QTDE"], ascending=[True, False])
)
st.dataframe(
    detalhe.rename(columns={"MODELO": "Modelo", "MEDIDA": "Medida", "ATIVOS": "Ativos", "QTDE": "Pneus"}),
    use_container_width=True,
    hide_index=True,
)
