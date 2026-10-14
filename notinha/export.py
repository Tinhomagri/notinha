"""Saídas: CSV pronto pra importar e relatório de conferência no terminal."""

import csv
from decimal import Decimal
from pathlib import Path

# Mesmo cabeçalho do modelo de importação de estoque usado pelo PDV.
CABECALHO_ESTOQUE = [
    "Nome", "Tipo", "Unidade", "Código de Barras", "Código do Produto",
    "Descrição", "Estoque Inicial", "Custo Unitário", "Estoque Mínimo",
    "Estoque Máximo", "Fornecedor", "Prazo de Entrega (dias)", "Foto",
]


def br(valor: Decimal | None) -> str:
    if valor is None:
        return ""
    texto = format(valor.normalize(), "f")
    return texto.replace(".", ",")


def escrever_csv(nota: dict, destino: str | Path) -> Path:
    destino = Path(destino)
    with destino.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(CABECALHO_ESTOQUE)
        for item in nota["itens"]:
            escritor.writerow([
                item["descricao"], "insumo", item["unidade_uso"], "", "",
                f"{nota['fornecedor']} {nota['documento']}".strip(),
                br(item["quantidade_uso"]), br(item["custo_unidade_uso"]),
                "", "", nota["fornecedor"], "", "",
            ])
    return destino


def relatorio(nota: dict) -> str:
    linhas = [
        f"Fornecedor: {nota['fornecedor'] or '—'}   "
        f"Doc: {nota['documento'] or '—'}   Data: {nota['data'] or '—'}",
        f"{len(nota['itens'])} itens · total lido R$ {br(nota['total_itens'])}",
        "",
    ]
    largura = max((len(i["descricao"]) for i in nota["itens"]), default=10)
    largura = min(max(largura, 10), 42)
    linhas.append(
        f"{'ITEM'.ljust(largura)}  {'QTD':>10}  {'UNIT':>10}  {'CUSTO USO':>12}"
    )
    for item in nota["itens"]:
        nome = item["descricao"][:largura].ljust(largura)
        uso = f"{br(item['custo_unidade_uso'])}/{item['unidade_uso']}"
        linhas.append(
            f"{nome}  {br(item['quantidade']):>10}  "
            f"{br(item['valor_unitario']):>10}  {uso:>12}"
        )
        for alerta in item["alertas"]:
            linhas.append(f"{' ' * largura}  ⚠ {alerta}")
    if nota["itens_com_alerta"]:
        linhas += ["", f"⚠ {nota['itens_com_alerta']} item(ns) pedem conferência."]
    return "\n".join(linhas)
