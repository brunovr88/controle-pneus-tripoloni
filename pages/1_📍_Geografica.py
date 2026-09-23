import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.page_boot import boot
from src.theme import AZUL_ESCURO_2, AZUL_MEDIO, AZUL_PRINCIPAL, RAMPA_SEQUENCIAL, plotly_layout

_, df = boot("Visão Geográfica e Distribuição", icone="📍")

st.subheader("Mapa de pneus por obra")
por_obra = (
    df.groupby(["OBRA_LOCAL", "CIDADE", "UF", "LATITUDE", "LONGITUDE"], as_index=False)["QTDE"]
    .sum()
    .dropna(subset=["LATITUDE", "LONGITUDE"])
)

if por_obra.empty:
    st.info("Nenhuma obra com coordenadas cadastradas em LOCAL para plotar no mapa.")
else:
    fig_mapa = px.scatter_mapbox(
        por_obra,
        lat="LATITUDE",
        lon="LONGITUDE",
        size="QTDE",
        color="QTDE",
        color_continuous_scale=RAMPA_SEQUENCIAL,
        hover_name="OBRA_LOCAL",
        hover_data={"CIDADE": True, "UF": True, "QTDE": True, "LATITUDE": False, "LONGITUDE": False},
        zoom=3,
        height=480,
    )
    fig_mapa.update_layout(**plotly_layout())
    fig_mapa.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_mapa, use_container_width=True)

st.divider()

st.subheader("Matriz de estoque — Obra × Medida")
matriz = df[df["MEDIDA"] != ""].pivot_table(
    index="OBRA_LOCAL", columns="MEDIDA", values="QTDE", aggfunc="sum", fill_value=0
)
if matriz.empty:
    st.info("Sem medidas cadastradas para montar a matriz.")
else:
    st.dataframe(
        matriz.style.background_gradient(cmap="Blues", axis=None),
        use_container_width=True,
    )

st.divider()

st.subheader("Concentração por obra (Pareto — quem responde por 80% dos pneus)")
pareto = df.groupby("OBRA_LOCAL", as_index=False)["QTDE"].sum().sort_values("QTDE", ascending=False)
pareto["PCT_ACUMULADO"] = pareto["QTDE"].cumsum() / pareto["QTDE"].sum() * 100

fig_pareto = go.Figure()
fig_pareto.add_bar(x=pareto["OBRA_LOCAL"], y=pareto["QTDE"], name="Pneus rodando", marker_color=AZUL_PRINCIPAL)
fig_pareto.add_trace(
    go.Scatter(
        x=pareto["OBRA_LOCAL"],
        y=pareto["PCT_ACUMULADO"],
        name="% acumulado",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=AZUL_ESCURO_2, width=2),
    )
)
fig_pareto.add_hline(y=80, yref="y2", line_dash="dash", line_color=AZUL_MEDIO, annotation_text="80%")
layout_pareto = plotly_layout()
layout_pareto["yaxis"].update(title="Pneus rodando")
layout_pareto["xaxis"].update(title="", tickangle=-45)
layout_pareto["yaxis2"] = dict(title="% acumulado", overlaying="y", side="right", range=[0, 105])
layout_pareto["height"] = 460
fig_pareto.update_layout(**layout_pareto)
st.plotly_chart(fig_pareto, use_container_width=True)

n_obras_80 = int((pareto["PCT_ACUMULADO"] <= 80).sum()) + 1
st.caption(
    f"{n_obras_80} de {len(pareto)} obras concentram 80% do volume de pneus — "
    "candidatas naturais para estoque físico centralizado / oficina central."
)
