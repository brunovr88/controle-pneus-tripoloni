"""Regra "esse tipo de ativo tem pneu?" para prefixos novos vindos do Consolidado Frota.

A decisao mora na aba Classes_Pneu do Google Sheets (CLASSE, MODELO, TEM_PNEU,
EXEMPLO_GRUPO, QTD_ATIVOS, OBSERVACAO) -- nunca e adivinhada silenciosamente em
codigo. MODELO em branco = regra vale para toda a classe; MODELO preenchido =
excecao para aquele modelo especifico dentro da classe (quando o padrao da
classe nao vale para ele). Editavel em pages/6_🔐_Administracao.py.
"""

from __future__ import annotations

import pandas as pd

TEM_PNEU_SIM = "SIM"
TEM_PNEU_NAO = "NAO"
TEM_PNEU_REVISAR = "A_REVISAR"

COLUNAS = ["CLASSE", "MODELO", "TEM_PNEU", "EXEMPLO_GRUPO", "QTD_ATIVOS", "OBSERVACAO"]


def avaliar(df_classes_pneu: pd.DataFrame, classe: str, modelo: str) -> str:
    """Prioridade: (CLASSE, MODELO) exato > (CLASSE, MODELO em branco) > A_REVISAR."""
    if df_classes_pneu is None or df_classes_pneu.empty:
        return TEM_PNEU_REVISAR

    classe_norm = (classe or "").strip().upper()
    modelo_norm = (modelo or "").strip().upper()

    df = df_classes_pneu.copy()
    df["CLASSE"] = df["CLASSE"].astype(str).str.strip().str.upper()
    df["MODELO"] = df["MODELO"].astype(str).str.strip().str.upper()

    especifico = df[(df["CLASSE"] == classe_norm) & (df["MODELO"] == modelo_norm) & (df["MODELO"] != "")]
    if not especifico.empty:
        return str(especifico.iloc[0]["TEM_PNEU"]).strip().upper()

    geral = df[(df["CLASSE"] == classe_norm) & (df["MODELO"] == "")]
    if not geral.empty:
        return str(geral.iloc[0]["TEM_PNEU"]).strip().upper()

    return TEM_PNEU_REVISAR


def avaliar_prefixos_sem_pneu(df_frota: pd.DataFrame, prefixos_alvo: list[str], df_classes_pneu: pd.DataFrame) -> dict:
    """Para cada prefixo de prefixos_alvo (que deve existir em df_frota), decide se
    tem pneu. Usado tanto por scripts/sincronizar_frota.py (prefixos sem nenhuma
    linha em Pneus, novos ou pendentes de antes) quanto pelo botao "aplicar
    classes revisadas" da tela de Administracao (mesma decisao, sob demanda,
    depois que o time de frota confirma uma classe que estava em A_REVISAR).
    """
    com_pneu, sem_pneu, pendentes = [], [], []
    classes_novas_pendentes: dict[str, str] = {}

    frota_idx = df_frota.drop_duplicates(subset=["PREFIXO"]).set_index("PREFIXO")
    for prefixo in prefixos_alvo:
        if prefixo not in frota_idx.index:
            continue
        linha = frota_idx.loc[prefixo]
        decisao = avaliar(df_classes_pneu, linha["CLASSE"], linha["MODELO"])
        if decisao == TEM_PNEU_SIM:
            com_pneu.append(prefixo)
        elif decisao == TEM_PNEU_NAO:
            sem_pneu.append(prefixo)
        else:
            pendentes.append(prefixo)
            classes_novas_pendentes.setdefault(linha["CLASSE"], linha["GRUPO"])

    return {
        "com_pneu": com_pneu,
        "sem_pneu": sem_pneu,
        "pendentes": pendentes,
        "classes_novas_pendentes": classes_novas_pendentes,
    }


def seed_inicial(df_frota: pd.DataFrame, df_pneus: pd.DataFrame) -> pd.DataFrame:
    """Ponto de partida data-driven para a carga inicial: classe com evidencia real
    de pneu cadastrado (QTDE > 0 em algum prefixo dessa classe) vira SIM; o resto
    fica A_REVISAR para o time de frota confirmar uma vez na tela de Administracao.

    Nunca marca NAO sozinho -- ausencia de pneu cadastrado pode ser so falta de
    cadastro (o problema que esse app existe para corrigir), nao ausencia real
    de pneu no equipamento.
    """
    pneus_validos = df_pneus[pd.to_numeric(df_pneus["QTDE"], errors="coerce").fillna(0) > 0]
    prefixos_com_pneu = set(pneus_validos["PREFIXO"])

    linhas = []
    for classe, grupo in df_frota.groupby("CLASSE"):
        prefixos_classe = set(grupo["PREFIXO"])
        tem_evidencia = bool(prefixos_classe & prefixos_com_pneu)
        linhas.append(
            {
                "CLASSE": classe,
                "MODELO": "",
                "TEM_PNEU": TEM_PNEU_SIM if tem_evidencia else TEM_PNEU_REVISAR,
                "EXEMPLO_GRUPO": grupo["GRUPO"].iloc[0],
                "QTD_ATIVOS": len(prefixos_classe),
                "OBSERVACAO": "",
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS).sort_values(["TEM_PNEU", "CLASSE"]).reset_index(drop=True)
