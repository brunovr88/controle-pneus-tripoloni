"""Sincroniza um novo "Consolidado Frota" com o Google Sheets.

O nome do arquivo pode mudar a cada exportacao (ex.: "CONSOLIDADO FROTA
16.09.2026.xlsx" numa exportacao, "CONSOLIDADO FROTA 23.09.2026.xlsx" na
proxima) -- a estrutura de colunas e que precisa se manter (ver
src/frota_parser.py). Este script:

  1. Atualiza OBRA_LOCAL e demais dados cadastrais de prefixos ja existentes
     (a localizacao "vem" deste arquivo a cada sincronizacao).
  2. Para prefixos novos, avalia MODELO + CLASSE OPERACIONAL contra a aba
     Classes_Pneu para decidir se o ativo entra no banco de pneus:
       - classe/modelo ja confirmados como "possui pneu" -> cria 3 linhas
         vazias em Pneus (Dianteiro/Traseiro/Step) prontas pra obra preencher
         no app;
       - confirmados como "nao possui pneu" (ex.: usina fixa, gerador) -> so
         entra na Frota, nao cria linhas em Pneus;
       - classe nunca vista antes -> NAO cria linhas em Pneus ainda, fica
         pendente em Classes_Pneu ("A_REVISAR") ate alguem confirmar na tela
         de Administracao do app.
  3. Nunca apaga historico de pneus. Prefixos que sumiram do arquivo novo sao
     so listados no relatorio final (equipamento baixado/vendido?) para
     revisao manual -- a decisao de remover fica com uma pessoa, nao com o script.

Uso:
    python scripts/sincronizar_frota.py --credentials service_account.json --spreadsheet-id ID
    python scripts/sincronizar_frota.py --arquivo "CONSOLIDADO FROTA 23.09.2026.xlsx" \
        --credentials service_account.json --spreadsheet-id ID

Sem --arquivo, usa o mais recente que bater com "CONSOLIDADO FROTA*.xlsx" na
pasta do projeto. Use --dry-run para só ver o plano, sem gravar nada.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.classes_pneu import COLUNAS as COLUNAS_CLASSES_PNEU  # noqa: E402
from src.classes_pneu import TEM_PNEU_REVISAR, avaliar_prefixos_sem_pneu  # noqa: E402
from src.frota_parser import ler_frota_bruta, localizar_arquivo_mais_recente  # noqa: E402
from src.sheets_client import ABA_CLASSES_PNEU, ABA_FROTA, ABA_PNEUS  # noqa: E402

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

POSICOES_PADRAO = ["DIANTEIRO", "TRASEIRO", "STEP"]


def calcular_plano(
    df_novo: pd.DataFrame, df_atual: pd.DataFrame, df_classes_pneu: pd.DataFrame, df_pneus_atual: pd.DataFrame
) -> dict:
    """Logica pura (sem gspread) -- testavel com dataframes na mao, sem precisar de credenciais.

    A decisao "criar linhas vazias em Pneus" e reavaliada para TODO prefixo sem
    nenhuma linha em Pneus ainda (nao so os prefixos novos desta rodada). Isso
    e necessario porque um prefixo pode ter ficado pendente numa sincronizacao
    anterior (classe ainda nao revisada) -- sem essa reavaliacao, depois que a
    classe fosse confirmada ele nunca mais seria pego, porque deixa de aparecer
    como "novo" assim que entra na Frota.
    """
    prefixos_novo = set(df_novo["PREFIXO"])
    prefixos_atual = set(df_atual["PREFIXO"]) if not df_atual.empty else set()

    novos = sorted(prefixos_novo - prefixos_atual)
    saidas = sorted(prefixos_atual - prefixos_novo)

    status_atual = {}
    if not df_atual.empty and "STATUS_CADASTRO" in df_atual.columns:
        status_atual = df_atual.set_index("PREFIXO")["STATUS_CADASTRO"].to_dict()

    df_frota_final = df_novo.copy()
    df_frota_final["STATUS_CADASTRO"] = df_frota_final["PREFIXO"].map(status_atual).fillna("NAO IDENTIFICADO")

    prefixos_com_pneu_no_banco = set(df_pneus_atual["PREFIXO"]) if not df_pneus_atual.empty else set()
    sem_registro_pneu = sorted(prefixos_novo - prefixos_com_pneu_no_banco)

    avaliacao = avaliar_prefixos_sem_pneu(df_frota_final, sem_registro_pneu, df_classes_pneu)

    return {
        "df_frota_final": df_frota_final,
        "novos": novos,
        "saidas": saidas,
        "prefixos_com_pneu": avaliacao["com_pneu"],
        "prefixos_sem_pneu": avaliacao["sem_pneu"],
        "prefixos_pendentes": avaliacao["pendentes"],
        "classes_novas_pendentes": avaliacao["classes_novas_pendentes"],
    }


def montar_linhas_pneu_vazias(prefixos: list[str]) -> pd.DataFrame:
    linhas = [
        {
            "PREFIXO": p,
            "POSICAO": pos,
            "MEDIDA": "",
            "QTDE": 0,
            "ULT_ATUALIZACAO": "",
            "ATUALIZADO_POR": "sincronizacao_frota",
        }
        for p in prefixos
        for pos in POSICOES_PADRAO
    ]
    return pd.DataFrame(linhas)


def imprimir_relatorio(plano: dict):
    print(f"\n{len(plano['novos'])} prefixos novos encontrados no arquivo")
    print(
        f"\n{len(plano['prefixos_com_pneu']) + len(plano['prefixos_sem_pneu']) + len(plano['prefixos_pendentes'])} "
        "prefixos sem nenhuma linha em Pneus ainda (novos desta rodada + pendentes de rodadas anteriores):"
    )
    print(f"  -> {len(plano['prefixos_com_pneu'])} com pneu (classe/modelo já confirmados) — ganham linhas vazias em Pneus")
    print(f"  -> {len(plano['prefixos_sem_pneu'])} sem pneu (classe/modelo confirmados como 'NAO') — só entram na Frota")
    print(f"  -> {len(plano['prefixos_pendentes'])} pendentes de revisão de classe — NÃO entram em Pneus ainda")

    if plano["classes_novas_pendentes"]:
        print("\n  Classes novas para revisar na tela de Administração:")
        for classe, exemplo in plano["classes_novas_pendentes"].items():
            print(f"    - {classe}  (ex.: {exemplo})")

    if plano["saidas"]:
        print(f"\n{len(plano['saidas'])} prefixos que estavam na Frota e NÃO aparecem mais no arquivo novo:")
        for p in plano["saidas"][:20]:
            print(f"    - {p}")
        if len(plano["saidas"]) > 20:
            print(f"    ... e mais {len(plano['saidas']) - 20}")
        print("  (nada foi apagado — pode ser baixa/venda do equipamento; revise manualmente se preciso)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arquivo", help="Caminho do novo Consolidado Frota (default: mais recente na pasta do projeto)")
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Só mostra o plano, não grava nada no Sheets")
    args = parser.parse_args()

    arquivo = Path(args.arquivo) if args.arquivo else localizar_arquivo_mais_recente(BASE_DIR)
    if not arquivo.exists():
        print(f"ERRO: arquivo não encontrado: {arquivo}", file=sys.stderr)
        sys.exit(1)

    print(f"Lendo {arquivo.name} ...")
    df_novo = ler_frota_bruta(arquivo)

    creds = Credentials.from_service_account_file(args.credentials, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(args.spreadsheet_id)

    df_atual = pd.DataFrame(sh.worksheet(ABA_FROTA).get_all_records())
    df_pneus_atual = pd.DataFrame(sh.worksheet(ABA_PNEUS).get_all_records())
    try:
        df_classes_pneu = pd.DataFrame(sh.worksheet(ABA_CLASSES_PNEU).get_all_records())
    except gspread.WorksheetNotFound:
        df_classes_pneu = pd.DataFrame(columns=COLUNAS_CLASSES_PNEU)

    plano = calcular_plano(df_novo, df_atual, df_classes_pneu, df_pneus_atual)
    imprimir_relatorio(plano)

    if args.dry_run:
        print("\n--dry-run: nada foi gravado no Google Sheets.")
        return

    ws_frota = sh.worksheet(ABA_FROTA)
    ws_frota.clear()
    valores = [plano["df_frota_final"].columns.tolist()] + plano["df_frota_final"].astype(str).values.tolist()
    ws_frota.update(valores, value_input_option="USER_ENTERED")
    print(f"\n[ok] Frota atualizada: {len(plano['df_frota_final'])} ativos")

    if plano["prefixos_com_pneu"]:
        df_pneus_novos = montar_linhas_pneu_vazias(plano["prefixos_com_pneu"])
        ws_pneus = sh.worksheet(ABA_PNEUS)
        ws_pneus.append_rows(df_pneus_novos.astype(str).values.tolist(), value_input_option="USER_ENTERED")
        print(f"[ok] Pneus: {len(df_pneus_novos)} linhas novas criadas ({len(plano['prefixos_com_pneu'])} ativos)")

    if plano["classes_novas_pendentes"]:
        try:
            ws_classes = sh.worksheet(ABA_CLASSES_PNEU)
        except gspread.WorksheetNotFound:
            ws_classes = sh.add_worksheet(title=ABA_CLASSES_PNEU, rows=200, cols=len(COLUNAS_CLASSES_PNEU) + 2)
            ws_classes.update([COLUNAS_CLASSES_PNEU], value_input_option="USER_ENTERED")
        novas_linhas = [
            [classe, "", TEM_PNEU_REVISAR, exemplo, "", ""] for classe, exemplo in plano["classes_novas_pendentes"].items()
        ]
        ws_classes.append_rows(novas_linhas, value_input_option="USER_ENTERED")
        print(f"[ok] {ABA_CLASSES_PNEU}: {len(novas_linhas)} classes novas marcadas 'A_REVISAR'")
        print("     Confirme SIM/NAO na tela de Administração e rode a sincronização de novo (os pendentes serão reavaliados).")

    print("\nSincronização concluída.")


if __name__ == "__main__":
    main()
