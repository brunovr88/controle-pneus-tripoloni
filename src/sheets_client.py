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
from gspread.utils import rowcol_to_a1

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
        # gspread as vezes relanca so "PermissionError" sem mensagem, escondendo a causa
        # real (ex.: API nao ativada) em __cause__ -- mostra os dois para nao perder o motivo.
        causa = f" | causa: {e.__cause__}" if e.__cause__ else ""
        st.caption(f"Detalhe técnico: {type(e).__name__}: {e}{causa}")
        st.stop()


@st.cache_data(ttl=120, show_spinner="Carregando dados do Google Sheets...")
def carregar_aba(nome: str) -> pd.DataFrame:
    ws = worksheet(nome)
    # numericise_ignore=["all"]: por padrao o gspread converte qualquer celula
    # que "parece numero" pra int/float na leitura -- MODELO "950" virava int
    # e "FMX" continuava string, misturando tipos na mesma coluna e quebrando
    # sorted() em filtros.py. O app ja faz sua propria conversao numerica onde
    # precisa (QTDE, LATITUDE, LONGITUDE em calculations.py), entao aqui tudo
    # deve vir como texto puro, sem "ajuda" automatica do gspread.
    registros = ws.get_all_records(numericise_ignore=["all"])
    return pd.DataFrame(registros)


def limpar_cache():
    carregar_aba.clear()


def df_para_valores(df: pd.DataFrame) -> list:
    """[cabecalho] + linhas, tudo como string, pronto pra ws.update()/append_rows().

    fillna("") ANTES do astype(str) e obrigatorio: no pandas 3.x (dtype "str"
    por padrao para colunas de texto), astype(str) numa coluna que ja e "str"
    vira no-op e um NaN real sobrevive dentro dela -- isso quebra a
    serializacao JSON do gspread com 'Out of range float values are not JSON
    compliant: nan'. fillna("") elimina o NaN antes disso importar.
    """
    df_limpo = df.fillna("").astype(str)
    return [df_limpo.columns.tolist()] + df_limpo.values.tolist()


def _set_cell(ws, row: int, col: int, valor):
    """Substitui o Worksheet.update_cell() nativo do gspread: aquele metodo
    ignora qualquer value_input_option e SEMPRE manda USER_ENTERED pro Google,
    que reinterpreta o conteudo (ex.: MODELO "950" virava numero em vez de
    texto, misturando tipos na coluna e quebrando sorted() em filtros.py).
    Usar RAW explicito via ws.update() com A1 notation grava exatamente a
    string que mandamos, sem reinterpretacao."""
    ws.update(rowcol_to_a1(row, col), [[str(valor)]], value_input_option="RAW")


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

    ws.update(df_para_valores(df), value_input_option="RAW")
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
        _set_cell(ws, linha_alvo, c_idx, novo_valor)
        _registrar_log(valor_chave, campo, anterior, novo_valor, usuario, agora)

    if "ULT_ATUALIZACAO" in cabecalho:
        _set_cell(ws, linha_alvo, cabecalho.index("ULT_ATUALIZACAO") + 1, agora)
    if "ATUALIZADO_POR" in cabecalho:
        _set_cell(ws, linha_alvo, cabecalho.index("ATUALIZADO_POR") + 1, usuario)

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
        _set_cell(ws, linha_alvo, c_idx, novo_valor)
        _registrar_log(f"{prefixo}/{posicao}", campo, anterior, novo_valor, usuario, agora)

    if "ULT_ATUALIZACAO" in cabecalho:
        _set_cell(ws, linha_alvo, cabecalho.index("ULT_ATUALIZACAO") + 1, agora)
    if "ATUALIZADO_POR" in cabecalho:
        _set_cell(ws, linha_alvo, cabecalho.index("ATUALIZADO_POR") + 1, usuario)

    limpar_cache()
    return True


def _registrar_log(chave: str, campo: str, anterior, novo, usuario: str, timestamp: str):
    ws = worksheet(ABA_LOG)
    ws.append_row([timestamp, usuario, chave, campo, str(anterior), str(novo)])
