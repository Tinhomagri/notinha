"""Leitura completa: lê, confere, relê o que não fechou, confere de novo."""

from pathlib import Path

from .export import br as _br
from .extract import read_nota, reler_linha
from .normalize import normalizar, normalizar_item


def _desconfia(item: dict) -> bool:
    """Vale a pena gastar uma segunda inferência nesta linha?"""
    # Só relê o que tem total legível: sem âncora, a releitura é só outro palpite.
    return bool(item["alertas"]) and item["valor_total"] is not None


def processar(caminho: str | Path, reparar: bool = True) -> dict:
    bruto, imagens = read_nota(caminho)
    nota = normalizar(bruto)
    if not reparar:
        return nota

    for posicao, item in enumerate(nota["itens"]):
        if not _desconfia(item):
            continue
        pagina = imagens[min(bruto["itens"][posicao].get("pagina", 0), len(imagens) - 1)]
        try:
            relido = reler_linha(
                pagina, item["descricao"], f"{item['valor_total']:f}".replace(".", ",")
            )
        except Exception:
            continue  # releitura é melhoria; se falhar, fica a linha marcada

        total_txt = f"{item['valor_total']:f}".replace(".", ",")
        base = {
            "descricao": item["descricao"],
            "unidade": relido.get("unidade") or item["unidade"],
            "valor_unitario": relido.get("valor_unitario"),
            "valor_total": total_txt,
        }

        # 1ª escolha: a releitura inteira fecha a conta sozinha.
        candidato = normalizar_item({**base, "quantidade": relido.get("quantidade")})
        if not candidato["alertas"]:
            candidato["relido"] = True
            nota["itens"][posicao] = candidato
            continue

        # 2ª escolha: fica o unitário da releitura e a quantidade sai do total.
        # Só vale quando a leitura focada discorda da leitura larga — desalinhamento
        # de coluna é falha da tabela inteira, não de um campo lido isoladamente.
        unitario_novo = normalizar_item(base)["valor_unitario"]
        if unitario_novo is None or unitario_novo == item["valor_unitario"]:
            continue
        derivado = normalizar_item({**base, "quantidade": None})
        if derivado["alertas"] or not derivado["quantidade"]:
            continue
        derivado["relido"] = True
        derivado["notas"] = [
            f"unitário relido ({_br(unitario_novo)}); "
            f"quantidade calculada: {_br(item['valor_total'])} ÷ {_br(unitario_novo)}"
        ]
        nota["itens"][posicao] = derivado

    nota["itens_com_alerta"] = sum(1 for i in nota["itens"] if i["alertas"])
    nota["itens_relidos"] = sum(1 for i in nota["itens"] if i.get("relido"))
    return nota
