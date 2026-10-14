---
title: "The invoice on the counter: a local-first cost reader for small restaurants"
published: true
tags: hf26challenge, ai, opensource, python
---


*This is a submission for the [Hacktoberfest Open-Source AI Challenge: Week 2](https://dev.to/challenges/hf26), Side Hustle theme.*

## What I Built

**Notinha** turns a phone photo of a supplier invoice into a cost spreadsheet a restaurant can actually import. It runs entirely on the owner's laptop — Gemma 3 through Ollama, no API key, no upload, no per-invoice cost.

I work on point-of-sale software for Brazilian restaurants, so I have watched this specific chore happen a lot. The supplier delivers, hands over a paper invoice, and somebody types it into a spreadsheet line by line. Every week. The owner of a 12-table burger place does this at 11pm, after close, because nobody else will.

And the number they actually need is never the number on the paper.

The invoice says **R$ 89,90 per case**. The recipe card needs **R$ 7,49 per litre**. The invoice says `FD 6X2 ROLOS`; the stock count is in rolls. Between the paper and the decision — *is this burger still making money?* — there is a unit conversion that a human does in their head, badly, at 11pm.

So Notinha does two things, and the second one is the product:

1. Read the table off the photo.
2. Convert closed packaging into the unit the kitchen counts in.

```
$ notinha nota-do-fornecedor.jpg
lendo nota-do-fornecedor.jpg com gemma3:4b (local)...

Fornecedor: SERRA AZUL LTDA   Doc: PEDIDO DE VENDA No 018447   Data: 13/10/2026
10 itens · total lido R$ 2329,8

ITEM                                    QTD        UNIT     CUSTO USO
REFRIGERANTE COLA CX 12X1L                4        89,9       7,492/L
OLEO DE SOJA CX 20X900ML                  2         118       6,556/L
QUEIJO MUSSARELA FATIADO               12,5        38,9       38,9/KG
                                 ↻ unitário relido (38,9); quantidade calculada: 486,25 ÷ 38,9
BACON EM MENTA DEFUMADO                 8,2        27,5       27,5/KG
BATATA PRE-FRITA CONG PCT 2.5KG          10        31,4       31,4/UN
PAO BRIOCHE BURGER PCT C/ 12             15        14,2       14,2/UN
ALFACE AMERICANA UNIDADE                 24         4,3        4,3/UN
TOMATE SALADA CAIXA 20KG                  1          96        4,8/KG
MOLHO BARBECUE GALAO 3.2KG                3       42,75      42,75/UN
PAPEL TOALHA FD 6X2 ROLOS                 5        33,6        2,8/UN

CSV: nota-do-fornecedor.csv
```

That last column is the whole point. `CX 12X1L` at R$ 89,90 became R$ 7,49 per litre. `FD 6X2 ROLOS` at R$ 33,60 became R$ 2,80 per roll. Nobody did arithmetic at 11pm.

The `↻` on the cheese line is the interesting part. The model read that row wrong, the arithmetic caught it, a second look fixed it, and the mark tells you which number was reconciled rather than copied. More on that below — it is most of the engineering.

There is also a drag-and-drop page on `localhost:8777`, because the person who owns the restaurant is not going to open a terminal.

## Demo

![Notinha reading a supplier invoice in the browser: ten line items, the cheese line flagged in orange, and a button to download the import CSV](https://raw.githubusercontent.com/Tinhomagri/notinha/master/docs/notinha-ui.png)

The grey `↻` line is the one the first pass read wrong and the second pass recovered. Anything the second pass *cannot* recover stays orange and reaches the CSV with its numbers blank.

Repository: **https://github.com/Tinhomagri/notinha**

Try it on synthetic data — no real invoice needed, and no real CNPJ, supplier or price anywhere in the repo:

```bash
ollama pull gemma3:4b
pip install -e .
python3 samples/make_sample.py
notinha samples/nota-fornecedor.jpg
```

`make_sample.py` draws an invoice and then *ruins* it on purpose: tilts it, drops a light gradient across it, adds sensor grain. A clean render would have told me nothing.

## How I Used Open Models

The stack is `gemma3:4b` served by Ollama, called over plain HTTP with a JSON Schema. Around 590 lines of Python — 455 of them the reading pipeline, the rest the drag-and-drop page — and one dependency (`requests`).

**Structured output is doing real work here.** Ollama lets you hand `/api/chat` a JSON Schema in `format`, and the model is constrained to produce conforming JSON. No "respond only with JSON" in the prompt, no regex over a markdown fence.

One detail cost me a run to find. Every numeric field in my schema is typed `string`:

```python
"valor_unitario": {"type": "string"},
```

Brazilian invoices write one thousand two hundred thirty-four and fifty-six cents as `1.234,56`. Let that be a JSON `number` and the parser reads `1.234` — a thousandfold error, silently, with no exception anywhere. So the model copies the glyphs and my code owns the parsing:

```python
if "," in limpo:
    # comma is the decimal: a dot can only be a thousands separator
    limpo = limpo.replace(".", "").replace(",", ".")
```

The prompt is also explicit that the model must not compute anything — just transcribe. Arithmetic is the one thing I can do perfectly and it cannot.

### The check that makes it usable

A 4B model reading a tilted photo under kitchen lighting *will* misread a digit. It reads `12,500 × 38,90` in the cheese row as quantity `2`, unit price `12,5` — and it does so on every run, so this is not bad luck I can retry away.

The fix is not a better prompt. It is that an invoice line is over-determined: quantity × unit price = line total. Three numbers, one constraint. So:

```python
if quantidade and unitario and total:
    esperado = (quantidade * unitario).quantize(CENTAVO)
    if abs(esperado - total) > max(CENTAVO, total * Decimal("0.01")):
        item["alertas"].append(f"qtd x unitário = {esperado}, nota diz {total}")
```

That misread line came out flagged: `⚠ qtd x unitário = 25.00, nota diz 486.25`. The error was caught by arithmetic, not by the model noticing.

The same redundancy repairs crushed invoices: if a photo loses the unit-price column to a glare, any two of the three numbers reconstruct the third.

### Spending inference only where verification failed

Flagging was where I stopped at first. Then I looked at *why* the model misses that row, and the answer suggested the fix.

The failure is not that the model cannot read `12,500`. It is that it is reading a ten-row table in one pass, and the description column sits far to the left of the numeric columns. Row alignment is what breaks, not glyph recognition.

So the repair is a second look with a narrower question. For each flagged line — and only those — the line goes back to the model on its own, anchored by the one number I already trust:

```
Na nota da imagem, ache a linha do produto "QUEIJO MUSSARELA FATIADO".
Essa linha tem valor total 486,25. Olhe só para ela e devolva a quantidade,
a unidade e o valor unitário, copiados exatamente como estão escritos.
Atenção à coluna QTD: números como 12,500 são um só valor, não dois.
```

The focused read returns `quantidade: 2, valor_unitario: 38,90`. Still wrong on the quantity — but it now disagrees with the first pass on the **unit price**, and 486,25 ÷ 38,90 is exactly 12,5. Two of the three numbers are solid, so the third follows.

That last step needs a guard, because `(12,5 × 38,90)` and `(38,9 × 12,50)` both equal 486,25 — the identity alone cannot tell you which column is which. The tiebreaker is that a *focused* read does not suffer the alignment failure that a *table-wide* read does, so I take the new unit price only when it disagrees with the first pass, and derive the quantity from it. If anything in that chain fails, the line stays flagged.

```python
# 1st choice: the re-read closes the arithmetic on its own.
candidato = normalizar_item({**base, "quantidade": relido.get("quantidade")})
if not candidato["alertas"]:
    ...
# 2nd choice: keep the re-read unit price, derive quantity from the total.
if unitario_novo is None or unitario_novo == item["valor_unitario"]:
    continue
```

The derived number is not presented as if it had been read off the paper. It carries `↻ unitário relido (38,9); quantidade calculada: 486,25 ÷ 38,9` through the terminal, the web page and the CSV, so you can see which numbers were transcribed and which were reconciled.

One invoice costs ~1m40s. One flagged line costs ~45s more. Nothing is re-read that passed.

This reframed the product for me. The promise is not *the model always reads correctly*. It is **what it gets wrong is caught, and then either repaired in the open or handed to you marked**. A tool that is right 95% of the time and silent about the other 5% is useless for money.

### Vocabulary nobody else will maintain

`FD`, `PÇ`, `SC`, `C/ 12`, `DZ` are Brazilian wholesale distributor shorthand. No general-purpose vision API is going to carry a dictionary for it. Mine is 20 lines and I edit it when a customer's supplier invents a new abbreviation:

```python
UNIDADE_CANONICA = {
    "KG": "KG", "CX": "CX", "FD": "FD", "PC": "UN", "SC": "SC", ...
}
```

Plus a regex that pulls `12X1L` out of a description and divides the case price by 12 litres.

### Honest numbers

On a 15 GB laptop with **no GPU**, `gemma3:4b` reads a one-page invoice in **~1m40s**. That is slow for a chatbot and completely fine for a thing you run once per delivery while you put the boxes away.

Accuracy, measured rather than asserted. Runs at `temperature: 0` over the same photo produce **byte-identical CSVs** (same md5), so the failures are reproducible rather than a lottery — which is the only reason the numbers below mean anything. Against the known ground truth of that invoice:

| | first pass only (`--sem-reparo`) | with the repair pass |
|---|---|---|
| Items found | 10 / 10 | 10 / 10 |
| Supplier, document number, date | correct | correct |
| Invoice total reconstructed | R$ 2.329,80 — exact | R$ 2.329,80 — exact |
| Numeric lines fully correct | 9 / 10 | **10 / 10** |
| `QUEIJO MUSSARELA` (`12,500 × 38,90`) | read as `2 × 12,5` — flagged | recovered, marked `↻` |
| Description typos | 1 — `MANTA` read as `MENTA` | 1 — unchanged |
| Time | ~1m40s | ~2m20s |

The spelling error survives both passes, and that is correct behaviour rather than a gap I failed to close. It does not touch a number, so no arithmetic can see it — and it does not need to. A misspelt item name costs you a rename. A wrong unit cost gets baked into every burger you sell. The verification layer is aimed at money, not at tidiness.

When the second pass cannot close the gap either, the line reaches the CSV with its **quantity and cost columns empty** and the reason written into the description field:

```
ITEM ILEGIVEL;insumo;KG;;;CONFERIR (qtd x unitário = 25.00, nota diz 486.25) — ...;;;;;
```

The importer refuses that row, the human looks at that one line, and the rest go in untouched. Half an automated invoice beats a wrong one.

## Why Open Innovation Matters Here

Four reasons, in the order a restaurant owner would care.

**The invoice is a tax document.** It carries the supplier's CNPJ, the negotiated price, and by implication the supplier's margin. "Where does this go?" is the first question I get, and "nowhere, it stays on this machine" is an answer that ends the conversation. With a hosted API, the honest answer is a paragraph about data processing agreements, and I lose the sale.

**Per-invoice cost is zero.** A small restaurant receives 15–40 invoices a month. On a metered API my cost scales with my customer's volume, which means either I price for the heaviest user or I watch margin erode on them. Running local, a busy month costs me nothing, so I can charge a flat monthly fee — which is the only pricing a restaurant owner will agree to.

**It works in the stockroom.** Receiving happens at the back door, with the phone on one bar of signal and both hands full.

**The dictionary is mine.** `FD 6X2 ROLOS` is not a problem a general model will ever prioritise. It is a 20-line dict I edit the same afternoon a customer complains.

What I did not get for free: a 4B model on CPU is slower and shakier than a frontier API would be, and I paid for that with the verification layer. That trade was worth it — but it *was* a trade, and the verification layer is most of the engineering.

## What's Next

Not shipped yet, and I am not going to pretend otherwise: **it has not been in front of a real restaurant owner yet.** Every number in this post comes from synthetic invoices I generated and degraded on purpose, run on my own machine. The real test is a stack of crumpled paper from an actual delivery, and that is the next thing, not a finished thing.

The repair pass also has an obvious next move I did not take: right now it re-reads the whole page image for one line, because I never know where on the paper that line is. Cropping to the row first would make it faster and probably more accurate, and it needs bounding boxes the current prompt does not ask for.

After that: reading NF-e XML when the supplier sends one (exact beats inferred, always), and tracking the same item across months so the tool can say *this went up 9% since August* — which is the question underneath the whole chore.

---

Built with Claude Code. Code is MIT.
