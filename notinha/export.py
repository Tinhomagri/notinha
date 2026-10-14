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
        origem = f"{nota['fornecedor']} {nota['documento']}".strip()
        for item in nota["itens"]:
            # Linha marcada vai sem número: melhor o importador reclamar de campo
            # vazio do que entrar custo errado calado na ficha técnica.
            marcada = bool(item["alertas"])
            descricao = (
                f"CONFERIR ({'; '.join(item['alertas'])}) — {origem}"
                if marcada else origem
            )
            escritor.writerow([
                item["descricao"], "insumo", item["unidade_uso"], "", "",
                descricao,
                "" if marcada else br(item["quantidade_uso"]),
                "" if marcada else br(item["custo_unidade_uso"]),
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
        for nota_item in item.get("notas", []):
            linhas.append(f"{' ' * largura}  ↻ {nota_item}")
    if nota["itens_com_alerta"]:
        linhas += ["", f"⚠ {nota['itens_com_alerta']} item(ns) pedem conferência."]
    return "\n".join(linhas)
