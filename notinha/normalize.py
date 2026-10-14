"""Transforma o que o modelo leu em custo por unidade de uso da cozinha."""

import re
from decimal import Decimal, InvalidOperation

CENTAVO = Decimal("0.01")
MILESIMO = Decimal("0.001")

# Sigla do fornecedor -> unidade que a cozinha usa pra medir.
UNIDADE_CANONICA = {
    "KG": "KG", "KGS": "KG", "QUILO": "KG", "QUILOS": "KG",
    "G": "G", "GR": "G", "GRS": "G", "GRAMA": "G", "GRAMAS": "G",
    "L": "L", "LT": "L", "LTS": "L", "LITRO": "L", "LITROS": "L",
    "ML": "ML",
    "UN": "UN", "UND": "UN", "UNID": "UN", "UNIDADE": "UN", "PC": "UN",
    "PÇ": "UN", "PCT": "UN", "PACOTE": "UN", "PT": "UN",
    "CX": "CX", "CAIXA": "CX", "FD": "FD", "FARDO": "FD",
    "DZ": "DZ", "DUZIA": "DZ", "DÚZIA": "DZ",
    "SC": "SC", "SACO": "SC", "SACA": "SC",
}

# Quantas unidades de venda cabem na embalagem fechada.
FATOR_EMBALAGEM = {"CX": None, "FD": None, "DZ": Decimal(12), "SC": None}

# "CX 12X1L", "FD C/ 6 X 500ML", "PCT 5KG"
RE_PACK = re.compile(
    r"(?:(\d{1,3})\s*[X*]\s*)?(\d+(?:[.,]\d+)?)\s*(KG|G|GR|L|LT|ML|UN)\b",
    re.IGNORECASE,
)
RE_MULTIPLO = re.compile(r"\b(?:C/\s*)?(\d{1,3})\s*[X*]\s*", re.IGNORECASE)
# "FD 6X2 ROLOS", "CX 4X6 POTES": não tem KG/L, mas tem contagem fechada.
RE_PACK_CONTAGEM = re.compile(r"\b(\d{1,3})\s*[X*]\s*(\d{1,3})\b(?!\s*(?:KG|G|L|ML))", re.IGNORECASE)


def para_decimal(texto: str) -> Decimal | None:
    """'1.234,56' -> 1234.56 ; '12.5' -> 12.5 ; 'R$ 42,00' -> 42.00"""
    if texto is None:
        return None
    limpo = re.sub(r"[^\d.,-]", "", str(texto)).strip()
    if not limpo:
        return None
    if "," in limpo:
        # vírgula é o decimal: ponto só pode ser separador de milhar
        limpo = limpo.replace(".", "").replace(",", ".")
    elif limpo.count(".") > 1:
        limpo = limpo.replace(".", "")
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


def canonizar_unidade(sigla: str) -> str:
    return UNIDADE_CANONICA.get(re.sub(r"[^A-ZÇ]", "", (sigla or "").upper()), "UN")


def conteudo_embalagem(descricao: str, unidade: str) -> tuple[Decimal, str] | None:
    """'CX 12X1L' com unidade CX -> (12 L, 'L'). Devolve None se não der pra afirmar."""
    if unidade not in FATOR_EMBALAGEM:
        return None
    if FATOR_EMBALAGEM[unidade] is not None:
        return FATOR_EMBALAGEM[unidade], "UN"
    achado = RE_PACK.search(descricao or "")
    if not achado:
        contagem = RE_PACK_CONTAGEM.search(descricao or "")
        if contagem:
            return Decimal(contagem.group(1)) * Decimal(contagem.group(2)), "UN"
        return None
    multiplo, medida, sigla = achado.groups()
    if multiplo is None:
        solto = RE_MULTIPLO.search(descricao or "")
        multiplo = solto.group(1) if solto else "1"
    total = Decimal(multiplo) * (para_decimal(medida) or Decimal(0))
    base = canonizar_unidade(sigla)
    if base == "G":
        return (total / 1000).quantize(MILESIMO), "KG"
    if base == "ML":
        return (total / 1000).quantize(MILESIMO), "L"
    return total, base


def normalizar_item(bruto: dict) -> dict:
    descricao = (bruto.get("descricao") or "").strip()
    quantidade = para_decimal(bruto.get("quantidade"))
    unitario = para_decimal(bruto.get("valor_unitario"))
    total = para_decimal(bruto.get("valor_total"))
    unidade = canonizar_unidade(bruto.get("unidade"))

    # Qualquer um dos três sai do outro: nota amassada costuma comer uma coluna.
    if quantidade and unitario and total is None:
        total = (quantidade * unitario).quantize(CENTAVO)
    elif quantidade and total and unitario is None and quantidade:
        unitario = (total / quantidade).quantize(CENTAVO)
    elif unitario and total and quantidade is None and unitario:
        quantidade = (total / unitario).quantize(MILESIMO)

    item = {
        "descricao": descricao,
        "quantidade": quantidade,
        "unidade": unidade,
        "valor_unitario": unitario,
        "valor_total": total,
        "custo_unidade_uso": unitario,
        "unidade_uso": unidade,
        "quantidade_uso": quantidade,
        "alertas": [],
        "notas": [],
    }

    # Caixa fechada vira custo por litro/quilo/unidade, que é como a ficha técnica pensa.
    conteudo = conteudo_embalagem(descricao, unidade)
    if conteudo and conteudo[0] > 0 and unitario:
        total_conteudo, unidade_uso = conteudo
        item["custo_unidade_uso"] = (unitario / total_conteudo).quantize(MILESIMO)
        item["unidade_uso"] = unidade_uso
        if quantidade:
            item["quantidade_uso"] = (quantidade * total_conteudo).quantize(MILESIMO)
    elif unidade in FATOR_EMBALAGEM:
        item["alertas"].append("embalagem fechada sem conteúdo declarado na descrição")

    # Confere a conta do fornecedor: divergência quase sempre é leitura errada de dígito.
    if quantidade and unitario and total:
        esperado = (quantidade * unitario).quantize(CENTAVO)
        if abs(esperado - total) > max(CENTAVO, total * Decimal("0.01")):
            item["alertas"].append(f"qtd x unitário = {esperado}, nota diz {total}")

    for campo in ("descricao", "quantidade", "valor_unitario"):
        if not item[campo]:
            item["alertas"].append(f"{campo} não foi lido")

    return item


def normalizar(nota: dict) -> dict:
    itens = [normalizar_item(i) for i in nota.get("itens", [])]
    soma = sum((i["valor_total"] for i in itens if i["valor_total"]), Decimal(0))
    return {
        "fornecedor": (nota.get("fornecedor") or "").strip(),
        "documento": (nota.get("documento") or "").strip(),
        "data": (nota.get("data") or "").strip(),
        "itens": itens,
        "total_itens": soma.quantize(CENTAVO),
        "itens_com_alerta": sum(1 for i in itens if i["alertas"]),
    }
