"""Gera uma nota de fornecedor SINTÉTICA pra testar sem expor dado de cliente.

Nenhum CNPJ, nome ou preço aqui é real. Rode `python3 samples/make_sample.py`.
"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).parent
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

CABECALHO = [
    "DISTRIBUIDORA SERRA AZUL LTDA",
    "CNPJ 00.000.000/0001-00  IE 000.000.000",
    "PEDIDO DE VENDA No 018447     EMISSAO 13/10/2026",
    "CLIENTE: RESTAURANTE EXEMPLO ME",
]

COLUNAS = ("DESCRICAO DO PRODUTO", "UN", "QTD", "VL.UNIT", "VL.TOTAL")

ITENS = [
    ("REFRIGERANTE COLA CX 12X1L", "CX", "4", "89,90", "359,60"),
    ("OLEO DE SOJA CX 20X900ML", "CX", "2", "118,00", "236,00"),
    ("QUEIJO MUSSARELA FATIADO", "KG", "12,500", "38,90", "486,25"),
    ("BACON EM MANTA DEFUMADO", "KG", "8,200", "27,50", "225,50"),
    ("BATATA PRE-FRITA CONG PCT 2,5KG", "PC", "10", "31,40", "314,00"),
    ("PAO BRIOCHE BURGER PCT C/ 12", "PC", "15", "14,20", "213,00"),
    ("ALFACE AMERICANA UNIDADE", "UN", "24", "4,30", "103,20"),
    ("TOMATE SALADA CAIXA 20KG", "CX", "1", "96,00", "96,00"),
    ("MOLHO BARBECUE GALAO 3,2KG", "UN", "3", "42,75", "128,25"),
    ("PAPEL TOALHA FD 6X2 ROLOS", "FD", "5", "33,60", "168,00"),
]


def desenhar() -> Image.Image:
    img = Image.new("RGB", (1240, 760), "white")
    d = ImageDraw.Draw(img)
    mono = ImageFont.truetype(MONO, 21)
    bold = ImageFont.truetype(BOLD, 23)

    y = 48
    for i, linha in enumerate(CABECALHO):
        d.text((60, y), linha, font=bold if i == 0 else mono, fill="black")
        y += 34

    y += 18
    d.line((60, y, 1180, y), fill="black", width=2)
    y += 12
    x = (60, 700, 780, 910, 1050)
    for pos, titulo in zip(x, COLUNAS):
        d.text((pos, y), titulo, font=bold, fill="black")
    y += 32
    d.line((60, y, 1180, y), fill="black", width=1)
    y += 14

    for item in ITENS:
        for pos, campo in zip(x, item):
            d.text((pos, y), campo, font=mono, fill="black")
        y += 32

    y += 10
    d.line((60, y, 1180, y), fill="black", width=2)
    y += 16
    d.text((700, y), "TOTAL DOS PRODUTOS", font=bold, fill="black")
    d.text((1050, y), "2.329,80", font=bold, fill="black")
    y += 44
    d.text((60, y), "FRETE CIF  -  PRAZO 28 DDL  -  VENDEDOR 07", font=mono, fill="black")
    return img


def envelhecer(img: Image.Image, seed: int = 7) -> Image.Image:
    """Deixa com cara de foto de celular: tortinha, sombra e granulado."""
    random.seed(seed)
    moldura = Image.new("RGB", (img.size[0] + 120, img.size[1] + 120), "white")
    moldura.paste(img, (60, 60))
    img = moldura.rotate(-1.4, resample=Image.BICUBIC, expand=True, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    # Luz de teto entrando por um canto: escurece de leve, sem apagar texto.
    sombra = Image.linear_gradient("L").rotate(
        -25, resample=Image.BICUBIC
    ).resize(img.size).point(lambda v: 150 + v // 3)
    img = Image.composite(img, Image.new("RGB", img.size, (196, 194, 188)), sombra)
    px = img.load()
    for _ in range(img.size[0] * img.size[1] // 90):
        cx, cy = random.randrange(img.size[0]), random.randrange(img.size[1])
        r, g, b = px[cx, cy]
        ruido = random.randint(-16, 16)
        px[cx, cy] = (
            max(0, min(255, r + ruido)),
            max(0, min(255, g + ruido)),
            max(0, min(255, b + ruido)),
        )
    return img


if __name__ == "__main__":
    destino = AQUI / "nota-fornecedor.jpg"
    envelhecer(desenhar()).save(destino, quality=78)
    print(destino)
