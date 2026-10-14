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


def _ask(image: bytes) -> dict:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "format": SCHEMA,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 4096},
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT,
                    "images": [base64.b64encode(image).decode()],
                }
            ],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["message"]["content"])


def read_nota(path: str | Path) -> dict:
    """Devolve {fornecedor, documento, data, itens[]} cru, do jeito que o modelo leu."""
    path = Path(path)
    nota = {"fornecedor": "", "documento": "", "data": "", "itens": []}
    for image in _page_images(path):
        pagina = _ask(image)
        for campo in ("fornecedor", "documento", "data"):
            if not nota[campo]:
                nota[campo] = (pagina.get(campo) or "").strip()
        nota["itens"].extend(pagina.get("itens") or [])
    return nota
