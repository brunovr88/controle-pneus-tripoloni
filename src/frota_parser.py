"""Leitura/limpeza do arquivo "Consolidado Frota".

Usado tanto na carga inicial (scripts/migrar_para_sheets.py) quanto nas
sincronizacoes seguintes (scripts/sincronizar_frota.py). O NOME do arquivo pode
mudar a cada exportacao (ex.: "CONSOLIDADO FROTA 16.09.2026.xlsx", depois
"... 23.09.2026.xlsx", etc.) -- o que precisa se manter e a estrutura de colunas.
Se a estrutura mudar de verdade, ler_frota_bruta falha alto e cedo em vez de
seguir com colunas faltando.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.calculations import extrair_classe

COLUNAS_RENOMEAR = {
    "Prefixo-Bem": "PREFIXO",
    "Local-Obra": "OBRA_LOCAL",
    "Grupo": "GRUPO",
    "Subgrupo": "SUBGRUPO",
    "Marca": "FABRICANTE",
    "Modelo": "MODELO",
    "Ano": "ANO",
    "Placa": "PLACA",
}
COLUNAS_FINAIS = ["PREFIXO", "OBRA_LOCAL", "GRUPO", "SUBGRUPO", "FABRICANTE", "MODELO", "ANO", "PLACA", "CLASSE"]


def ler_frota_bruta(caminho: str | Path) -> pd.DataFrame:
    df = pd.read_excel(caminho, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns=COLUNAS_RENOMEAR)

    faltando = [c for c in COLUNAS_RENOMEAR.values() if c not in df.columns]
    if faltando:
        raise ValueError(
            f"'{caminho}' nao tem as colunas esperadas do Consolidado Frota: {faltando}. "
            "A estrutura do arquivo mudou -- confira as colunas antes de sincronizar."
        )

    df = df[list(COLUNAS_RENOMEAR.values())].copy()
    df["PREFIXO"] = df["PREFIXO"].astype(str).str.strip()
    df["OBRA_LOCAL"] = df["OBRA_LOCAL"].astype(str).str.strip()
    df["MODELO"] = df["MODELO"].astype(str).str.strip()
    df = df[df["PREFIXO"] != ""].drop_duplicates(subset=["PREFIXO"], keep="last")
    df["CLASSE"] = df["GRUPO"].apply(extrair_classe)
    return df[COLUNAS_FINAIS].reset_index(drop=True)


def localizar_arquivo_mais_recente(pasta: str | Path, padrao: str = "CONSOLIDADO FROTA*.xlsx") -> Path:
    pasta = Path(pasta)
    candidatos = sorted(pasta.glob(padrao), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo '{padrao}' encontrado em {pasta}")
    return candidatos[0]
