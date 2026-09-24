"""Regras de calculo e montagem do dataset analitico (Pneus + Frota + Local).

Ponto de atencao herdado da planilha original: a coluna LOCAL que vinha na
CONSOLIDADO_PNEUS_POR_ATIVO era um texto curto (ex.: "ASSIS-SP") que NAO bate
com a granularidade real de obra (ex.: existem "EQUIPAMENTOS TERCEIROS - OBRA 422
ASSIS SP" e "MANUT. E PECAS DE EQUIPAMENTOS PROPRIOS - OBRA 422 ASSIS SP" como
duas obras distintas na mesma cidade). Por isso essa coluna NAO foi migrada para
o Google Sheets -- a obra de cada pneu e sempre resolvida via
Pneus.PREFIXO -> Frota.PREFIXO -> Frota.OBRA_LOCAL -> Local.OBRA_LOCAL.
"""

from __future__ import annotations

import math

import pandas as pd

# Mapeamento de negocio SUBGRUPO -> categoria tecnica. E um ponto de partida
# razoavel a partir dos 15 subgrupos encontrados na Frota; a equipe de
# engenharia/frota deve validar e ajustar esta tabela antes de confiar nela
# em decisoes de estoque.
SUBGRUPO_TIPO_VEICULO = {
    "CAMINHAO": "VEICULO",
    "CARGA SEMI-REBOQUE": "VEICULO",
    "VEICULOS PEQUENOS": "VEICULO",
    "EQUIPAMENTOS LEVES": "VEICULO",
    "CONTAINER": "VEICULO",
    "BALANCAS": "MAQUINA",
    "BRITAGEM": "MAQUINA",
    "GERADOR": "MAQUINA",
    "IMPLEMENTOS": "MAQUINA",
    "MAQUINA DE CORTE": "MAQUINA",
    "MAQUINAS PESADAS": "MAQUINA",
    "USINA DE ASFALTO": "MAQUINA",
    "USINA DE CONCRETO": "MAQUINA",
    "USINA DE SOLOS": "MAQUINA",
}

# Regra citada na propria planilha (aba PADRONIZACAO MEDIDAS): veiculo rodoviario
# roda radial, maquina fora-de-estrada roda diagonal. Mesma ressalva acima.
TIPO_VEICULO_MONTAGEM = {
    "VEICULO": "RADIAL",
    "MAQUINA": "DIAGONAL",
}


def extrair_classe(grupo: str) -> str:
    """'CBM - CAMINHAO BASCULANTE MINERIO' -> 'CBM'."""
    if not grupo or not isinstance(grupo, str):
        return "N/D"
    return grupo.split(" - ")[0].strip()


def montar_dataset(df_pneus: pd.DataFrame, df_frota: pd.DataFrame, df_local: pd.DataFrame) -> pd.DataFrame:
    """Junta as 3 tabelas em um dataset longo (1 linha por PREFIXO+POSICAO)."""
    frota = df_frota.copy()
    frota["CLASSE"] = frota["GRUPO"].apply(extrair_classe)
    frota["TIPO_VEICULO"] = frota["SUBGRUPO"].map(SUBGRUPO_TIPO_VEICULO).fillna("MAQUINA")
    frota["MONTAGEM"] = frota["TIPO_VEICULO"].map(TIPO_VEICULO_MONTAGEM)

    base = df_pneus.merge(frota, on="PREFIXO", how="left", suffixes=("", "_FROTA"))
    base = base.merge(
        df_local, left_on="OBRA_LOCAL", right_on="OBRA_LOCAL", how="left", suffixes=("", "_LOCAL")
    )

    base["QTDE"] = pd.to_numeric(base["QTDE"], errors="coerce").fillna(0).astype(int)
    for col in ("LATITUDE", "LONGITUDE"):
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce")

    return base


PCT_SOLICITADO_PADRAO = 0.10
PCT_MINIMO_PADRAO = 0.20


def calcular_estoque(
    df: pd.DataFrame,
    group_cols: list[str],
    pct_solicitado: float = PCT_SOLICITADO_PADRAO,
    pct_minimo: float = PCT_MINIMO_PADRAO,
) -> pd.DataFrame:
    """Estoque Solicitado = floor(pct_solicitado * qtde total rodando).
    Estoque Minimo = floor(pct_minimo * Estoque Solicitado) -- o "gatilho de compra":
    quando o estoque FISICO cai pra esse nivel (ou abaixo), pede-se reposicao ate
    o Estoque Solicitado.

    group_cols tipicamente ['OBRA_LOCAL', 'MEDIDA'] -- estoque e por obra+medida,
    porque e o par que define "o que comprar e onde guardar". Os percentuais tem
    default 10%/20% mas sao ajustaveis (ver aba Parametros / tela Administracao).
    """
    agrupado = df.groupby(group_cols, as_index=False)["QTDE"].sum().rename(columns={"QTDE": "QTDE_RODANDO"})
    agrupado["ESTOQUE_SOLICITADO"] = agrupado["QTDE_RODANDO"].apply(lambda q: math.floor(q * pct_solicitado))
    agrupado["ESTOQUE_MINIMO"] = agrupado["ESTOQUE_SOLICITADO"].apply(lambda q: math.floor(q * pct_minimo))
    return agrupado


def aplicar_filtros(
    df: pd.DataFrame,
    obra: str | None = None,
    modelo: str | None = None,
    classe: str | None = None,
    prefixo: str | None = None,
    placa: str | None = None,
) -> pd.DataFrame:
    out = df
    if obra:
        out = out[out["OBRA_LOCAL"] == obra]
    if modelo:
        out = out[out["MODELO"] == modelo]
    if classe:
        out = out[out["CLASSE"] == classe]
    if prefixo:
        out = out[out["PREFIXO"] == prefixo]
    if placa:
        out = out[out["PLACA"].astype(str).str.contains(placa, case=False, na=False, regex=False)]
    return out
