"""Interface de arrastar-e-soltar. Só biblioteca padrão, roda em localhost.

    python3 -m notinha.server      ->  http://localhost:8777
"""

import html
import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .export import br, escrever_csv
from .extract import MODEL
from .pipeline import processar

PORTA = 8777

PAGINA = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Notinha</title><style>
:root{color-scheme:light dark;--bg:#faf8f4;--fg:#1b1a17;--linha:#e2ddd2;--acento:#b4541f}
@media(prefers-color-scheme:dark){:root{--bg:#171613;--fg:#efece4;--linha:#32302a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.5 ui-sans-serif,system-ui,sans-serif;padding:24px}
main{max-width:860px;margin:0 auto}h1{font-size:1.4rem;margin:0 0 4px}
p.sub{margin:0 0 24px;opacity:.7;font-size:.9rem}
#solta{border:2px dashed var(--linha);border-radius:14px;padding:48px 16px;text-align:center;cursor:pointer}
#solta.ativo{border-color:var(--acento);background:color-mix(in srgb,var(--acento) 8%,transparent)}
table{width:100%;border-collapse:collapse;margin-top:24px;font-size:.88rem}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--linha)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.alerta{color:var(--acento);font-size:.8rem}
.nota{opacity:.65;font-size:.8rem}
a.baixar{display:inline-block;margin-top:18px;background:var(--acento);color:#fff;
text-decoration:none;padding:10px 18px;border-radius:9px;font-weight:600}
</style><main>
<h1>Notinha</h1>
<p class="sub">Foto da nota do fornecedor &rarr; planilha de custo. Roda em __MODEL__ na sua máquina; nada sai daqui.</p>
<div id="solta">Arraste a foto ou o PDF da nota, ou clique aqui
<input id="arq" type="file" accept="image/*,.pdf" hidden></div>
<div id="saida"></div></main><script>
const solta=document.getElementById('solta'),arq=document.getElementById('arq'),saida=document.getElementById('saida');
solta.onclick=()=>arq.click();
solta.ondragover=e=>{e.preventDefault();solta.classList.add('ativo')};
solta.ondragleave=()=>solta.classList.remove('ativo');
solta.ondrop=e=>{e.preventDefault();solta.classList.remove('ativo');enviar(e.dataTransfer.files[0])};
arq.onchange=()=>enviar(arq.files[0]);
async function enviar(f){if(!f)return;
 solta.textContent='lendo '+f.name+'... (uns 2 min num notebook sem placa de vídeo)';saida.innerHTML='';
 const r=await fetch('/ler?nome='+encodeURIComponent(f.name),{method:'POST',body:f});
 solta.textContent='Arraste outra nota';
 if(!r.ok){saida.innerHTML='<p class="alerta">'+await r.text()+'</p>';return}
 saida.innerHTML=await r.text();}
</script></html>"""


def _tabela(nota: dict, csv_b64: str) -> str:
    linhas = []
    for item in nota["itens"]:
        marca = ""
        if item["alertas"]:
            marca = f'<div class="alerta">⚠ {html.escape("; ".join(item["alertas"]))}</div>'
        elif item.get("notas"):
            marca = f'<div class="nota">↻ {html.escape("; ".join(item["notas"]))}</div>'
        linhas.append(
            f'<tr><td>{html.escape(item["descricao"])}{marca}</td>'
            f'<td class="n">{br(item["quantidade"])} {item["unidade"]}</td>'
            f'<td class="n">{br(item["valor_unitario"])}</td>'
            f'<td class="n">{br(item["custo_unidade_uso"])}/{item["unidade_uso"]}</td></tr>'
        )
    cabecalho = (
        f'<p><b>{html.escape(nota["fornecedor"] or "fornecedor não lido")}</b> · '
        f'{html.escape(nota["documento"] or "—")} · {html.escape(nota["data"] or "—")} · '
        f'{len(nota["itens"])} itens · total R$ {br(nota["total_itens"])}</p>'
    )
    return (
        cabecalho
        + '<table><tr><th>Item</th><th class="n">Qtd</th>'
        '<th class="n">Unit.</th><th class="n">Custo de uso</th></tr>'
        + "".join(linhas)
        + "</table>"
        + f'<a class="baixar" download="estoque.csv" '
        f'href="data:text/csv;base64,{csv_b64}">Baixar CSV para importar</a>'
    )


class Handler(BaseHTTPRequestHandler):
    def _responder(self, corpo: str, status=200, tipo="text/html; charset=utf-8"):
        dados = corpo.encode()
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path != "/":
            return self._responder("não achei", 404, "text/plain; charset=utf-8")
        self._responder(PAGINA.replace("__MODEL__", html.escape(MODEL)))

    def do_POST(self):
        import base64
        from urllib.parse import parse_qs, urlparse

        nome = (parse_qs(urlparse(self.path).query).get("nome") or ["nota.jpg"])[0]
        bruto = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not bruto:
            return self._responder("arquivo vazio", 400, "text/plain; charset=utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / Path(nome).name
            caminho.write_bytes(bruto)
            try:
                nota = processar(caminho)
            except Exception as erro:
                return self._responder(
                    f"não consegui ler: {erro}", 500, "text/plain; charset=utf-8"
                )
            destino = Path(tmp) / "estoque.csv"
            escrever_csv(nota, destino)
            csv_b64 = base64.b64encode(destino.read_bytes()).decode()
        self._responder(_tabela(nota, csv_b64))

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    print(f"Notinha em http://localhost:{PORTA}  (modelo {MODEL}, tudo local)")
    ThreadingHTTPServer(("127.0.0.1", PORTA), Handler).serve_forever()
