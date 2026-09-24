import bcrypt
import pandas as pd
import streamlit as st

import src.medidas_padrao as medidas_padrao
from src.auth import exigir_login, is_admin, logout, usuario_logado
from src.classes_pneu import COLUNAS as COLUNAS_CLASSES_PNEU
from src.classes_pneu import TEM_PNEU_NAO, TEM_PNEU_REVISAR, TEM_PNEU_SIM, avaliar_prefixos_sem_pneu
from src.page_boot import logo_sidebar
from src.sheets_client import (
    ABA_CLASSES_PNEU,
    ABA_FROTA,
    ABA_MEDIDAS_PADRAO,
    ABA_PARAMETROS,
    ABA_PNEUS,
    ABA_USUARIOS,
    carregar_aba,
    df_para_valores,
    garantir_aba,
    limpar_cache,
    worksheet,
)
from src.theme import CUSTOM_CSS

st.set_page_config(page_title="Administração — Tripoloni", page_icon="🔐", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
logo_sidebar()
exigir_login()
user = usuario_logado()

with st.sidebar:
    st.markdown(f"**{user['NOME']}**  \n_{user['PERFIL']}_")
    if st.button("Sair"):
        logout()

st.title("Administração de usuários")

if not is_admin():
    st.error("Apenas administradores acessam esta página.")
    st.stop()

df_usuarios = carregar_aba(ABA_USUARIOS)
st.subheader("Usuários cadastrados")
st.dataframe(
    df_usuarios[["USUARIO", "NOME", "PERFIL", "OBRA_VINCULADA", "ATIVO"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("Novo usuário")

with st.form("novo_usuario"):
    c1, c2 = st.columns(2)
    novo_login = c1.text_input("Usuário (login)")
    novo_nome = c2.text_input("Nome completo")
    nova_senha = c1.text_input("Senha provisória", type="password")
    novo_perfil = c2.selectbox("Perfil", ["OBRA", "ADMIN"])
    nova_obra = st.text_input("Obra vinculada (deixe vazio se ADMIN)", disabled=(novo_perfil == "ADMIN"))
    criar = st.form_submit_button("Criar usuário")

if criar:
    if not novo_login or not nova_senha:
        st.error("Usuário e senha são obrigatórios.")
    elif novo_login.lower() in df_usuarios["USUARIO"].astype(str).str.lower().values:
        st.error("Já existe um usuário com esse login.")
    else:
        senha_hash = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        ws = worksheet(ABA_USUARIOS)
        ws.append_row(
            [
                novo_login.strip(),
                senha_hash,
                novo_nome.strip(),
                novo_perfil,
                "" if novo_perfil == "ADMIN" else nova_obra.strip(),
                "TRUE",
            ]
        )
        limpar_cache()
        st.success(f"Usuário '{novo_login}' criado.")
        st.rerun()

st.divider()
st.subheader("Classes operacionais — este tipo de ativo tem pneu?")
st.caption(
    "Quando o Consolidado Frota traz um prefixo de uma classe nunca vista (ex.: uma usina fixa, "
    "um gerador), ele fica pendente aqui em vez de entrar direto no banco de pneus. Confirme "
    "SIM/NÃO abaixo — MODELO em branco vale para toda a classe; preencha MODELO só para abrir uma "
    "exceção pontual dentro da classe."
)

df_classes = carregar_aba(ABA_CLASSES_PNEU)
if df_classes.empty:
    st.info("Nenhuma classe cadastrada ainda — rode a migração inicial ou uma sincronização de frota primeiro.")
else:
    pendentes_antes = int((df_classes["TEM_PNEU"] == TEM_PNEU_REVISAR).sum())
    if pendentes_antes:
        st.warning(f"{pendentes_antes} classe(s) aguardando revisão.")

    df_classes_editado = st.data_editor(
        df_classes,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "TEM_PNEU": st.column_config.SelectboxColumn(
                "Tem pneu?", options=[TEM_PNEU_SIM, TEM_PNEU_NAO, TEM_PNEU_REVISAR], required=True
            ),
            "QTD_ATIVOS": st.column_config.NumberColumn("Qtd. ativos", disabled=True),
            "EXEMPLO_GRUPO": st.column_config.TextColumn("Exemplo de grupo", disabled=True),
        },
        key="editor_classes_pneu",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Salvar revisão de classes"):
            ws = worksheet(ABA_CLASSES_PNEU)
            ws.clear()
            ws.update(df_para_valores(df_classes_editado), value_input_option="RAW")
            limpar_cache()
            st.success("Classes atualizadas.")
            st.rerun()

    with col_b:
        if st.button("Aplicar classes revisadas (criar pneus pendentes)", type="primary"):
            df_frota_atual = carregar_aba(ABA_FROTA)
            df_pneus_atual = carregar_aba(ABA_PNEUS)
            prefixos_com_registro = set(df_pneus_atual["PREFIXO"]) if not df_pneus_atual.empty else set()
            prefixos_sem_registro = sorted(set(df_frota_atual["PREFIXO"]) - prefixos_com_registro)

            resultado = avaliar_prefixos_sem_pneu(df_frota_atual, prefixos_sem_registro, df_classes_editado)

            if resultado["com_pneu"]:
                linhas = [
                    {
                        "PREFIXO": p,
                        "POSICAO": pos,
                        "MEDIDA": "",
                        "QTDE": 0,
                        "ULT_ATUALIZACAO": "",
                        "ATUALIZADO_POR": f"revisao_classes:{user['USUARIO']}",
                    }
                    for p in resultado["com_pneu"]
                    for pos in ["DIANTEIRO", "TRASEIRO", "STEP"]
                ]
                df_novas = pd.DataFrame(linhas)
                ws_pneus = worksheet(ABA_PNEUS)
                ws_pneus.append_rows(df_para_valores(df_novas)[1:], value_input_option="RAW")
                limpar_cache()

            st.success(
                f"{len(resultado['com_pneu'])} ativo(s) ganharam linhas de pneu. "
                f"{len(resultado['sem_pneu'])} confirmados sem pneu. "
                f"{len(resultado['pendentes'])} ainda pendentes (classe sem revisão)."
            )
            if resultado["com_pneu"]:
                st.rerun()

st.divider()
st.subheader("Medidas de pneu padronizadas")
st.caption(
    "Lista usada na tela Editar Equipamento — só se pode escolher uma medida daqui, pra evitar "
    "grafias diferentes pra mesma medida (ex.: \"1000R20\" vs \"10.00R20\"). Adicione, corrija ou "
    "remova linhas e salve."
)

garantir_aba(ABA_MEDIDAS_PADRAO, medidas_padrao.seed_inicial(carregar_aba(ABA_PNEUS)))
df_medidas_padrao = carregar_aba(ABA_MEDIDAS_PADRAO)
df_medidas_padrao_editado = st.data_editor(
    df_medidas_padrao,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    key="editor_medidas_padrao",
)
if st.button("Salvar medidas padronizadas"):
    medidas_limpas = (
        df_medidas_padrao_editado["MEDIDA"].astype(str).str.strip().replace("", pd.NA).dropna().drop_duplicates()
    )
    df_para_salvar = pd.DataFrame({"MEDIDA": sorted(medidas_limpas)})
    ws = worksheet(ABA_MEDIDAS_PADRAO)
    ws.clear()
    ws.update(df_para_valores(df_para_salvar), value_input_option="RAW")
    limpar_cache()
    st.success("Lista de medidas atualizada.")
    st.rerun()

st.divider()
st.subheader("Parâmetros de estoque")
st.caption(
    "Percentuais usados no cálculo de Estoque Solicitado e Estoque Mínimo (ver página Estoque). "
    "Estoque Solicitado = % Solicitado × pneus rodando. Estoque Mínimo = % Mínimo × Estoque Solicitado "
    "— é o gatilho: quando o estoque físico cair pra esse nível, pede-se reposição até o Estoque Solicitado."
)

garantir_aba(ABA_PARAMETROS, pd.DataFrame([{"PCT_SOLICITADO": 10, "PCT_MINIMO": 20}]))
df_parametros = carregar_aba(ABA_PARAMETROS)
linha_parametros = df_parametros.iloc[0] if not df_parametros.empty else {"PCT_SOLICITADO": 10, "PCT_MINIMO": 20}

col_p1, col_p2 = st.columns(2)
pct_solicitado = col_p1.number_input(
    "% Solicitado (sobre pneus rodando)", min_value=1, max_value=100, value=int(float(linha_parametros["PCT_SOLICITADO"]))
)
pct_minimo = col_p2.number_input(
    "% Mínimo (sobre o Estoque Solicitado)", min_value=1, max_value=100, value=int(float(linha_parametros["PCT_MINIMO"]))
)
if st.button("Salvar parâmetros de estoque"):
    ws = worksheet(ABA_PARAMETROS)
    ws.clear()
    ws.update(
        df_para_valores(pd.DataFrame([{"PCT_SOLICITADO": pct_solicitado, "PCT_MINIMO": pct_minimo}])),
        value_input_option="RAW",
    )
    limpar_cache()
    st.success("Parâmetros atualizados.")
    st.rerun()

st.caption(
    "Para trazer localização atualizada e prefixos novos direto de um Consolidado Frota mais recente, "
    "rode `python scripts/sincronizar_frota.py` (veja o cabeçalho do script para as opções)."
)
