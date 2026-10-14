"""notinha nota.jpg -o estoque.csv"""

import argparse
import json
import sys
from pathlib import Path

from .export import escrever_csv, relatorio
from .extract import MODEL
from .pipeline import processar


def main(argv=None):
    p = argparse.ArgumentParser(prog="notinha", description=__doc__)
    p.add_argument("nota", help="foto ou PDF da nota do fornecedor")
    p.add_argument("-o", "--saida", help="caminho do CSV (padrão: ao lado da nota)")
    p.add_argument("--json", action="store_true", help="imprime o JSON cru e sai")
    p.add_argument("--sem-reparo", action="store_true",
                   help="não relê as linhas que falham na conferência")
    args = p.parse_args(argv)

    origem = Path(args.nota)
    if not origem.exists():
        p.error(f"não achei {origem}")

    print(f"lendo {origem.name} com {MODEL} (local)...", file=sys.stderr)
    nota = processar(origem, reparar=not args.sem_reparo)

    if args.json:
        print(json.dumps(nota, ensure_ascii=False, indent=2, default=str))
        return 0

    saida = Path(args.saida) if args.saida else origem.with_suffix(".csv")
    escrever_csv(nota, saida)
    print(relatorio(nota))
    print(f"\nCSV: {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
