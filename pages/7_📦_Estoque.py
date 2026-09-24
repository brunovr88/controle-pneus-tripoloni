import pandas as pd
import streamlit as st

from src.auth import usuario_logado
from src.calculations import calcular_estoque
from src.page_boot import boot
from src.sheets_client import (
    ABA_ESTOQUE_FISICO,
    ABA_PARAMETROS,
    carregar_aba,
    df_para_valores,
    garantir_aba,
    limpar_cache,
    worksheet,
)

_, df = boot("Estoque", icone="📦")
user = usuario_logado()

st.caption(
    "Estoque Solicitado = % Solicitado × pneus rodando no projeto (por obra e medida). "
    "Estoque Mínimo = % Mínimo × Estoque Solicitado — é o gatilho de compra: quando o Estoque Físico "
    "cair pra esse nível (ou abaixo), pede-se reposição até completar o Estoque Solicitado. "
    "Os percentuais são ajustáveis em Administração; como o Estoque Solicitado/Mínimo é recalculado "
    "sempre a partir dos pneus rodando agora, ele sobe e desce sozinho conforme equipamentos "
    "mobilizam/desmobilizam do projeto."
)

garantir_aba(ABA_PARAMETROS, pd.DataFrame([{"PCT_SOLICITADO": 10, "PCT_MINIMO": 20}]))
df_parametros = carregar_aba(ABA_PARAMETROS)
linha_parametros = df_parametros.iloc[0] if not df_parametros.empty else {"PCT_SOLICITADO": 10, "PCT_MINIMO": 20}
pct_solicitado = float(linha_parametros["PCT_SOLICITADO"]) / 100
pct_minimo = float(linha_parametros["PCT_MINIMO"]) / 100

df_medidas = df[df["MEDIDA"] != ""]
estoque = calcular_estoque(df_medidas, ["OBRA_LOCAL", "MEDIDA"], pct_solicitado=pct_solicitado, pct_minimo=pct_minimo)

garantir_aba(
    ABA_ESTOQUE_FISICO,
    pd.DataFrame(columns=["OBRA_LOCAL", "MEDIDA", "QTDE_ESTOQUE", "ULT_ATUALIZACAO", "ATUALIZADO_POR"]),
)
df_estoque_fisico = carregar_aba(ABA_ESTOQUE_FISICO)
if not df_estoque_fisico.empty:
    df_estoque_fisico["QTDE_ESTOQUE"] = pd.to_numeric(df_estoque_fisico["QTDE_ESTOQUE"], errors="coerce").fillna(0).astype(int)
    estoque = estoque.merge(df_estoque_fisico[["OBRA_LOCAL", "MEDIDA", "QTDE_ESTOQUE"]], on=["OBRA_LOCAL", "MEDIDA"], how="left")
else:
    estoque["QTDE_ESTOQUE"] = pd.NA
estoque["QTDE_ESTOQUE"] = estoque["QTDE_ESTOQUE"].fillna(0).astype(int)
estoque["STATUS"] = estoque.apply(
    lambda r: "🔴 COMPRAR" if r["QTDE_ESTOQUE"] <= r["ESTOQUE_MINIMO"] else "🟢 OK", axis=1
)
estoque = estoque.sort_values(["STATUS", "QTDE_RODANDO"], ascending=[True, False])

col1, col2, col3 = st.columns(3)
col1.metric("Obra × Medida em alerta", int((estoque["STATUS"] == "🔴 COMPRAR").sum()))
col2.metric("Total de combinações", len(estoque))
col3.metric("% Solicitado / % Mínimo atuais", f"{pct_solicitado*100:.0f}% / {pct_minimo*100:.0f}%")

st.subheader("Estoque por Obra × Medida")
st.caption(
    "Edite a coluna **Estoque Físico** com a quantidade que tem hoje no almoxarifado/oficina e clique "
    "em Salvar. As demais colunas são calculadas e não são editáveis aqui."
)

estoque_editado = st.data_editor(
    estoque[["OBRA_LOCAL", "MEDIDA", "QTDE_RODANDO", "ESTOQUE_SOLICITADO", "ESTOQUE_MINIMO", "QTDE_ESTOQUE", "STATUS"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "OBRA_LOCAL": st.column_config.TextColumn("Obra", disabled=True),
        "MEDIDA": st.column_config.TextColumn("Medida", disabled=True),
        "QTDE_RODANDO": st.column_config.NumberColumn("Pneus rodando", disabled=True),
        "ESTOQUE_SOLICITADO": st.column_config.NumberColumn("Estoque solicitado", disabled=True),
        "ESTOQUE_MINIMO": st.column_config.NumberColumn("Estoque mínimo (gatilho)", disabled=True),
        "QTDE_ESTOQUE": st.column_config.NumberColumn("Estoque físico", min_value=0, step=1),
        "STATUS": st.column_config.TextColumn("Status", disabled=True),
    },
    key="editor_estoque_fisico",
)

if st.button("Salvar estoque físico", type="primary"):
    import datetime as dt

    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_salvar = estoque_editado[["OBRA_LOCAL", "MEDIDA", "QTDE_ESTOQUE"]].copy()
    df_salvar["ULT_ATUALIZACAO"] = agora
    df_salvar["ATUALIZADO_POR"] = user["USUARIO"]

    ws = worksheet(ABA_ESTOQUE_FISICO)
    ws.clear()
    ws.update(df_para_valores(df_salvar), value_input_option="RAW")
    limpar_cache()
    st.success("Estoque físico salvo.")
    st.rerun()
