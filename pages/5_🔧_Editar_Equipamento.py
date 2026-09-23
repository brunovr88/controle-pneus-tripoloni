import streamlit.components.v1 as components
import streamlit as st

from src.auth import is_admin, obra_do_usuario, usuario_logado
from src.diagram import render_svg
from src.page_boot import boot
from src.sheets_client import ABA_FROTA, atualizar_linha_pneu, atualizar_linha_por_chave

# Precisa rodar ANTES do boot() (que cria o widget "filtro_prefixo"): so e permitido
# pre-semear st.session_state de uma key de widget antes dela ser instanciada.
if "prefixo_para_corrigir" in st.session_state:
    st.session_state["filtro_prefixo"] = st.session_state.pop("prefixo_para_corrigir")

df_completo, _ = boot("Editar Equipamento", icone="🔧")
user = usuario_logado()

st.caption(
    "Selecione o equipamento pelo filtro **Equipamento (prefixo)** na barra lateral. "
    "O esquema abaixo é ilustrativo por posição (Dianteiro / Traseiro / Step) — "
    "edite a medida e a quantidade e salve para gravar direto no Google Sheets."
)

prefixo_sel = st.session_state.get("filtro_prefixo")
if not prefixo_sel or prefixo_sel == "(todos)":
    st.info("Escolha um equipamento no filtro à esquerda para editar.")
    st.stop()

ativo = df_completo[df_completo["PREFIXO"] == prefixo_sel]
if ativo.empty:
    st.error("Equipamento não encontrado no escopo atual.")
    st.stop()

obra_ativo = ativo["OBRA_LOCAL"].iloc[0]
if not is_admin() and obra_ativo != obra_do_usuario():
    st.error("Este equipamento não pertence à sua obra. Você não tem permissão para editá-lo.")
    st.stop()

dados_por_posicao = {
    row["POSICAO"]: {"medida": row["MEDIDA"], "qtde": row["QTDE"]} for _, row in ativo.iterrows()
}

st.subheader(f"Equipamento {prefixo_sel} — {ativo['MODELO'].iloc[0] or 'modelo não informado'}")
components.html(render_svg(prefixo_sel, dados_por_posicao), height=200)

st.markdown("#### Dados cadastrais do ativo")
col1, col2, col3 = st.columns(3)
obras_disponiveis = sorted(df_completo["OBRA_LOCAL"].dropna().unique().tolist())
status_atual = str(ativo["STATUS_CADASTRO"].iloc[0] or "NAO IDENTIFICADO").upper()

with col1:
    nova_obra = st.selectbox(
        "Obra vinculada",
        obras_disponiveis,
        index=obras_disponiveis.index(obra_ativo) if obra_ativo in obras_disponiveis else 0,
        disabled=not is_admin(),
        key=f"obra_edit_{prefixo_sel}",
    )
with col2:
    novo_status = st.selectbox(
        "Status do cadastro",
        ["IDENTIFICADO", "NAO IDENTIFICADO"],
        index=0 if status_atual == "IDENTIFICADO" else 1,
        key=f"status_edit_{prefixo_sel}",
    )
with col3:
    st.metric("Total de pneus", int(ativo["QTDE"].sum()))

if st.button("Salvar dados cadastrais"):
    atualizar_linha_por_chave(
        ABA_FROTA, "PREFIXO", prefixo_sel, {"OBRA_LOCAL": nova_obra, "STATUS_CADASTRO": novo_status}, user["USUARIO"]
    )
    st.success("Dados cadastrais atualizados.")
    st.rerun()

st.markdown("#### Medida e quantidade por posição")
novos_valores = {}
for posicao in ["DIANTEIRO", "TRASEIRO", "STEP"]:
    info = dados_por_posicao.get(posicao, {"medida": "", "qtde": 0})
    c1, c2, c3 = st.columns([1, 2, 1])
    c1.markdown(f"**{posicao}**")
    medida = c2.text_input(
        f"Medida — {posicao}", value=info["medida"], key=f"medida_{prefixo_sel}_{posicao}", label_visibility="collapsed"
    )
    qtde = c3.number_input(
        f"Qtde — {posicao}",
        value=int(info["qtde"]),
        min_value=0,
        step=1,
        key=f"qtde_{prefixo_sel}_{posicao}",
        label_visibility="collapsed",
    )
    novos_valores[posicao] = {"MEDIDA": medida.strip(), "QTDE": qtde}

if st.button("Salvar alterações de pneus", type="primary"):
    algo_mudou = False
    for posicao, valores in novos_valores.items():
        info_atual = dados_por_posicao.get(posicao)
        if info_atual is None:
            continue
        if str(info_atual["medida"]) == valores["MEDIDA"] and int(info_atual["qtde"]) == valores["QTDE"]:
            continue
        atualizar_linha_pneu(prefixo_sel, posicao, valores, user["USUARIO"])
        algo_mudou = True
    if algo_mudou:
        st.success("Alterações salvas no Google Sheets.")
        st.rerun()
    else:
        st.info("Nenhuma alteração para salvar.")
