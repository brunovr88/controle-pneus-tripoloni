"""Login e controle de acesso por obra (row-level security).

Usuarios ficam na aba 'Usuarios' do Google Sheets: usuario, senha_hash (bcrypt),
nome, perfil (ADMIN ou OBRA) e obra_vinculada. Perfil ADMIN enxerga e edita
todas as obras; perfil OBRA fica travado na obra_vinculada em toda a sessao.
"""

from __future__ import annotations

import bcrypt
import streamlit as st

from src.sheets_client import ABA_USUARIOS, carregar_aba


def _buscar_usuario(usuario: str):
    df = carregar_aba(ABA_USUARIOS)
    if df.empty:
        return None
    linhas = df[df["USUARIO"].astype(str).str.lower() == usuario.strip().lower()]
    if linhas.empty:
        return None
    return linhas.iloc[0].to_dict()


def _senha_confere(senha_digitada: str, hash_armazenado: str) -> bool:
    try:
        return bcrypt.checkpw(senha_digitada.encode("utf-8"), hash_armazenado.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def usuario_logado() -> dict | None:
    return st.session_state.get("usuario_autenticado")


def is_admin() -> bool:
    u = usuario_logado()
    return bool(u) and str(u.get("PERFIL", "")).upper() == "ADMIN"


def obra_do_usuario() -> str | None:
    """Obra que trava o filtro global. None para ADMIN (sem trava)."""
    u = usuario_logado()
    if not u or is_admin():
        return None
    return u.get("OBRA_VINCULADA")


def logout():
    st.session_state.pop("usuario_autenticado", None)
    st.rerun()


def exigir_login():
    """Bloqueia a pagina com uma tela de login ate autenticar. Chamar no topo de cada pagina."""
    if usuario_logado():
        return

    st.markdown("## Controle de Pneus — Login")
    with st.form("form_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        registro = _buscar_usuario(usuario)
        if not registro:
            st.error("Usuário não encontrado.")
            st.stop()
        if str(registro.get("ATIVO", "TRUE")).upper() not in ("TRUE", "1", "SIM"):
            st.error("Usuário desativado. Fale com o administrador.")
            st.stop()
        if not _senha_confere(senha, str(registro.get("SENHA_HASH", ""))):
            st.error("Senha incorreta.")
            st.stop()

        st.session_state["usuario_autenticado"] = {
            "USUARIO": registro["USUARIO"],
            "NOME": registro.get("NOME", registro["USUARIO"]),
            "PERFIL": registro.get("PERFIL", "OBRA"),
            "OBRA_VINCULADA": registro.get("OBRA_VINCULADA", ""),
        }
        st.rerun()

    st.stop()
