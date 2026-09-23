"""Esquema ilustrativo do equipamento (SVG generico por eixo/posicao).

Nao existe um desenho fiel por modelo (a Frota tem 114 grupos distintos --
caminhao basculante, britador, motoniveladora, usina...). Em vez disso o
esquema e parametrico: 1 bloco por POSICAO (Dianteiro / Traseiro / Step) com
a medida e a quantidade atuais, o que cobre qualquer tipo de ativo com os
dados que ja existem na planilha. Clique-para-editar dentro do SVG exigiria
um componente Streamlit customizado (JS); aqui a edicao acontece nos campos
Streamlit logo abaixo de cada bloco, o que já resolve o fluxo de "ver a
posição e trocar a medida" sem essa complexidade extra.
"""

from __future__ import annotations

from src.theme import AZUL_ESCURO_2, AZUL_PRINCIPAL, BRANCO, CINZA_CLARO, CORES_POSICAO

_ORDEM_POSICOES = ["DIANTEIRO", "TRASEIRO", "STEP"]


def _bloco_svg(x: int, posicao: str, medida: str, qtde: int) -> str:
    cor = CORES_POSICAO.get(posicao, AZUL_PRINCIPAL)
    medida_txt = medida if medida and str(medida).strip() else "sem medida"
    return f"""
    <g transform="translate({x},0)">
      <rect x="0" y="0" width="150" height="120" rx="10" fill="{BRANCO}" stroke="{cor}" stroke-width="3"/>
      <circle cx="30" cy="60" r="22" fill="{cor}" opacity="0.15" stroke="{cor}" stroke-width="3"/>
      <circle cx="30" cy="60" r="8" fill="{cor}"/>
      <text x="75" y="30" font-size="13" font-weight="bold" fill="{AZUL_ESCURO_2}" text-anchor="middle">{posicao}</text>
      <text x="75" y="70" font-size="14" fill="{AZUL_ESCURO_2}" text-anchor="middle">{medida_txt}</text>
      <text x="75" y="95" font-size="24" font-weight="bold" fill="{cor}" text-anchor="middle">{qtde}x</text>
    </g>
    """


def render_svg(prefixo: str, dados_por_posicao: dict) -> str:
    """dados_por_posicao: {'DIANTEIRO': {'medida': ..., 'qtde': ...}, ...}"""
    blocos = []
    x = 20
    total = 0
    for pos in _ORDEM_POSICOES:
        info = dados_por_posicao.get(pos)
        if not info:
            continue
        qtde = int(info.get("qtde") or 0)
        total += qtde
        blocos.append(_bloco_svg(x, pos, info.get("medida", ""), qtde))
        x += 170

    largura = max(x + 20, 200)
    svg = f"""
    <svg width="{largura}" height="170" viewBox="0 0 {largura} 170" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="{largura}" height="170" fill="{CINZA_CLARO}" rx="12"/>
      <text x="20" y="20" font-size="15" font-weight="bold" fill="{AZUL_ESCURO_2}">{prefixo} — total de {total} pneus</text>
      <g transform="translate(0,25)">
        {''.join(blocos)}
      </g>
    </svg>
    """
    return svg
