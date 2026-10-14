"""Leitura da nota pelo modelo aberto rodando no Ollama local."""

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("NOTINHA_OLLAMA", "http://localhost:11434")
MODEL = os.environ.get("NOTINHA_MODEL", "gemma3:4b")
TIMEOUT = int(os.environ.get("NOTINHA_TIMEOUT", "900"))

# Os números vêm como string de propósito: o modelo escreve "1.234,56" e
# qualquer coerção para number do JSON vira 1.234 silenciosamente.
SCHEMA = {
    "type": "object",
    "properties": {
        "fornecedor": {"type": "string"},
        "documento": {"type": "string"},
        "data": {"type": "string"},
        "itens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "quantidade": {"type": "string"},
                    "unidade": {"type": "string"},
                    "valor_unitario": {"type": "string"},
                    "valor_total": {"type": "string"},
                },
                "required": [
                    "descricao",
                    "quantidade",
                    "unidade",
                    "valor_unitario",
                    "valor_total",
                ],
            },
        },
    },
    "required": ["fornecedor", "documento", "data", "itens"],
}

PROMPT = """Você está lendo a foto de uma nota fiscal ou pedido de um fornecedor brasileiro.

Extraia o nome do fornecedor, o número do documento (pedido/NF), a data de emissão
e TODOS os itens da tabela de produtos, linha por linha, de cima para baixo.

Regras:
- Copie os números exatamente como aparecem no papel, com vírgula decimal. Não converta, não arredonde, não calcule nada.
- A unidade é a sigla da coluna UN/UNID (UN, KG, CX, PC, FD, L, DZ). Se a descrição disser a embalagem (ex: "CX 12X1L"), mantenha na descrição.
- Não invente itens. Se um campo estiver ilegível, devolva string vazia.
- Ignore cabeçalho, impostos, frete e o total da nota: só a tabela de produtos.
"""

SCHEMA_LINHA = {
    "type": "object",
    "properties": {
        "quantidade": {"type": "string"},
        "unidade": {"type": "string"},
        "valor_unitario": {"type": "string"},
    },
    "required": ["quantidade", "unidade", "valor_unitario"],
}

PROMPT_LINHA = """Na nota da imagem, ache a linha do produto "{descricao}".

Essa linha tem valor total {total}. Olhe só para ela e devolva a quantidade, a
unidade e o valor unitário dessa linha, copiados exatamente como estão escritos,
com vírgula decimal.

Atenção à coluna QTD: números como 12,500 são um só valor, não dois.
Quantidade x valor unitário precisa dar {total}."""


def _page_images(path: Path) -> list[bytes]:
    """PDF vira PNG por página; imagem vai direto."""
    if path.suffix.lower() != ".pdf":
        return [path.read_bytes()]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "200", str(path), f"{tmp}/pg"],
            check=True,
            capture_output=True,
        )
        return [p.read_bytes() for p in sorted(Path(tmp).glob("pg*.png"))]


def _ask(image: bytes, prompt: str, schema: dict) -> dict:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 4096},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64.b64encode(image).decode()],
                }
            ],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["message"]["content"])


def read_nota(path: str | Path) -> tuple[dict, list[bytes]]:
    """Leitura crua da nota. Devolve os dados e as páginas, pra poder reler linha."""
    path = Path(path)
    nota = {"fornecedor": "", "documento": "", "data": "", "itens": []}
    imagens = _page_images(path)
    for indice, image in enumerate(imagens):
        pagina = _ask(image, PROMPT, SCHEMA)
        for campo in ("fornecedor", "documento", "data"):
            if not nota[campo]:
                nota[campo] = (pagina.get(campo) or "").strip()
        for item in pagina.get("itens") or []:
            item["pagina"] = indice
            nota["itens"].append(item)
    return nota, imagens


def reler_linha(image: bytes, descricao: str, total: str) -> dict:
    """Segunda leitura de UMA linha, ancorada no total que já conferimos."""
    return _ask(image, PROMPT_LINHA.format(descricao=descricao, total=total), SCHEMA_LINHA)
