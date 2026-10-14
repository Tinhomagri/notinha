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
QUEIJO MUSSARELA FATIADO                  2        12,5       12,5/KG
                                 ⚠ qtd x unitário = 25.00, nota diz 486.25
BACON EM MENTA DEFUMADO                 8,2        27,5       27,5/KG
BATATA PRE-FRITA CONG PCT 2.5KG          10        31,4       31,4/UN
PAO BRIOCHE BURGER PCT C/ 12             15        14,2       14,2/UN
ALFACE AMERICANA UNIDADE                 24         4,3        4,3/UN
TOMATE SALADA CAIXA 20KG                  1          96        4,8/KG
MOLHO BARBECUE GALAO 3.2KG                3       42,75      42,75/UN
PAPEL TOALHA FD 6X2 ROLOS                 5        33,6        2,8/UN

⚠ 1 item(ns) pedem conferência.

CSV: nota-do-fornecedor.csv
```

That last column is the whole point. `CX 12X1L` at R$ 89,90 became R$ 7,49 per litre. `FD 6X2 ROLOS` at R$ 33,60 became R$ 2,80 per roll. Nobody did arithmetic at 11pm.

And that warning on the cheese line is not me being modest about the demo. It is the feature. More on it below.

There is also a drag-and-drop page on `localhost:8777`, because the person who owns the restaurant is not going to open a terminal.

## Demo

![Notinha reading a supplier invoice in the browser: ten line items, the cheese line flagged in orange, and a button to download the import CSV](https://raw.githubusercontent.com/Tinhomagri/notinha/master/docs/notinha-ui.png)

The orange line is the one the model got wrong. It is the only line that does not reach the spreadsheet.

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

The stack is `gemma3:4b` served by Ollama, called over plain HTTP with a JSON Schema. About 240 lines of Python and one dependency (`requests`).

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

This reframed the product for me. The promise is not *the model always reads correctly*. It is **what it gets wrong arrives marked**. A tool that is right 95% of the time and silent about the other 5% is useless for money. A tool that is right 95% of the time and points at the remaining 5% saves the whole evening.

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

Accuracy, measured rather than asserted. Three runs over the same photo at
`temperature: 0` produced **byte-identical CSVs** (same md5), so the failures are
reproducible rather than a lottery. Against the known ground truth of that
invoice:

| | result |
|---|---|
| Items found | 10 / 10 |
| Supplier, document number, date | correct |
| Invoice total reconstructed | R$ 2.329,80 — exact |
| Numeric lines fully correct | 9 / 10 |
| The wrong one | `QUEIJO MUSSARELA`: read `12,500 × 38,90` as `2 × 12,5` — **flagged** |
| Description typos | 1 — `MANTA` read as `MENTA`, **not** flagged |

Two different failures, and the difference matters. The quantity error breaks
the arithmetic, so the check catches it. The spelling error does not touch any
number, so nothing catches it — and nothing should: a misspelt item name costs
you a rename, a wrong unit cost gets baked into every burger you sell.

A flagged line reaches the CSV with its **quantity and cost columns empty** and
the reason written into the description field:

```
QUEIJO MUSSARELA FATIADO;insumo;KG;;;CONFERIR (qtd x unitário = 25.00, nota diz 486.25) — ...;;;;;
```

The importer refuses it, the human looks at that one line, and the other nine
go in untouched. Half an automated invoice beats a wrong one.

## Why Open Innovation Matters Here

Four reasons, in the order a restaurant owner would care.

**The invoice is a tax document.** It carries the supplier's CNPJ, the negotiated price, and by implication the supplier's margin. "Where does this go?" is the first question I get, and "nowhere, it stays on this machine" is an answer that ends the conversation. With a hosted API, the honest answer is a paragraph about data processing agreements, and I lose the sale.

**Per-invoice cost is zero.** A small restaurant receives 15–40 invoices a month. On a metered API my cost scales with my customer's volume, which means either I price for the heaviest user or I watch margin erode on them. Running local, a busy month costs me nothing, so I can charge a flat monthly fee — which is the only pricing a restaurant owner will agree to.

**It works in the stockroom.** Receiving happens at the back door, with the phone on one bar of signal and both hands full.

**The dictionary is mine.** `FD 6X2 ROLOS` is not a problem a general model will ever prioritise. It is a 20-line dict I edit the same afternoon a customer complains.

What I did not get for free: a 4B model on CPU is slower and shakier than a frontier API would be, and I paid for that with the verification layer. That trade was worth it — but it *was* a trade, and the verification layer is most of the engineering.

## What's Next

Not shipped yet, and I am not going to pretend otherwise: **it has not been in front of a real restaurant owner yet.** Every number in this post comes from synthetic invoices I generated and degraded on purpose, run on my own machine. The real test is a stack of crumpled paper from an actual delivery, and that is the next thing, not a finished thing.

After that: reading NF-e XML when the supplier sends one (exact beats inferred, always), and tracking the same item across months so the tool can say *this went up 9% since August* — which is the question underneath the whole chore.

---

Built with Claude Code. Code is MIT.
