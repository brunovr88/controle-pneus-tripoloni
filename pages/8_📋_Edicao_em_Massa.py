import src.medidas_padrao as medidas_padrao
from src.auth import is_admin, usuario_logado
from src.page_boot import boot
from src.sheets_client import (
    ABA_FROTA,
    ABA_MEDIDAS_PADRAO,
    atualizar_linha_pneu,
    atualizar_linha_por_chave,
    carregar_aba,
    garantir_aba,
)
import streamlit as st

df_completo, df_filtrado = boot("Edição em Massa", icone="📋")
user = usuario_logado()

st.caption(
    "Aplica a mesma alteração para vários equipamentos de uma vez — útil em mobilização/desmobilização "
    "em lote. A lista abaixo respeita os filtros da barra lateral: filtre primeiro (por obra, modelo, "
    "classe...) pra facilitar achar os equipamentos certos."
)

prefixos_disponiveis = sorted(df_filtrado["PREFIXO"].dropna().unique().tolist())
if not prefixos_disponiveis:
    st.info("Nenhum equipamento no escopo atual dos filtros.")
    st.stop()

prefixos_selecionados = st.multiselect(
    f"Equipamentos ({len(prefixos_disponiveis)} disponíveis no filtro atual)", prefixos_disponiveis
)

if not prefixos_selecionados:
    st.info("Selecione ao menos um equipamento para habilitar as ações em massa.")
    st.stop()

st.success(f"{len(prefixos_selecionados)} equipamento(s) selecionado(s).")

st.divider()
st.subheader("O que alterar")
acao = st.radio(
    "Ação",
    ["Obra vinculada", "Status do cadastro", "Medida de uma posição"],
    horizontal=True,
    label_visibility="collapsed",
)

if acao == "Obra vinculada":
    if not is_admin():
        st.error("Só administradores podem alterar obra vinculada em massa.")
        st.stop()
    obras_disponiveis = sorted(df_completo["OBRA_LOCAL"].dropna().unique().tolist())
    nova_obra = st.selectbox("Nova obra vinculada", obras_disponiveis)

    if st.button(f"Aplicar a {len(prefixos_selecionados)} equipamento(s)", type="primary"):
        barra = st.progress(0.0)
        for i, prefixo in enumerate(prefixos_selecionados):
            atualizar_linha_por_chave(ABA_FROTA, "PREFIXO", prefixo, {"OBRA_LOCAL": nova_obra}, user["USUARIO"])
            barra.progress((i + 1) / len(prefixos_selecionados))
        st.success(f"Obra atualizada para {len(prefixos_selecionados)} equipamento(s).")
        st.rerun()

elif acao == "Status do cadastro":
    novo_status = st.selectbox("Novo status", ["IDENTIFICADO", "NAO IDENTIFICADO"])

    if st.button(f"Aplicar a {len(prefixos_selecionados)} equipamento(s)", type="primary"):
        barra = st.progress(0.0)
        for i, prefixo in enumerate(prefixos_selecionados):
            atualizar_linha_por_chave(ABA_FROTA, "PREFIXO", prefixo, {"STATUS_CADASTRO": novo_status}, user["USUARIO"])
            barra.progress((i + 1) / len(prefixos_selecionados))
        st.success(f"Status atualizado para {len(prefixos_selecionados)} equipamento(s).")
        st.rerun()

else:
    posicao = st.selectbox("Posição", ["DIANTEIRO", "TRASEIRO", "STEP"])

    garantir_aba(ABA_MEDIDAS_PADRAO, medidas_padrao.seed_inicial(df_completo))
    lista_medidas = sorted(carregar_aba(ABA_MEDIDAS_PADRAO)["MEDIDA"].dropna().astype(str).str.strip().unique().tolist())
    lista_medidas = [m for m in lista_medidas if m]
    nova_medida = st.selectbox("Nova medida", lista_medidas)

    st.caption(
        "A quantidade de pneus por posição de cada equipamento não é alterada aqui, só a medida "
        "— use a tela Editar Equipamento pra mudar quantidade individualmente."
    )

    if st.button(f"Aplicar a {len(prefixos_selecionados)} equipamento(s)", type="primary"):
        barra = st.progress(0.0)
        for i, prefixo in enumerate(prefixos_selecionados):
            linha_atual = df_completo[(df_completo["PREFIXO"] == prefixo) & (df_completo["POSICAO"] == posicao)]
            qtde_atual = int(linha_atual["QTDE"].iloc[0]) if not linha_atual.empty else 0
            atualizar_linha_pneu(prefixo, posicao, {"MEDIDA": nova_medida, "QTDE": qtde_atual}, user["USUARIO"])
            barra.progress((i + 1) / len(prefixos_selecionados))
        st.success(f"Medida de {posicao} atualizada para {len(prefixos_selecionados)} equipamento(s).")
        st.rerun()
