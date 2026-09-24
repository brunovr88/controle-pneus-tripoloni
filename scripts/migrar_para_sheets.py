"""Migracao ÚNICA: le as 3 planilhas locais, limpa/normaliza e grava no Google Sheets.

Pre-requisitos (fazer uma vez, fora deste script):
  1. Criar um projeto no Google Cloud, ativar "Google Sheets API" e "Google Drive API".
  2. Criar uma Service Account e baixar a chave JSON.
  3. Criar uma planilha Google Sheets vazia e compartilhar com o e-mail da service
     account (campo "client_email" do JSON) como Editor.
  4. Copiar o ID da planilha (trecho da URL entre /d/ e /edit).

Uso:
    python scripts/migrar_para_sheets.py \
        --credentials "caminho/para/service_account.json" \
        --spreadsheet-id "ID_DA_PLANILHA" \
        --admin-user admin --admin-password "TrocarDepois123" --admin-nome "Administrador"

Alternativa sem terminal: depois de configurar as credenciais em
.streamlit/secrets.toml, a mesma carga pode ser feita direto pelo navegador na
tela "Configuração Inicial" do app (pages/0_⚙️_Configuracao_Inicial.py), fazendo
upload das 3 planilhas em vez de rodar este script.

Reexecutar este script SUBSTITUI o conteudo das abas Pneus/Frota/Local/Classes_Pneu
(a aba Usuarios so e recriada se ainda nao existir, para nao apagar logins ja
cadastrados). Depois da carga inicial, use scripts/sincronizar_frota.py para
atualizar localizacao e incorporar prefixos novos sem repetir esta migracao.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bcrypt
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.carga_inicial import processar_frota, processar_local, processar_pneus  # noqa: E402
from src.classes_pneu import seed_inicial  # noqa: E402
import src.medidas_padrao as medidas_padrao  # noqa: E402
from src.sheets_client import (  # noqa: E402
    ABA_CLASSES_PNEU,
    ABA_ESTOQUE_FISICO,
    ABA_FROTA,
    ABA_LOCAL,
    ABA_LOG,
    ABA_MEDIDAS_PADRAO,
    ABA_PARAMETROS,
    ABA_PNEUS,
    ABA_USUARIOS,
    df_para_valores,
)

ARQ_PNEUS = BASE_DIR / "CONSOLIDADO_PNEUS_POR_ATIVO_vrs2.xlsx"
ARQ_FROTA = BASE_DIR / "CONSOLIDADO FROTA 16.09.2026.xlsx"
ARQ_LOCAL = BASE_DIR / "LOCAL.xlsx"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def escrever_aba(sh: gspread.Spreadsheet, nome: str, df: pd.DataFrame):
    try:
        ws = sh.worksheet(nome)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nome, rows=max(len(df) + 10, 100), cols=max(len(df.columns) + 2, 10))

    ws.update(df_para_valores(df), value_input_option="RAW")
    print(f"  [ok] {nome}: {len(df)} linhas gravadas")


def garantir_aba_usuarios(sh: gspread.Spreadsheet, admin_user: str, admin_password: str, admin_nome: str):
    try:
        sh.worksheet(ABA_USUARIOS)
        print("  [skip] Usuarios ja existe -- login nao foi tocado")
        return
    except gspread.WorksheetNotFound:
        pass

    senha_hash = bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    df_usuarios = pd.DataFrame(
        [
            {
                "USUARIO": admin_user,
                "SENHA_HASH": senha_hash,
                "NOME": admin_nome,
                "PERFIL": "ADMIN",
                "OBRA_VINCULADA": "",
                "ATIVO": "TRUE",
            }
        ]
    )
    escrever_aba(sh, ABA_USUARIOS, df_usuarios)
    print(f"  [ok] usuario admin '{admin_user}' criado -- troque a senha apos o primeiro login")


def garantir_aba_log(sh: gspread.Spreadsheet):
    try:
        sh.worksheet(ABA_LOG)
        return
    except gspread.WorksheetNotFound:
        pass
    df_log = pd.DataFrame(columns=["TIMESTAMP", "USUARIO", "CHAVE", "CAMPO", "VALOR_ANTERIOR", "VALOR_NOVO"])
    escrever_aba(sh, ABA_LOG, df_log)


def garantir_aba_estoque_fisico(sh: gspread.Spreadsheet):
    try:
        sh.worksheet(ABA_ESTOQUE_FISICO)
        return
    except gspread.WorksheetNotFound:
        pass
    df_estoque = pd.DataFrame(columns=["OBRA_LOCAL", "MEDIDA", "QTDE_ESTOQUE", "ULT_ATUALIZACAO", "ATUALIZADO_POR"])
    escrever_aba(sh, ABA_ESTOQUE_FISICO, df_estoque)


def garantir_aba_parametros(sh: gspread.Spreadsheet):
    try:
        sh.worksheet(ABA_PARAMETROS)
        return
    except gspread.WorksheetNotFound:
        pass
    df_parametros = pd.DataFrame([{"PCT_SOLICITADO": 10, "PCT_MINIMO": 20}])
    escrever_aba(sh, ABA_PARAMETROS, df_parametros)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--credentials", required=True, help="Caminho do JSON da service account")
    parser.add_argument("--spreadsheet-id", required=True, help="ID da planilha Google Sheets de destino")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-password", default="TrocarDepois123")
    parser.add_argument("--admin-nome", default="Administrador")
    args = parser.parse_args()

    for arq in (ARQ_PNEUS, ARQ_FROTA, ARQ_LOCAL):
        if not arq.exists():
            print(f"ERRO: arquivo nao encontrado: {arq}", file=sys.stderr)
            sys.exit(1)

    creds = Credentials.from_service_account_file(args.credentials, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(args.spreadsheet_id)

    print("Lendo planilhas locais...")
    df_pneus, status_por_prefixo = processar_pneus(ARQ_PNEUS)
    df_frota = processar_frota(ARQ_FROTA, status_por_prefixo)
    df_local = processar_local(ARQ_LOCAL)
    df_classes_pneu = seed_inicial(df_frota, df_pneus)
    df_medidas_padrao = medidas_padrao.seed_inicial(df_pneus)

    print(f"Gravando no Google Sheets '{sh.title}'...")
    escrever_aba(sh, ABA_PNEUS, df_pneus)
    escrever_aba(sh, ABA_FROTA, df_frota)
    escrever_aba(sh, ABA_LOCAL, df_local)
    escrever_aba(sh, ABA_CLASSES_PNEU, df_classes_pneu)
    escrever_aba(sh, ABA_MEDIDAS_PADRAO, df_medidas_padrao)
    garantir_aba_usuarios(sh, args.admin_user, args.admin_password, args.admin_nome)
    garantir_aba_log(sh)
    garantir_aba_estoque_fisico(sh)
    garantir_aba_parametros(sh)

    pendentes = (df_classes_pneu["TEM_PNEU"] == "A_REVISAR").sum()
    print(f"\n{pendentes} classes operacionais ficaram como 'A_REVISAR' em {ABA_CLASSES_PNEU}")
    print("Confirme SIM/NAO para elas na tela de Administração do app antes da próxima sincronização.")

    print("\nMigracao concluida.")
    print(f"Planilha: https://docs.google.com/spreadsheets/d/{args.spreadsheet_id}")


if __name__ == "__main__":
    main()
