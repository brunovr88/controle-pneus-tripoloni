"""Camada de acesso ao Google Sheets (banco de dados oficial do app).

Abas esperadas na planilha (ver scripts/migrar_para_sheets.py para a carga inicial):
  - Pneus       : fato, 1 linha por PREFIXO + POSICAO
  - Frota       : dimensao equipamento, 1 linha por PREFIXO
  - Local       : dimensao obra, 1 linha por OBRA_LOCAL
  - Usuarios    : login (usuario, hash bcrypt, perfil, obra vinculada)
  - LogAlteracoes: trilha de auditoria das edicoes feitas no app
"""

from __future__ import annotations

import datetime as dt

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

ABA_PNEUS = "Pneus"
ABA_FROTA = "Frota"
ABA_LOCAL = "Local"
ABA_USUARIOS = "Usuarios"
ABA_LOG = "LogAlteracoes"
ABA_CLASSES_PNEU = "Classes_Pneu"


@st.cache_resource(show_spinner=False)
def _client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _spreadsheet():
    return _client().open_by_key(st.secrets["sheets"]["spreadsheet_id"])


def worksheet(nome: str):
    """Ponto unico por onde toda leitura/escrita passa -- por isso e aqui que
    falhas de conexao (secrets ausentes/errados, planilha nao compartilhada,
    rede fora) sao convertidas numa mensagem amigavel em vez de um traceback
    Python cru na tela do usuario final. gspread.exceptions.WorksheetNotFound
    e propagada sem alteracao: varias telas do app dependem de captura-la
    especificamente para saber que uma aba so ainda nao existe (nao e uma
    falha de conexao)."""
    try:
        return _spreadsheet().worksheet(nome)
    except gspread.exceptions.WorksheetNotFound:
        raise
    except Exception as e:
        st.error(
            "Não foi possível conectar ao banco de dados (Google Sheets). Verifique se as "
            "credenciais estão configuradas em `.streamlit/secrets.toml` (local) ou em "
            "*App settings → Secrets* (Streamlit Community Cloud), e se a planilha foi "
            "compartilhada com o e-mail da Service Account como Editor."
        )
        st.caption(f"Detalhe técnico: {type(e).__name__}: {e}")
        st.stop()


@st.cache_data(ttl=120, show_spinner="Carregando dados do Google Sheets...")
def carregar_aba(nome: str) -> pd.DataFrame:
    ws = worksheet(nome)
    registros = ws.get_all_records()
    return pd.DataFrame(registros)


def limpar_cache():
    carregar_aba.clear()


def substituir_aba(nome: str, df: pd.DataFrame):
    """Apaga o conteudo da aba e regrava do zero a partir de df (cria a aba se
    nao existir). Usado pela tela de Configuracao Inicial no app -- equivalente
    ao escrever_aba() do script de linha de comando, so que reaproveitando a
    conexao ja cacheada via st.secrets em vez de credenciais passadas por CLI.
    """
    sh = _spreadsheet()
    try:
        ws = sh.worksheet(nome)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nome, rows=max(len(df) + 10, 100), cols=max(len(df.columns) + 2, 10))

    valores = [df.columns.tolist()] + df.astype(str).values.tolist()
    ws.update(valores, value_input_option="USER_ENTERED")
    limpar_cache()


def atualizar_linha_por_chave(
    aba: str, coluna_chave: str, valor_chave: str, valores: dict, usuario: str
) -> bool:
    """Atualiza a primeira linha cuja coluna_chave == valor_chave.

    Usado para edicoes vindas do diagrama do equipamento (troca de medida,
    correcao de cadastro). Grava tambem uma linha de auditoria.
    """
    ws = worksheet(aba)
    cabecalho = ws.row_values(1)
    if coluna_chave not in cabecalho:
        raise ValueError(f"Coluna chave '{coluna_chave}' nao existe em '{aba}'")

    col_idx = cabecalho.index(coluna_chave) + 1
    coluna_valores = ws.col_values(col_idx)

    linha_alvo = None
    for i, v in enumerate(coluna_valores[1:], start=2):
        if v == valor_chave:
            linha_alvo = i
            break
    if linha_alvo is None:
        return False

    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for campo, novo_valor in valores.items():
        if campo not in cabecalho:
            continue
        c_idx = cabecalho.index(campo) + 1
        anterior = ws.cell(linha_alvo, c_idx).value
        if str(anterior) == str(novo_valor):
            continue
        ws.update_cell(linha_alvo, c_idx, novo_valor)
        _registrar_log(valor_chave, campo, anterior, novo_valor, usuario, agora)

    if "ULT_ATUALIZACAO" in cabecalho:
        ws.update_cell(linha_alvo, cabecalho.index("ULT_ATUALIZACAO") + 1, agora)
    if "ATUALIZADO_POR" in cabecalho:
        ws.update_cell(linha_alvo, cabecalho.index("ATUALIZADO_POR") + 1, usuario)

    limpar_cache()
    return True


def atualizar_linha_pneu(prefixo: str, posicao: str, valores: dict, usuario: str) -> bool:
    """Igual a atualizar_linha_por_chave, mas a chave e composta (PREFIXO+POSICAO).

    Se o ativo nunca teve linha para essa posicao (ex.: STEP vazio na carga inicial),
    cria a linha em vez de falhar -- isso permite cadastrar uma posicao pela primeira vez.
    """
    ws = worksheet(ABA_PNEUS)
    cabecalho = ws.row_values(1)
    idx_prefixo = cabecalho.index("PREFIXO")
    idx_posicao = cabecalho.index("POSICAO")
    linhas = ws.get_all_values()[1:]

    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    linha_alvo = None
    for i, row in enumerate(linhas, start=2):
        if row[idx_prefixo] == prefixo and row[idx_posicao] == posicao:
            linha_alvo = i
            break

    if linha_alvo is None:
        nova_linha = [""] * len(cabecalho)
        nova_linha[idx_prefixo] = prefixo
        nova_linha[idx_posicao] = posicao
        for campo, novo_valor in valores.items():
            if campo in cabecalho:
                nova_linha[cabecalho.index(campo)] = str(novo_valor)
        if "ULT_ATUALIZACAO" in cabecalho:
            nova_linha[cabecalho.index("ULT_ATUALIZACAO")] = agora
        if "ATUALIZADO_POR" in cabecalho:
            nova_linha[cabecalho.index("ATUALIZADO_POR")] = usuario
        ws.append_row(nova_linha)
        _registrar_log(f"{prefixo}/{posicao}", "LINHA_CRIADA", "", str(valores), usuario, agora)
        limpar_cache()
        return True
    for campo, novo_valor in valores.items():
        if campo not in cabecalho:
            continue
        c_idx = cabecalho.index(campo) + 1
        anterior = ws.cell(linha_alvo, c_idx).value
        if str(anterior) == str(novo_valor):
            continue
        ws.update_cell(linha_alvo, c_idx, novo_valor)
        _registrar_log(f"{prefixo}/{posicao}", campo, anterior, novo_valor, usuario, agora)

    if "ULT_ATUALIZACAO" in cabecalho:
        ws.update_cell(linha_alvo, cabecalho.index("ULT_ATUALIZACAO") + 1, agora)
    if "ATUALIZADO_POR" in cabecalho:
        ws.update_cell(linha_alvo, cabecalho.index("ATUALIZADO_POR") + 1, usuario)

    limpar_cache()
    return True


def _registrar_log(chave: str, campo: str, anterior, novo, usuario: str, timestamp: str):
    ws = worksheet(ABA_LOG)
    ws.append_row([timestamp, usuario, chave, campo, str(anterior), str(novo)])
