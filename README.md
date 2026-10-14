# Notinha

[Post no DEV](https://dev.to/wellington_filipe_fccda4c/the-invoice-on-the-counter-a-local-first-cost-reader-for-small-restaurants-3bo) · Hacktoberfest Open-Source AI Challenge 2026, Week 2

Foto da nota do fornecedor vira planilha de custo de insumos. Roda inteiro na sua
máquina, com modelo aberto. A nota não sobe para lugar nenhum.

```
notinha nota-do-fornecedor.jpg
```

```
Fornecedor: SERRA AZUL LTDA   Doc: 018447   Data: 13/10/2026
10 itens · total lido R$ 2329,80

ITEM                                    QTD        UNIT     CUSTO USO
REFRIGERANTE COLA CX 12X1L                4        89,9       7,492/L
OLEO DE SOJA CX 20X900ML                  2         118       6,556/L
QUEIJO MUSSARELA FATIADO                  2        12,5       12,5/KG
                                 ⚠ qtd x unitário = 25.00, nota diz 486.25
PAPEL TOALHA FD 6X2 ROLOS                 5        33,6        2,8/UN
...
⚠ 1 item(ns) pedem conferência.

CSV: nota-do-fornecedor.csv
```

A linha marcada vai pro CSV **sem quantidade e sem custo**, com o motivo na
descrição. O importador recusa aquela linha; as outras entram.

## O problema

Dono de restaurante pequeno recebe nota de fornecedor em papel. Pra saber se o
hambúrguer ainda dá margem, alguém digita item por item numa planilha toda semana.
E a conta que importa nunca está na nota: a nota diz **R$ 89,90 a caixa**, a ficha
técnica precisa de **R$ 7,49 o litro**.

O Notinha faz as duas coisas: lê a tabela e converte embalagem fechada
(`CX 12X1L`, `FD 6X2 ROLOS`, `PCT 2,5KG`) para a unidade que a cozinha usa.

## Por que local, e não uma API

- **A nota é documento fiscal.** Tem CNPJ, preço negociado e a margem do
  fornecedor. Mandar isso pro servidor de terceiro é um problema do cliente, não
  meu — e some como objeção de venda quando nada sai da máquina dele.
- **Custo por nota: zero.** Um restaurante recebe de 15 a 40 notas por mês. Com
  API por token, o preço do produto acompanha o volume do cliente. Local, não.
- **Funciona no depósito sem sinal.** Conferência de mercadoria é no estoque.
- **O vocabulário é meu.** `FD`, `PÇ`, `C/ 12`, `SC` não são universais — são
  siglas de distribuidor brasileiro, e estão num dicionário que dá pra editar
  (`notinha/normalize.py`) sem pedir licença pra ninguém.

## Como funciona

1. **Leitura** (`extract.py`): a imagem vai pro `gemma3:4b` via Ollama com
   *structured output* — um JSON Schema que obriga a resposta a ter os campos
   certos. Números saem como **string** de propósito: o modelo escreve `1.234,56`
   e qualquer coerção pra `number` do JSON vira `1.234` em silêncio.
2. **Normalização** (`normalize.py`): converte número pt-BR, canoniza a sigla da
   unidade, decompõe a embalagem e calcula o custo por unidade de uso.
3. **Conferência**: `qtd × unitário` tem que bater com o total da linha. Quando
   não bate, a linha sai marcada em vez de entrar calada na planilha.
4. **Saída** (`export.py`): CSV no layout de importação de estoque do PDV.

O passo 3 é o que torna a ferramenta usável. Modelo pequeno lendo foto torta
erra dígito de vez em quando — e quando erra, a aritmética da linha denuncia.
O produto não é "o modelo acerta sempre": é "o que ele erra chega marcado".

## Instalação

Precisa de [Ollama](https://ollama.com) e Python 3.10+.

```bash
ollama pull gemma3:4b
pip install -e .
```

PDF precisa de `pdftoppm` (pacote `poppler-utils`).

## Uso

```bash
notinha nota.jpg                  # CSV ao lado da nota + relatório no terminal
notinha nota.pdf -o estoque.csv   # escolhendo o destino
notinha nota.jpg --json           # JSON cru, pra plugar em outra coisa
python3 -m notinha.server         # interface de arrastar-e-soltar em :8777
```

Trocar de modelo é variável de ambiente:

```bash
NOTINHA_MODEL=gemma3:12b notinha nota.jpg
```

## Limites conhecidos

- Testado com `gemma3:4b` em CPU: ~1min40 por página num notebook de 15 GB sem
  placa de vídeo. Com GPU ou com o `12b` fica melhor nos dois sentidos.
- Nota muito amassada, foto com flash estourado ou tabela de duas colunas por
  página ainda confundem a leitura. A conferência aritmética marca boa parte,
  não tudo: **confira o CSV antes de importar.**
- Não lê XML de NF-e. Se o fornecedor te manda XML, você não precisa disto — leia
  o XML, é exato.
- Sem suporte a nota de serviço, boleto ou cupom fiscal.

## Testando sem expor cliente

`samples/make_sample.py` gera uma nota sintética (nenhum CNPJ, nome ou preço real)
já com cara de foto de celular: tortinha, luz de lado e granulado.

```bash
python3 samples/make_sample.py && notinha samples/nota-fornecedor.jpg
```

## Licença

MIT.
