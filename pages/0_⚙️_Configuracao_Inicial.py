"""Configuração inicial pelo navegador -- alternativa a rodar
scripts/migrar_para_sheets.py no terminal. Sobe as 3 planilhas por upload e
grava tudo no Google Sheets.

Pré-requisito que continua fora do app (isso não dá pra automatizar de dentro
do Streamlit): a Service Account do Google Cloud já criada e suas credenciais
já coladas em .streamlit/secrets.toml (local) ou em App settings -> Secrets
(Streamlit Community Cloud). Sem isso o app não tem como falar com o Google
Sheets -- veja o passo a passo no topo de scripts/migrar_para_sheets.py.
"""

import bcrypt
import gspread
import pandas as pd
import streamlit as st

from src.auth import exigir_login, is_admin, logout, usuario_logado
from src.carga_inicial import processar_frota, processar_local, processar_pneus
from src.classes_pneu import seed_inicial
from src.sheets_client import (
    ABA_CLASSES_PNEU,
    ABA_FROTA,
    ABA_LOCAL,
    ABA_LOG,
    ABA_PNEUS,
    ABA_USUARIOS,
    carregar_aba,
    limpar_cache,
    substituir_aba,
    worksheet,
)
from src.theme import CUSTOM_CSS

st.set_page_config(page_title="Configuração Inicial — Tripoloni", page_icon="⚙️", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.title("Configuração inicial do sistema")


def _conexao_ok() -> bool:
    try:
        st.secrets["gcp_service_account"]
        st.secrets["sheets"]["spreadsheet_id"]
        return True
    except Exception:
        return False


if not _conexao_ok():
    st.error(
        "As credenciais do Google Sheets ainda não estão configuradas. Isso precisa ser feito uma "
        "única vez fora do app (não dá pra automatizar isso daqui de dentro):\n\n"
        "1. Crie um projeto no Google Cloud e uma Service Account (Sheets API + Drive API ativadas).\n"
        "2. Baixe a chave JSON da Service Account.\n"
        "3. Crie uma planilha Google Sheets vazia e compartilhe com o e-mail da Service Account como Editor.\n"
        "4. Copie o conteúdo do JSON + o ID da planilha para `.streamlit/secrets.toml` "
        "(veja `.streamlit/secrets.toml.example`) ou, em produção, em *App settings → Secrets* no "
        "Streamlit Community Cloud.\n\nDepois disso, volte nesta tela — o resto é só upload."
    )
    st.stop()

try:
    df_usuarios = carregar_aba(ABA_USUARIOS)
    sistema_ja_configurado = not df_usuarios.empty
except gspread.exceptions.WorksheetNotFound:
    sistema_ja_configurado = False
except Exception as e:
    st.error(f"Não consegui conectar ao Google Sheets configurado nos secrets: {e}")
    st.stop()


def _formulario_upload(exige_admin_novo: bool):
    st.subheader("1. Planilhas de origem")
    st.caption(
        "Mesma estrutura de sempre: aba 'CONSOLIDADO' no arquivo de pneus, "
        "cabeçalho simples no Consolidado Frota, aba 'LOCALIDADE' no arquivo de locais."
    )
    arq_pneus = st.file_uploader("CONSOLIDADO_PNEUS_POR_ATIVO (.xlsx)", type=["xlsx"], key="up_pneus")
    arq_frota = st.file_uploader("CONSOLIDADO FROTA (.xlsx)", type=["xlsx"], key="up_frota")
    arq_local = st.file_uploader("LOCAL (.xlsx)", type=["xlsx"], key="up_local")

    admin_user = admin_senha = admin_nome = None
    if exige_admin_novo:
        st.subheader("2. Usuário administrador")
        c1, c2 = st.columns(2)
        admin_user = c1.text_input("Login do administrador", value="admin")
        admin_nome = c2.text_input("Nome completo", value="Administrador")
        admin_senha = st.text_input("Senha provisória", type="password")

    return arq_pneus, arq_frota, arq_local, admin_user, admin_senha, admin_nome


def _rodar_carga(arq_pneus, arq_frota, arq_local, criar_admin: dict | None):
    with st.spinner("Lendo planilhas e gravando no Google Sheets..."):
        df_pneus, status_por_prefixo = processar_pneus(arq_pneus)
        df_frota = processar_frota(arq_frota, status_por_prefixo)
        df_local = processar_local(arq_local)
        df_classes_pneu = seed_inicial(df_frota, df_pneus)

        substituir_aba(ABA_PNEUS, df_pneus)
        substituir_aba(ABA_FROTA, df_frota)
        substituir_aba(ABA_LOCAL, df_local)
        substituir_aba(ABA_CLASSES_PNEU, df_classes_pneu)

        try:
            worksheet(ABA_LOG)
        except gspread.exceptions.WorksheetNotFound:
            substituir_aba(
                ABA_LOG, pd.DataFrame(columns=["TIMESTAMP", "USUARIO", "CHAVE", "CAMPO", "VALOR_ANTERIOR", "VALOR_NOVO"])
            )

        novo_usuario = None
        if criar_admin:
            senha_hash = bcrypt.hashpw(criar_admin["senha"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            df_admin = pd.DataFrame(
                [
                    {
                        "USUARIO": criar_admin["login"],
                        "SENHA_HASH": senha_hash,
                        "NOME": criar_admin["nome"],
                        "PERFIL": "ADMIN",
                        "OBRA_VINCULADA": "",
                        "ATIVO": "TRUE",
                    }
                ]
            )
            substituir_aba(ABA_USUARIOS, df_admin)
            novo_usuario = {
                "USUARIO": criar_admin["login"],
                "NOME": criar_admin["nome"],
                "PERFIL": "ADMIN",
                "OBRA_VINCULADA": "",
            }

    pendentes = int((df_classes_pneu["TEM_PNEU"] == "A_REVISAR").sum())
    st.success(
        f"Pronto: {len(df_pneus)} linhas de pneus, {len(df_frota)} ativos, {len(df_local)} obras gravados. "
        f"{pendentes} classe(s) operacional(is) ficaram pendentes de revisão em Administração."
    )
    return novo_usuario


if not sistema_ja_configurado:
    codigo_esperado = st.secrets.get("setup", {}).get("codigo", "")
    if not codigo_esperado:
        st.warning(
            "Nenhum código de configuração definido em `[setup] codigo` nos secrets — qualquer pessoa "
            "com este link pode concluir a configuração inicial agora. Defina um código nos secrets e "
            "reinicie o app antes de compartilhar a URL publicamente."
        )

    st.info(
        "Nenhum usuário cadastrado ainda — esta é a primeira configuração do sistema. "
        "Preencha os campos abaixo; ao final você já entra logado como administrador."
    )

    codigo_digitado = ""
    if codigo_esperado:
        codigo_digitado = st.text_input("Código de configuração (definido nos secrets)", type="password")

    arq_pneus, arq_frota, arq_local, admin_user, admin_senha, admin_nome = _formulario_upload(exige_admin_novo=True)

    if st.button("Configurar sistema", type="primary"):
        if codigo_esperado and codigo_digitado != codigo_esperado:
            st.error("Código de configuração incorreto.")
        elif not (arq_pneus and arq_frota and arq_local):
            st.error("Envie as 3 planilhas antes de continuar.")
        elif not admin_user or not admin_senha:
            st.error("Informe login e senha do administrador.")
        else:
            novo_usuario = _rodar_carga(
                arq_pneus, arq_frota, arq_local, {"login": admin_user.strip(), "senha": admin_senha, "nome": admin_nome.strip()}
            )
            st.session_state["usuario_autenticado"] = novo_usuario
            st.switch_page("app.py")

else:
    exigir_login()
    user = usuario_logado()
    with st.sidebar:
        try:
            st.image("LOGO-HORIZONTAL-BRANCA.png", use_container_width=True)
        except Exception:
            st.markdown("### TRIPOLONI")
        st.markdown(f"**{user['NOME']}**  \n_{user['PERFIL']}_")
        if st.button("Sair"):
            logout()

    if not is_admin():
        st.error("Apenas administradores acessam esta página.")
        st.stop()

    st.warning(
        "O sistema já está configurado. Recarregar as bases aqui **substitui** o conteúdo atual de "
        "Pneus, Frota, Local e Classes_Pneu (login e histórico de alterações não são afetados). "
        "Prefira `scripts/sincronizar_frota.py` para trazer só localização/prefixos novos sem "
        "reconstruir tudo do zero — use esta tela só para uma recarga completa mesmo."
    )
    arq_pneus, arq_frota, arq_local, _, _, _ = _formulario_upload(exige_admin_novo=False)

    if st.button("Recarregar bases (substitui Pneus/Frota/Local/Classes_Pneu)", type="primary"):
        if not (arq_pneus and arq_frota and arq_local):
            st.error("Envie as 3 planilhas antes de continuar.")
        else:
            _rodar_carga(arq_pneus, arq_frota, arq_local, criar_admin=None)
            limpar_cache()
