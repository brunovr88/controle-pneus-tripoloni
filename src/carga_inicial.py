"""Processamento das 3 planilhas de carga inicial (Pneus, Frota, Local).

Logica compartilhada entre scripts/migrar_para_sheets.py (rodado por linha de
comando, le arquivos do disco) e pages/0_⚙️_Configuracao_Inicial.py (rodado no
navegador, le arquivos enviados por upload) -- os dois usam exatamente as
mesmas funcoes, so muda de onde o arquivo vem (Path ou UploadedFile do
Streamlit; pandas.read_excel aceita os dois do mesmo jeito).
"""

from __future__ import annotations

import unicodedata

import pandas as pd

from src.frota_parser import ler_frota_bruta

POSICOES = [
    ("DIANTEIRO", "MP DIANTEIRO", "QTDE DIANTEIRO"),
    ("TRASEIRO", "MP TRASEIRO", "QTDE TRASEIRO"),
    ("STEP", "MP STEP", "QTDE STEP"),
]


def processar_pneus(arquivo) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Um unico read do arquivo de pneus, reaproveitado para 2 coisas:
    (1) a aba Pneus em formato longo, (2) o STATUS_CADASTRO por prefixo, que
    processar_frota() precisa para popular a dimensao Frota."""
    df = pd.read_excel(arquivo, sheet_name="CONSOLIDADO", header=2)
    df.columns = [str(c).strip() for c in df.columns]

    linhas = []
    for _, row in df.iterrows():
        prefixo = row.get("PREFIXO")
        if pd.isna(prefixo) or not str(prefixo).strip():
            continue
        for posicao, col_medida, col_qtde in POSICOES:
            qtde = row.get(col_qtde)
            medida = row.get(col_medida)
            if pd.isna(qtde) and pd.isna(medida):
                continue
            linhas.append(
                {
                    "PREFIXO": str(prefixo).strip(),
                    "POSICAO": posicao,
                    "MEDIDA": "" if pd.isna(medida) else str(medida).strip(),
                    "QTDE": 0 if pd.isna(qtde) else int(qtde),
                    "ULT_ATUALIZACAO": "",
                    "ATUALIZADO_POR": "carga_inicial",
                }
            )
    df_pneus_longo = pd.DataFrame(linhas)

    status_por_prefixo = (
        df[["PREFIXO", "STATUS"]]
        .dropna(subset=["PREFIXO"])
        .assign(PREFIXO=lambda d: d["PREFIXO"].astype(str).str.strip())
        .drop_duplicates(subset=["PREFIXO"])
    )
    return df_pneus_longo, status_por_prefixo


def _normalizar_status(valor) -> str:
    """A planilha origem mistura 'NAO IDENTIFICADO' e 'NÃO IDENTIFICADO' (com
    acento) como se fossem 2 status diferentes -- aqui os dois caem no mesmo
    valor canonico."""
    if not isinstance(valor, str) or not valor.strip():
        return "NAO IDENTIFICADO"
    sem_acento = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
    sem_acento = sem_acento.strip().upper()
    return "IDENTIFICADO" if sem_acento == "IDENTIFICADO" else "NAO IDENTIFICADO"


def processar_frota(arquivo_frota, status_por_prefixo: pd.DataFrame) -> pd.DataFrame:
    df_frota = ler_frota_bruta(arquivo_frota)
    df_frota = df_frota.merge(status_por_prefixo, on="PREFIXO", how="left")
    df_frota = df_frota.rename(columns={"STATUS": "STATUS_CADASTRO"})
    df_frota["STATUS_CADASTRO"] = df_frota["STATUS_CADASTRO"].apply(_normalizar_status)
    return df_frota


def processar_local(arquivo) -> pd.DataFrame:
    df = pd.read_excel(arquivo, sheet_name="LOCALIDADE", header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={"OBRA-LOCAL": "OBRA_LOCAL"})
    return df
