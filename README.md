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
QUEIJO MUSSARELA FATIADO               12,5        38,9       38,9/KG
                                 ↻ unitário relido (38,9); quantidade calculada: 486,25 ÷ 38,9
PAPEL TOALHA FD 6X2 ROLOS                 5        33,6        2,8/UN
...
CSV: nota-do-fornecedor.csv
```

A linha do queijo saiu errada na primeira leitura. A conferência aritmética
pegou, a segunda leitura consertou, e o `↻` conta de onde veio cada número.
O que a segunda leitura **não** conserta continua marcado e vai pro CSV sem
quantidade e sem custo: o importador recusa aquela linha, as outras entram.

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
4. **Reparo** (`pipeline.py`): só as linhas marcadas voltam pro modelo, uma de
   cada vez, com o total da linha como âncora. Leitura focada não sofre o
   desalinhamento de coluna que derruba a leitura da tabela inteira. Se a
   segunda leitura fecha a conta, substitui; se não fecha, a linha continua
   marcada. Nada de reler a nota toda: inferência só onde a verificação falhou.
5. **Saída** (`export.py`): CSV no layout de importação de estoque do PDV.

Os passos 3 e 4 são o que torna a ferramenta usável. Modelo pequeno lendo foto
torta erra dígito — e quando erra, a aritmética da linha denuncia e a releitura
costuma consertar. O produto não é "o modelo acerta sempre": é "o que ele erra
chega consertado ou marcado, nunca calado".

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
notinha nota.jpg --sem-reparo      # só a primeira leitura, sem reler linha marcada
python3 -m notinha.server         # interface de arrastar-e-soltar em :8777
```

Trocar de modelo é variável de ambiente:

```bash
NOTINHA_MODEL=gemma3:12b notinha nota.jpg
```

## Limites conhecidos

- Testado com `gemma3:4b` em CPU: ~1min40 por página num notebook de 15 GB sem
  placa de vídeo, mais ~45s por linha que precisa de releitura. Com GPU ou com
  o `12b` fica melhor nos dois sentidos.
- A releitura troca o número só quando a conta fecha E quando ela discorda da
  primeira leitura. Ainda assim é inferência: o `↻` no relatório existe pra
  você ver que aquele número foi reconciliado, não copiado do papel.
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
