"""Paleta de marca Tripoloni e template Plotly derivado dela.

A marca fornece apenas tons de azul (nenhum hue distinto para uso categorico
com muitas series). Por isso:
  - Os 4 azuis servem para: fundo/chrome, rampa sequencial (mapa, heatmap,
    barras ranqueadas de 1 serie) e comparacoes binarias (2 categorias).
  - Para status (bom/atencao/critico) usamos uma escala reservada e separada
    da identidade de marca -- pratica padrao mesmo em dashboards com paleta
    fechada, exigida aqui porque o proprio escopo pede "destacar inconsistencias"
    e "medidas criticas", que sao estados, nao series.
"""

AZUL_PRINCIPAL = "#1B2C8C"
AZUL_MEDIO = "#646A8C"
AZUL_ESCURO_1 = "#172E73"
AZUL_ESCURO_2 = "#162759"
CINZA_CLARO = "#F2F2F2"
BRANCO = "#FFFFFF"

# Rampa sequencial (magnitude: mapa, matriz de estoque, Pareto) do claro ao escuro.
RAMPA_SEQUENCIAL = ["#D8DCF3", "#93A0DC", AZUL_PRINCIPAL, AZUL_ESCURO_1, AZUL_ESCURO_2]

# Categoria de posicao do pneu (3 valores fixos -- ordem nunca muda).
CORES_POSICAO = {
    "DIANTEIRO": AZUL_PRINCIPAL,
    "TRASEIRO": AZUL_MEDIO,
    "STEP": AZUL_ESCURO_1,
}

# Escala de status reservada (nao reusar para "serie 4"). Sempre com icone/texto junto.
STATUS_BOM = "#1B2C8C"       # reaproveita o azul principal como "normal"
STATUS_ATENCAO = "#B8860B"   # ambar corporativo
STATUS_CRITICO = "#B3261E"   # vermelho desaturado

TEXTO_PRIMARIO = "#1A1A2E"
TEXTO_SECUNDARIO = AZUL_MEDIO
GRID = "#D9DCE8"

FONTE = "Segoe UI, Arial, sans-serif"


def plotly_layout(titulo: str | None = None) -> dict:
    """Layout Plotly padrao com a paleta Tripoloni."""
    return dict(
        title=titulo,
        paper_bgcolor=CINZA_CLARO,
        plot_bgcolor=BRANCO,
        font=dict(family=FONTE, color=TEXTO_PRIMARIO, size=13),
        colorway=[AZUL_PRINCIPAL, AZUL_MEDIO, AZUL_ESCURO_1, AZUL_ESCURO_2],
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=40, b=10),
    )


CUSTOM_CSS = f"""
<style>
    .stApp {{
        background-color: {CINZA_CLARO};
    }}
    section[data-testid="stSidebar"] {{
        background-color: {AZUL_ESCURO_2};
    }}
    section[data-testid="stSidebar"] * {{
        color: {CINZA_CLARO} !important;
    }}
    h1, h2, h3, h4 {{
        color: {AZUL_ESCURO_2};
        font-family: {FONTE};
    }}
    div[data-testid="stMetric"] {{
        background-color: {BRANCO};
        border: 1px solid {GRID};
        border-left: 4px solid {AZUL_PRINCIPAL};
        border-radius: 6px;
        padding: 12px 16px;
    }}
    div[data-testid="stMetricLabel"] {{
        color: {AZUL_MEDIO};
    }}
    .stButton>button {{
        background-color: {AZUL_PRINCIPAL};
        color: {BRANCO};
        border: none;
        border-radius: 4px;
    }}
    .stButton>button:hover {{
        background-color: {AZUL_ESCURO_1};
        color: {BRANCO};
    }}
    div[data-baseweb="tab-list"] button[aria-selected="true"] {{
        color: {AZUL_PRINCIPAL};
        border-bottom-color: {AZUL_PRINCIPAL};
    }}
</style>
"""
