"""
Geração do site: uma página por dia com a grade de quadros, mais um índice
com o histórico. Sem dependências — só string formatting.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path

# as mesmas quatro cores de método do aplicativo (--m1 a --m4)
CORES = {"BACK_FAV": "#4C7EF3", "LAY_ZEBRA": "#A97BF0", "OVER": "#25B49B", "BACK22": "#E0A02F"}
FAIXAS_ROT = ["0–15'", "16–30'", "31–45'", "46–60'", "61–75'", "76–90'"]


def sem_tags(s):
    """A motivação vem com marcação; na capa ela entra como texto puro."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s or ""))).strip()


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def _slug(s):
    """Pedaço de nome de arquivo: sem acento, sem espaço, sem caractere proibido."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Za-z0-9]+", "", s) or "Time"


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def f2(v, casas=2):
    return "—" if v is None else f"{v:.{casas}f}"


def pc(v, casas=0):
    return "—" if v is None else f"{v*100:.{casas}f}%"


# Mesma identidade visual do aplicativo (mesa-analise-trading.html): tema escuro,
# as mesmas variáveis de cor, o mesmo quadro quadrado com 4 por linha.
CSS = """
:root{
  --bg:#0E1116; --panel:#151A21; --panel2:#1B222B; --line:#28313D;
  --tx:#E7ECF3; --tx2:#94A1B2; --tx3:#66707E;
  --pos:#34C48A; --neg:#EF5F5F; --warn:#E0A02F;
  --m1:#4C7EF3; --m2:#A97BF0; --m3:#25B49B; --m4:#E0A02F;
  --r:10px;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--tx);-webkit-font-smoothing:antialiased;
  font:14px/1.5 "Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--m1)}
h1,h2,h3,h4{margin:0;font-weight:600;letter-spacing:-.01em}
button{font:inherit;cursor:pointer}

/* ---------- topo ---------- */
.topbar{position:sticky;top:0;z-index:50;background:rgba(14,17,22,.92);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.topbar-in{max-width:1680px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px}
.brand .dot{width:9px;height:9px;border-radius:50%;background:var(--pos);box-shadow:0 0 0 3px rgba(52,196,138,.15);flex:none}
.brand h1{font-size:15px}
.brand span{color:var(--tx3);font-size:11px;display:block;font-weight:400;letter-spacing:.04em;text-transform:uppercase}
.spacer{flex:1}
.pg{max-width:1680px;margin:0 auto;padding:20px 20px 60px}
.sub{color:var(--tx2);font-size:12.5px;line-height:1.55;margin-bottom:16px}

/* ---------- faixa de números ---------- */
.resumo{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:10px;margin-bottom:16px}
.resumo div{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:13px 15px}
.resumo div span{display:block;font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--tx3);font-weight:600}
.resumo div b{font-size:25px;font-weight:650;margin-top:5px;display:block;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.resumo div:nth-child(1){border-left:2px solid var(--m1)}
.resumo div:nth-child(2){border-left:2px solid var(--m2)}
.resumo div:nth-child(3){border-left:2px solid var(--m3)}
.resumo div:nth-child(4){border-left:2px solid var(--m4)}

.acoes{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.acoes button,.acoes a{background:var(--panel2);border:1px solid var(--line);border-radius:8px;
  padding:8px 13px;font-size:13px;font-weight:500;color:var(--tx);text-decoration:none;transition:.12s;
  display:inline-flex;align-items:center;gap:7px}
.acoes button:hover,.acoes a:hover{border-color:#3A4756;background:#212a35}
.acoes .spacer{flex:1}
.banca{display:inline-flex;align-items:center;gap:8px;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:.06em;color:var(--tx3)}
.banca .inp{width:110px;text-align:right;font-size:14px;font-weight:650;color:var(--tx);
  letter-spacing:0;text-transform:none;font-variant-numeric:tabular-nums}
.banca .btn-lim{background:transparent;border:1px solid var(--line);color:var(--tx3);
  border-radius:7px;padding:6px 9px;font-size:13px;line-height:1;transition:.12s}
.banca .btn-lim:hover{color:var(--tx);border-color:#3A4756}

/* ---------- filtros ---------- */
.filtros{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.chip{background:var(--panel);border:1px solid var(--line);color:var(--tx2);border-radius:20px;
  padding:6px 13px;font-size:12.5px;font-weight:500;transition:.12s;display:inline-flex;align-items:center;gap:7px}
.chip:hover{color:var(--tx);border-color:#3A4756}
.chip[aria-pressed="true"]{background:var(--panel2);color:var(--tx);border-color:#48566A}
.chip .sw{width:8px;height:8px;border-radius:2px;flex:none}
.chip .ct{font-size:10.5px;color:var(--tx3);font-weight:700}
.chip.lim{color:var(--tx3)}
.inp{background:var(--panel);border:1px solid var(--line);color:var(--tx);border-radius:8px;
  padding:7px 11px;font:inherit;font-size:12.5px}
.inp:focus{outline:0;border-color:var(--m1)}
select.inp{cursor:pointer}
.filtros .spacer{flex:1}
.filtros .conta{color:var(--tx3);font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}
.jogo.fora{display:none}
.vazio{text-align:center;padding:44px 20px;color:var(--tx3);font-size:13px;
  border:1px dashed var(--line);border-radius:12px}

/* ---------- grade de quadros ---------- */
.grade{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;align-items:stretch}
.jogo{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--c);
  border-radius:12px;overflow:hidden;page-break-inside:avoid;display:flex;flex-direction:column}
.jogo>summary{flex:1;display:flex;flex-direction:column;list-style:none;cursor:pointer}
.jogo>summary::-webkit-details-marker{display:none}
.jogo[open]{grid-column:1/-1}
.cap{display:flex;flex-direction:column;gap:7px;padding:11px 13px;flex:1}
/* o quadrado é o piso: com a motivação o card cresce, e a linha inteira acompanha */
.jogo:not([open]) .cap{aspect-ratio:1/1;justify-content:space-between}
.jogo[open] .cap{flex-direction:row;align-items:center;flex-wrap:wrap;gap:12px 22px;
  border-bottom:1px solid var(--line);background:rgba(255,255,255,.02)}
.cap:hover{background:rgba(255,255,255,.02)}
.c-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.c-hora{font-variant-numeric:tabular-nums;font-weight:700;color:var(--tx2);font-size:14px}
.c-jogo .t{display:flex;align-items:center;gap:7px;margin-bottom:3px}
.c-jogo .t b{font-size:13.5px;font-weight:650;line-height:1.25;min-width:0;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.esc{width:22px;height:22px;object-fit:contain;flex:none;vertical-align:middle}
.esc.vazio{width:22px;height:22px;border-radius:50%;background:var(--panel2);border:1px solid var(--line);
  color:var(--tx3);display:grid;place-items:center;font-size:11px;font-weight:800;flex:none}
.c-jogo small{display:block;color:var(--tx3);font-size:11px;margin-top:4px}
.c-motivo{margin:5px 0 0;font-size:11.5px;line-height:1.4;color:var(--tx2);
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
details[open] .c-motivo{display:none}
details[open] .c-jogo .t b{-webkit-line-clamp:none}
.c-merc .met{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--c)}
.c-merc b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  font-size:12.5px;font-weight:600;line-height:1.35;margin-top:2px}
.c-vals{border-top:1px solid var(--line);padding-top:6px}
.c-vals div{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:3px}
.c-vals span{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--tx3);font-weight:700}
.c-vals b{font-size:15px;font-variant-numeric:tabular-nums;white-space:nowrap}
.c-vals em{font-style:normal;font-size:12px;font-weight:600;color:var(--tx2)}
.badge{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.04em;padding:3px 8px;border-radius:20px;white-space:nowrap}
.badge.live{background:rgba(239,95,95,.12);color:#F58A8A;border:1px solid rgba(239,95,95,.3)}
.badge.pre{background:rgba(76,126,243,.12);color:#8FB0F7;border:1px solid rgba(76,126,243,.3)}
.c-abre{color:var(--tx3);font-size:11.5px;border-top:1px solid var(--line);padding-top:6px;
  display:flex;align-items:center;justify-content:space-between;gap:8px}
.c-abre .chev{display:inline-block;margin-left:2px;transition:transform .15s}
.c-img{background:transparent;border:1px solid var(--line);color:var(--tx2);border-radius:6px;
  padding:3px 9px;font-size:10.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;transition:.12s}
.c-img:hover{color:var(--tx);border-color:#3A4756;background:var(--panel2)}
details[open] .c-abre{border:0;padding:0;margin-left:auto}
details[open] .c-abre .chev{transform:rotate(180deg)}
details[open] .c-vals{border:0;padding:0;display:flex;gap:22px}
details[open] .c-vals div{margin:0;flex-direction:column;align-items:flex-start;gap:0}
details[open] .c-merc b{-webkit-line-clamp:none}

/* ---------- detalhe aberto ---------- */
.corpo{padding:16px;background:rgba(0,0,0,.16);
  display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:0 24px}
.corpo>.alerta,.corpo>.ok,.corpo>.neutro,.corpo>.notas{grid-column:1/-1}
.bl{padding:12px 0;border-bottom:1px solid rgba(40,49,61,.7);min-width:0}
.bl.wide{grid-column:1/-1}
.bl h4{margin:0 0 5px;font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--tx3);font-weight:700}
.bl>div{font-size:13px;line-height:1.6}
.bl b{color:#fff;font-weight:650}
.alerta{margin:0 0 10px;background:rgba(224,160,47,.07);border:1px solid rgba(224,160,47,.28);
  color:#E9C98A;border-radius:9px;padding:10px 13px;font-size:13px}
.alerta b{color:#FFD98A}
.ok{margin:0 0 10px;background:rgba(52,196,138,.08);border:1px solid rgba(52,196,138,.3);
  color:#8FE0BC;border-radius:9px;padding:10px 13px;font-size:13px}
.neutro{margin:0 0 10px;background:var(--panel2);border:1px solid var(--line);
  color:var(--tx2);border-radius:9px;padding:10px 13px;font-size:13px}
.live-l{display:flex;gap:10px;margin-bottom:6px;font-size:13px}
.live-l span{flex:none;width:92px;font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:700;padding-top:3px}
.seguir span{color:var(--pos)}
.descartar span{color:var(--neg)}
.notas{margin-top:12px;background:rgba(224,160,47,.07);border:1px solid rgba(224,160,47,.25);
  border-radius:9px;padding:11px 13px;font-size:12.5px;color:#E9C98A;line-height:1.6}
table.mini{width:100%;border-collapse:collapse;font-size:12.5px}
table.mini td{padding:4px 6px;border-bottom:1px solid rgba(40,49,61,.7)}
table.mini tr:last-child td{border-bottom:0}
table.mini td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.mini tr.dentro td{color:var(--pos);font-weight:600}
td.barra{width:45%}
td.barra i{display:block;height:5px;border-radius:3px;background:#2C3541}
tr.dentro td.barra i{background:var(--m3)}
.mono{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace;font-size:12px}
.mut{color:var(--tx3)}
.rodape{margin-top:24px;color:var(--tx3);font-size:12px;line-height:1.6}

/* ---------- advertências ---------- */
.legal{margin-top:18px;border:1px solid var(--line);border-left:3px solid var(--warn);
  border-radius:var(--r);background:rgba(224,160,47,.05);padding:14px 16px}
.legal-forte{font-size:13.5px;font-weight:700;color:#E9C98A;letter-spacing:.01em}
.legal-linha{margin-top:7px;font-size:12.5px;color:var(--tx2);display:flex;align-items:center;
  gap:9px;flex-wrap:wrap}
.legal .idade{display:inline-grid;place-items:center;min-width:34px;height:24px;padding:0 7px;
  border-radius:6px;background:#B3261E;color:#fff;font-size:12px;font-weight:800;letter-spacing:.02em}
.legal-nota{margin-top:9px;font-size:11.5px;line-height:1.65;color:var(--tx3)}
.legal-nota a{color:var(--tx2);text-decoration:underline}

/* ---------- índice de dias ---------- */
.dias{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
.dia{background:var(--panel);border:1px solid var(--line);border-left:2px solid var(--m1);
  border-radius:var(--r);padding:15px 17px;text-decoration:none;color:inherit;display:block;transition:.12s}
.dia:hover{border-color:#3A4756;border-left-color:var(--m1);background:var(--panel2)}
.dia b{display:block;font-size:19px;font-weight:650;margin-bottom:5px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.dia span{color:var(--tx2);font-size:12px}

@media (max-width:1400px){ .grade{grid-template-columns:repeat(3,minmax(0,1fr))} }
@media (max-width:1000px){ .grade{grid-template-columns:repeat(2,minmax(0,1fr))} }
@media (max-width:640px){ .grade{grid-template-columns:1fr} .jogo:not([open]) .cap{aspect-ratio:auto} }
@media print{
  body{background:#fff;color:#000}
  .topbar,.acoes,.filtros,.c-img{display:none!important}
  .pg{padding:0}
  .grade{display:block}
  .jogo{border-color:#ccc;background:#fff;margin-bottom:10px}
  .jogo:not([open]) .cap{aspect-ratio:auto}
  .corpo{display:block!important;background:#fff}
  .bl b,.dia b{color:#000}
}
"""


# Advertências da Portaria SPA/MF nº 1.964/2026 (em vigor desde 17/07/2026), que
# alterou a Portaria SPA/MF nº 1.231/2024. São três frases admitidas; usamos a
# primeira. A norma exige que a advertência ocupe no mínimo 10% da peça — daí a
# tarja de 108 px na imagem de 1080 px.
AVISO_FAZENDA = "Ministério da Fazenda adverte: Apostar pode causar dependência."
AVISO_APOIO = ("Proibido para menores de 18 anos · Aposta não é investimento · "
               "Jogue com responsabilidade")
AVISOS_ALTERNATIVOS = [
    "Ministério da Fazenda adverte: Apostar faz você perder dinheiro.",
    "Ministério da Fazenda adverte: Aposta não é investimento.",
]


PWA_NOME = "Mesa de Análise"


def _manifesto():
    return json.dumps({
        "name": PWA_NOME,
        "short_name": "Mesa",
        "description": "Quadros operacionais do dia — análise de partidas para trading esportivo.",
        "lang": "pt-BR",
        # relativo: o site mora em /<repositorio>/ no GitHub Pages, não na raiz do domínio
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0E1116",
        "theme_color": "#0E1116",
        "icons": [
            {"src": "icone-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "icone-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "icone-mask.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, ensure_ascii=False, indent=2)


# Rede primeiro, cache como rede de segurança: o relatório do dia muda, então
# servir cache primeiro mostraria dado velho. Offline, cai no que já foi visto.
SW_JS = r"""
const CACHE = "mesa-v1";
const ESSENCIAIS = ["./", "./index.html", "./manifest.webmanifest"];

self.addEventListener("install", ev => {
  ev.waitUntil(caches.open(CACHE).then(c => c.addAll(ESSENCIAIS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", ev => {
  ev.waitUntil(
    caches.keys()
      .then(ns => Promise.all(ns.filter(n => n !== CACHE).map(n => caches.delete(n))))
      .then(() => self.clients.claim()));
});

self.addEventListener("fetch", ev => {
  const req = ev.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  ev.respondWith(
    fetch(req)
      .then(resp => {
        if (resp && resp.ok){
          const copia = resp.clone();
          caches.open(CACHE).then(c => c.put(req, copia));
        }
        return resp;
      })
      .catch(() => caches.match(req).then(r => r || caches.match("./index.html"))));
});
"""

JS_PWA = r"""
// O botão de instalar só aparece quando o navegador diz que dá para instalar.
let promptInstalar = null;

window.addEventListener("beforeinstallprompt", ev => {
  ev.preventDefault();
  promptInstalar = ev;
  const b = document.getElementById("b-instalar");
  if (b) b.hidden = false;
});

window.addEventListener("appinstalled", () => {
  promptInstalar = null;
  const b = document.getElementById("b-instalar");
  if (b) b.hidden = true;
});

async function instalar(){
  if (promptInstalar){
    promptInstalar.prompt();
    await promptInstalar.userChoice;
    promptInstalar = null;
    const b = document.getElementById("b-instalar");
    if (b) b.hidden = true;
    return;
  }
  // iPhone e iPad não têm o prompt: lá a instalação é pelo menu Compartilhar
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
  alert(ios
    ? "No iPhone/iPad: toque em Compartilhar (o quadrado com a seta) e escolha "
      + "\"Adicionar à Tela de Início\"."
    : "Seu navegador não ofereceu a instalação. No Chrome, procure o ícone de instalar "
      + "na barra de endereço, ou o menu ⋮ → \"Instalar aplicativo\".");
}

if ("serviceWorker" in navigator){
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(RAIZ_SITE + "sw.js", {scope: RAIZ_SITE})
      .catch(() => {});   // file:// e http não registram — a página funciona igual
  });
}
"""


def _cabeca_pwa(prefixo=""):
    """Tags que tornam a página instalável. `prefixo` = caminho até a raiz do site."""
    return (f'<link rel="manifest" href="{prefixo}manifest.webmanifest">'
            f'<meta name="theme-color" content="#0E1116">'
            f'<meta name="mobile-web-app-capable" content="yes">'
            f'<meta name="apple-mobile-web-app-capable" content="yes">'
            f'<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
            f'<meta name="apple-mobile-web-app-title" content="Mesa">'
            f'<link rel="apple-touch-icon" href="{prefixo}icone-192.png">'
            f'<link rel="icon" href="{prefixo}icone-192.png">')


def _botao_instalar():
    return ('<button id="b-instalar" hidden onclick="instalar()" '
            'title="Instalar como aplicativo">⤓ Instalar app</button>')


def _escrever_icones(destino: Path):
    """Ícone sem texto: só formas, para não depender de fonte instalada."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  (aviso: Pillow não encontrado — o site fica sem ícone e o navegador não vai\n"
              "   oferecer a instalação. Rode: pip install pillow)")
        return False

    def desenhar(lado, margem):
        img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        raio = int(lado * 0.22)
        d.rounded_rectangle([0, 0, lado - 1, lado - 1], radius=raio, fill="#0E1116")

        util = lado - 2 * margem
        larg = int(util * 0.14)
        vao = int((util - 4 * larg) / 3)
        alturas = [0.42, 0.68, 0.90, 0.56]        # silhueta de barras, como um gráfico
        cores = ["#4C7EF3", "#A97BF0", "#25B49B", "#E0A02F"]
        base = margem + util
        for i, (h, cor) in enumerate(zip(alturas, cores)):
            x = margem + i * (larg + vao)
            y = base - int(util * h)
            d.rounded_rectangle([x, y, x + larg, base], radius=int(larg * 0.35), fill=cor)
        return img

    # ícone comum usa a moldura toda; o maskable recua 20%, que é a zona segura
    desenhar(512, int(512 * 0.20)).save(destino / "icone-512.png")
    desenhar(512, int(512 * 0.20)).resize((192, 192), Image.LANCZOS).save(destino / "icone-192.png")
    desenhar(512, int(512 * 0.30)).save(destino / "icone-mask.png")
    return True


def _rodape_legal():
    return f"""<div class="legal">
  <div class="legal-forte">{e(AVISO_FAZENDA)}</div>
  <div class="legal-linha"><span class="idade">18+</span> {e(AVISO_APOIO)}</div>
  <div class="legal-nota">Este site é material de análise próprio; não é convite, promessa de
  ganho nem indicação de casa de apostas. Resultado passado não garante resultado futuro, e
  qualquer entrada pode dar prejuízo. Se apostar deixou de ser diversão, procure ajuda:
  <a href="https://jogadoresanonimos.com.br" target="_blank" rel="noopener">Jogadores Anônimos</a>
  ou <a href="https://cvv.org.br" target="_blank" rel="noopener">CVV</a> (ligue 188, 24h,
  gratuito).</div>
</div>"""


# o botão "Imagem" desenha o quadro num canvas e baixa um PNG quadrado, do
# tamanho certo para mandar no grupo. Sem biblioteca: os escudos já estão na
# página como data: URI, então o canvas não fica "sujo" e o toBlob funciona.
JS_IMAGEM = r"""
const CORES_IMG = {bg:"#151A21", pan:"#1B222B", line:"#28313D",
                   tx:"#E7ECF3", tx2:"#94A1B2", tx3:"#66707E"};
const FONTE = '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif';

function _linhas(ctx, texto, largura, max){
  const palavras = String(texto || "").split(/\s+/).filter(Boolean);
  const saida = [];
  let linha = "", sobrou = false;
  for (let i = 0; i < palavras.length; i++){
    const teste = linha ? linha + " " + palavras[i] : palavras[i];
    if (ctx.measureText(teste).width > largura && linha){
      if (saida.length === max - 1){ sobrou = true; break; }   // não cabe mais linha
      saida.push(linha); linha = palavras[i];
    } else {
      linha = teste;
    }
  }
  if (linha) saida.push(linha);
  // texto cortado sempre termina em reticências, senão a frase mente por omissão
  if (sobrou && saida.length){
    let corte = saida[saida.length-1];
    while (corte.length > 4 && ctx.measureText(corte + "…").width > largura) corte = corte.slice(0,-1);
    saida[saida.length-1] = corte.replace(/[ ,;:]+$/, "") + "…";
  }
  return saida;
}

function _imagem(src){
  return new Promise(ok => {
    if (!src) return ok(null);
    const im = new Image();
    im.onload = () => ok(im);
    im.onerror = () => ok(null);
    im.src = src;
  });
}

async function montarImagem(card){
  const d = JSON.parse(card.dataset.img);
  const escudos = [...card.querySelectorAll("img.esc")].map(i => i.src);
  const [ec, ef] = await Promise.all([_imagem(escudos[0]), _imagem(escudos[1])]);

  const S = 1080, P = 66;
  const cv = document.createElement("canvas");
  cv.width = S; cv.height = S;
  const c = cv.getContext("2d");

  c.fillStyle = CORES_IMG.bg; c.fillRect(0,0,S,S);
  c.fillStyle = d.cor;        c.fillRect(0,0,S,9);

  // marca d'água: entra antes do conteúdo, para ficar atrás e não atrapalhar a leitura
  if (MARCA){
    c.save();
    c.translate(S/2, S/2); c.rotate(-24 * Math.PI / 180);
    c.textAlign = "center"; c.textBaseline = "middle";
    c.font = `800 92px ${FONTE}`;
    c.fillStyle = "rgba(255,255,255,.055)";
    c.fillText(MARCA, 0, 0);
    c.restore();
    c.textAlign = "left";
  }

  // cabeçalho
  c.textBaseline = "alphabetic";
  c.font = `700 21px ${FONTE}`; c.fillStyle = CORES_IMG.tx3;
  c.fillText("MESA DE ANÁLISE", P, 74);
  if (MARCA){
    const lg = c.measureText("MESA DE ANÁLISE").width;
    c.fillStyle = CORES_IMG.tx2;
    c.fillText(MARCA, P + lg + 18, 74);
  }
  c.textAlign = "right"; c.fillStyle = CORES_IMG.tx3;
  c.fillText(String(d.data || "").toUpperCase(), S-P, 74);
  c.textAlign = "left";

  // hora + etiqueta
  c.font = `700 52px ${FONTE}`; c.fillStyle = CORES_IMG.tx;
  c.fillText(d.hora || "", P, 168);
  const larguraHora = c.measureText(d.hora || "").width;
  const et = d.live ? d.etiqueta : "PRÉ-LIVE";
  c.font = `800 22px ${FONTE}`;
  const larguraEt = c.measureText(et).width;
  const exBg = d.live ? "rgba(239,95,95,.14)" : "rgba(76,126,243,.14)";
  const exTx = d.live ? "#F58A8A" : "#8FB0F7";
  c.fillStyle = exBg;
  c.beginPath(); c.roundRect(P + larguraHora + 22, 138, larguraEt + 34, 40, 20); c.fill();
  c.fillStyle = exTx; c.fillText(et, P + larguraHora + 39, 165);

  // times
  let y = 250;
  for (const [nome, im] of [[d.casa, ec], [d.fora, ef]]){
    if (im){ c.drawImage(im, P, y-42, 54, 54); }
    else {
      c.fillStyle = CORES_IMG.pan;
      c.beginPath(); c.arc(P+27, y-15, 27, 0, 7); c.fill();
      c.fillStyle = CORES_IMG.tx3; c.font = `800 24px ${FONTE}`;
      c.textAlign = "center"; c.fillText((nome||"?")[0].toUpperCase(), P+27, y-6); c.textAlign = "left";
    }
    c.fillStyle = CORES_IMG.tx; c.font = `650 42px ${FONTE}`;
    c.fillText(_linhas(c, nome, S - P*2 - 80, 1)[0] || "", P + 76, y);
    y += 76;
  }
  c.fillStyle = CORES_IMG.tx3; c.font = `400 25px ${FONTE}`;
  c.fillText(d.liga || "", P, y - 4);

  // divisória
  y += 34;
  c.fillStyle = CORES_IMG.line; c.fillRect(P, y, S - P*2, 1);

  // método e mercado
  y += 56;
  c.fillStyle = d.cor; c.font = `800 24px ${FONTE}`;
  c.fillText(String(d.metodo || "").toUpperCase(), P, y);
  y += 48;
  c.fillStyle = CORES_IMG.tx; c.font = `600 36px ${FONTE}`;
  for (const l of _linhas(c, d.mercado, S - P*2, 2)){ c.fillText(l, P, y); y += 44; }

  // motivo
  y += 14;
  c.fillStyle = CORES_IMG.tx2; c.font = `400 27px ${FONTE}`;
  for (const l of _linhas(c, d.motivo, S - P*2, 4)){ c.fillText(l, P, y); y += 38; }

  // números, ancorados acima da tarja de advertência
  const BANDA = Math.round(S * 0.10);      // a norma pede no mínimo 10% da peça
  const cx = S - P*2, bh = 132, by = S - BANDA - 26 - bh;

  // o espaço que sobrar entre o motivo e os números vira leitura ao vivo:
  // quantas linhas couberem, sem nunca invadir os números
  const sobra = by - 34 - y;
  const MINIMO = 20 + 34 + 34;          // respiro + rótulo + uma linha de texto
  if (d.seguir && sobra >= MINIMO){
    y += 20;
    c.fillStyle = "#34C48A"; c.font = `700 21px ${FONTE}`;
    c.fillText("SEGUIR SE", P, y);
    y += 34;
    const cabem = Math.max(1, Math.min(4, Math.floor((by - 34 - y) / 34)));
    c.fillStyle = CORES_IMG.tx2; c.font = `400 25px ${FONTE}`;
    for (const l of _linhas(c, d.seguir, S - P*2, cabem)){ c.fillText(l, P, y); y += 34; }
  }
  c.fillStyle = CORES_IMG.pan;
  c.beginPath(); c.roundRect(P, by, cx/2 - 7, bh, 12); c.fill();
  c.beginPath(); c.roundRect(P + cx/2 + 7, by, cx/2 - 7, bh, 12); c.fill();

  const bloco = (x, rot, val, sub) => {
    c.fillStyle = CORES_IMG.tx3; c.font = `700 21px ${FONTE}`;
    c.fillText(rot.toUpperCase(), x + 26, by + 44);
    c.fillStyle = CORES_IMG.tx;  c.font = `650 46px ${FONTE}`;
    c.fillText(val, x + 26, by + 100);
    if (sub){
      const w = c.measureText(val).width;
      c.fillStyle = CORES_IMG.tx2; c.font = `600 26px ${FONTE}`;
      c.fillText(sub, x + 26 + w + 14, by + 100);
    }
  };
  bloco(P, d.rotOdd, d.odd);
  // a imagem sai com a banca que está na tela agora, não com a do arquivo
  const reais = (typeof BANCA === "number" && d.stakeNum != null)
    ? "· " + brlJS(d.stakeNum / 100 * BANCA) : d.reais;
  bloco(P + cx/2 + 7, "stake", d.stake, reais);

  // tarja de advertência — ocupa os 10% de baixo, em fundo próprio para contrastar
  c.fillStyle = "#0A0D11"; c.fillRect(0, S - BANDA, S, BANDA);
  c.fillStyle = "#3A4756"; c.fillRect(0, S - BANDA, S, 1);
  c.textAlign = "center";
  c.fillStyle = "#E7ECF3"; c.font = `700 27px ${FONTE}`;
  c.fillText(AVISO_FAZENDA, S/2, S - BANDA + 44);
  c.fillStyle = "#94A1B2"; c.font = `600 22px ${FONTE}`;
  c.fillText(AVISO_APOIO, S/2, S - BANDA + 80);
  c.textAlign = "left";
  return cv;
}

async function baixarImagem(botao, ev){
  ev.preventDefault(); ev.stopPropagation();
  const card = botao.closest("details.jogo");
  const rotulo = botao.textContent;
  botao.textContent = "gerando…";
  try {
    const cv = await montarImagem(card);
    await new Promise(ok => cv.toBlob(b => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = card.dataset.arquivo + ".png";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      ok();
    }, "image/png"));
  } catch (e) {
    alert("Não deu para gerar a imagem: " + e.message);
  }
  botao.textContent = rotulo;
}
"""


JS_BANCA = r"""
// A stake é uma fração da banca (Kelly), então trocar a banca muda o valor em
// reais e NÃO muda o percentual — nem a exposição, que também é percentual.
let BANCA = BANCA_INICIAL;

function brlJS(v){
  const p = (Math.round(v * 100) / 100).toFixed(2).split(".");
  return "R$ " + p[0].replace(/\B(?=(\d{3})+$)/g, ".") + "," + p[1];
}

function aplicarBanca(valor, guardar){
  const n = parseFloat(valor);
  if (!isFinite(n) || n <= 0) return;          // campo vazio ou lixo: mantém a anterior
  BANCA = n;

  for (const c of document.querySelectorAll("details.jogo")){
    const em = c.querySelector(".c-vals .reais");
    if (em) em.textContent = "· " + brlJS(parseFloat(c.dataset.stake) / 100 * BANCA);
  }
  const kb = document.getElementById("k-banca");
  if (kb) kb.textContent = brlJS(BANCA);
  const kr = document.getElementById("k-risco");
  if (kr) kr.textContent = brlJS(RISCO_PCT / 100 * BANCA);

  if (guardar){
    try { localStorage.setItem("mesa-banca", String(BANCA)); } catch (e) {}
  }
}

function restaurarBanca(){
  let guardada = null;
  try { guardada = localStorage.getItem("mesa-banca"); } catch (e) {}
  const campo = document.getElementById("f-banca");
  if (guardada && parseFloat(guardada) > 0){
    if (campo) campo.value = guardada;
    aplicarBanca(guardada, false);
  }
}

function bancaPadrao(){
  try { localStorage.removeItem("mesa-banca"); } catch (e) {}
  const campo = document.getElementById("f-banca");
  if (campo) campo.value = BANCA_INICIAL;
  aplicarBanca(BANCA_INICIAL, false);
}

document.addEventListener("DOMContentLoaded", restaurarBanca);
"""

JS_FILTROS = r"""
const $$ = s => [...document.querySelectorAll(s)];

function _ativos(grupo){
  return $$(`.chip[data-grupo="${grupo}"][aria-pressed="true"]`).map(b => b.dataset.valor);
}

function filtrar(){
  const metodos = _ativos("metodo");
  const tipos   = _ativos("tipo");
  const liga    = document.getElementById("f-liga")?.value || "";
  const busca   = (document.getElementById("f-busca")?.value || "").trim().toLowerCase();
  const ordem   = document.getElementById("f-ordem")?.value || "hora";

  let visiveis = [];
  for (const c of $$("details.jogo")){
    const d = c.dataset;
    const ok =
      (!metodos.length || metodos.includes(d.metodo)) &&
      (!tipos.length   || tipos.includes(d.live === "1" ? "live" : "pre")) &&
      (!liga  || d.liga === liga) &&
      (!busca || d.busca.includes(busca));
    c.classList.toggle("fora", !ok);
    if (ok) visiveis.push(c);
  }

  // a grade é CSS grid: 'order' reposiciona sem mexer no HTML
  const chave = {
    hora:  c => c.dataset.hora,
    stake: c => -parseFloat(c.dataset.stake),
    conf:  c => -parseFloat(c.dataset.conf),
  }[ordem];
  visiveis
    .slice()
    .sort((a,b) => { const x = chave(a), y = chave(b); return x < y ? -1 : x > y ? 1 : 0; })
    .forEach((c,i) => c.style.order = i);

  const total = $$("details.jogo").length;
  const cont = document.getElementById("f-conta");
  if (cont) cont.textContent = visiveis.length === total
    ? `${total} entrada(s)`
    : `${visiveis.length} de ${total}`;
  const vazio = document.getElementById("f-vazio");
  if (vazio) vazio.style.display = visiveis.length ? "none" : "block";
}

function alternarChip(b){
  b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
  filtrar();
}

function limparFiltros(){
  $$(".chip").forEach(b => b.setAttribute("aria-pressed","false"));
  const l = document.getElementById("f-liga");   if (l) l.value = "";
  const b = document.getElementById("f-busca");  if (b) b.value = "";
  const o = document.getElementById("f-ordem");  if (o) o.value = "hora";
  filtrar();
}

document.addEventListener("DOMContentLoaded", filtrar);
"""


def _filtros(entradas):
    """Chips de método e tipo, seletor de liga, busca e ordenação.

    Sem JavaScript nada disso aparece filtrando — mas os quadros continuam
    todos visíveis, que é o estado certo para quem só quer ler.
    """
    if not entradas:
        return ""

    chips = []
    for metodo, rotulo in (("BACK_FAV", "Back Favorito"), ("LAY_ZEBRA", "Lay Zebra"),
                           ("OVER", "Over Limite"), ("BACK22", "Back 2x2")):
        n = sum(1 for x in entradas if x["principal"]["metodo"] == metodo)
        if not n:
            continue
        chips.append(
            f'<button class="chip" data-grupo="metodo" data-valor="{metodo}" aria-pressed="false" '
            f'onclick="alternarChip(this)"><i class="sw" style="background:{CORES[metodo]}"></i>'
            f'{rotulo}<span class="ct">{n}</span></button>')

    for valor, rotulo in (("live", "Ao vivo"), ("pre", "Pré-live")):
        n = sum(1 for x in entradas if bool(x.get("aoVivo")) == (valor == "live"))
        if not n:
            continue
        chips.append(
            f'<button class="chip" data-grupo="tipo" data-valor="{valor}" aria-pressed="false" '
            f'onclick="alternarChip(this)">{rotulo}<span class="ct">{n}</span></button>')

    ligas = sorted({x.get("liga") for x in entradas if x.get("liga") and x["liga"] != "—"})
    sel_liga = ""
    if len(ligas) > 1:
        opcoes = "".join(f'<option value="{e(l)}">{e(l)}</option>' for l in ligas)
        sel_liga = (f'<select class="inp" id="f-liga" onchange="filtrar()">'
                    f'<option value="">Todas as ligas</option>{opcoes}</select>')

    return f"""<div class="filtros">
  {"".join(chips)}
  {sel_liga}
  <input class="inp" id="f-busca" type="search" placeholder="Buscar time…" oninput="filtrar()">
  <select class="inp" id="f-ordem" onchange="filtrar()">
    <option value="hora">Por horário</option>
    <option value="stake">Maior stake</option>
    <option value="conf">Maior confiança</option>
  </select>
  <button class="chip lim" onclick="limparFiltros()">Limpar</button>
  <span class="spacer"></span>
  <span class="conta" id="f-conta">{len(entradas)} entrada(s)</span>
</div>"""


def _topo(titulo, sub=""):
    """A mesma barra do aplicativo, para o site e o aplicativo parecerem a mesma coisa."""
    return (f'<div class="topbar"><div class="topbar-in"><div class="brand"><i class="dot"></i>'
            f'<div><h1>Mesa de Análise</h1><span>{e(sub or titulo)}</span></div></div>'
            f'<div class="spacer"></div></div></div>')


def _bloco(rot, conteudo, largo=False):
    if not conteudo:
        return ""
    cls = "bl wide" if largo else "bl"
    return f'<section class="{cls}"><h4>{rot}</h4><div>{conteudo}</div></section>'


def _card(ent, cfg, data_rot=""):
    p = ent["principal"]
    cor = CORES.get(p["metodo"], "#6B7280")
    live = bool(ent.get("aoVivo"))
    rot_odd = "odd máx." if p["tipo"] == "lay" else "odd mín."
    banca = cfg["geral"]["banca"]
    gat = int(cfg["OVER"]["minutoGatilho"])
    tipo_txt = f'AO VIVO {p["janela"][0]}\'' if live else "PRÉ-LIVE"

    esc_map = ent.get("escudos") or {}

    def _time(nome, lado):
        url = esc_map.get(lado)
        img = (f'<img class="esc" src="{url}" alt="" loading="lazy">' if url
               else f'<span class="esc vazio">{e(nome[:1].upper())}</span>')
        return f'<div class="t">{img}<b>{e(nome)}</b></div>'

    capa = f"""
      <div class="cap">
        <div class="c-top">
          <span class="c-hora">{e(ent.get("hora"))}</span>
          <span class="badge {'live' if live else 'pre'}">{tipo_txt}</span>
        </div>
        <div class="c-jogo">
          {_time(ent["casa"], "casa")}
          {_time(ent["fora"], "fora")}
          <small>{e(ent.get("liga"))}</small>
        </div>
        <div class="c-merc">
          <span class="met">{e(p["nome"])}</span>
          <b>{e(p["mercado"])}</b>
          <p class="c-motivo">{e(sem_tags(ent.get("motivoBase") or ent.get("motivoCurto")))}</p>
        </div>
        <div class="c-vals">
          <div><span>{rot_odd}</span><b>{f2(p["oddRec"])}</b></div>
          <div><span>stake</span><b>{f2(p["stake"])}% <em class="reais">· {brl(p["stake"]/100*banca)}</em></b></div>
        </div>
        <div class="c-abre">
          <span class="det">Detalhes <span class="chev">▾</span></span>
          <button type="button" class="c-img" onclick="baixarImagem(this,event)"
                  title="Baixar este quadro como imagem">Imagem</button>
        </div>
      </div>"""

    if p["status"] == "AGUARDAR":
        direcao = "espere a odd cair até" if p["tipo"] == "lay" else "espere a odd subir até"
        preco = (f'<div class="alerta">Não entre no preço atual ({f2(p["oddPdf"])}) — '
                 f'{direcao} <b>{f2(p["oddRec"])}</b>.</div>')
    elif p["status"] == "VALOR":
        preco = (f'<div class="ok">A odd do relatório ({f2(p["oddPdf"])}) já paga a margem — '
                 "pode entrar.</div>")
    else:
        preco = ('<div class="neutro">O relatório não traz preço para este mercado. '
                 f'Busque na exchange a partir de {f2(p["oddRec"])}.</div>')

    M, T = ent["modelo"], ent["tempos"]
    probs = (f'1X2 {pc(M["prob1x2Final"][0])} / {pc(M["prob1x2Final"][1])} / {pc(M["prob1x2Final"][2])} · '
             f'Ambas marcam {pc(M["btts"])} · Over 2.5 {pc(M["over"]["2.5"])} · Over 3.5 {pc(M["over"]["3.5"])}<br>'
             f'Gols esperados <b>{f2(M["lambdaCasa"])} × {f2(M["lambdaFora"])}</b> '
             f'(total {f2(M["lambdaTotal"])}) · Placares: '
             + " · ".join(f'{x["placar"]} <span class="mut">{x["prob"]*100:.0f}%</span>'
                          for x in M["placares"][:4]))

    faixas_mom = ent["momentoDosGols"]["faixas"]
    linhas_mom = "".join(
        f'<tr class="{"dentro" if (i+1)*15 > gat else ""}"><td>{FAIXAS_ROT[i]}</td>'
        f'<td class="barra"><i style="width:{min(100, fx["pctGols"]*2.6):.0f}%"></i></td>'
        f'<td class="n">{fx["pctGols"]:.0f}%</td>'
        f'<td class="n mut">{fx["golsEsperados"]:.2f} gol</td></tr>'
        for i, fx in enumerate(faixas_mom))
    momento = (f'<table class="mini">{linhas_mom}</table>'
               f'<small class="mut">Verde = janela após o minuto {gat}. '
               f'Fonte: {e(ent["momentoDosGols"]["fonte"])}.</small>')

    hist = []
    if ent.get("ultimosCasa"):
        u = ent["ultimosCasa"]
        hist.append(f'<b>{e(ent["casa"])}</b> últimos {u["n"]}: '
                    f'<span class="mono">{e(u["placares"])}</span> · forma {e(u["forma"])}')
    if ent.get("ultimosFora"):
        u = ent["ultimosFora"]
        hist.append(f'<b>{e(ent["fora"])}</b> últimos {u["n"]}: '
                    f'<span class="mono">{e(u["placares"])}</span> · forma {e(u["forma"])}')
    if ent.get("h2h"):
        hist.append(f'Confronto direto: {e(ent["h2h"])}')

    faixas = ""
    if ent.get("faixasFavoritismo"):
        rot = {"superFav": "Super Favorito", "favorito": "Favorito",
               "parelho": "Parelho", "naoFav": "Não Favorito"}
        faixas = " · ".join(f'{rot[k]} <b>{b["v"]}V {b["e"]}E {b["d"]}D</b> ({b["aprov"]:.0f}%)'
                            for k, b in ent["faixasFavoritismo"].items())
        fh = ent.get("faixaHoje")
        if fh:
            faixas += (f'<br><span class="mut">Hoje {e(fh["time"])} entra como '
                       f'<b>{e(fh["nome"])}</b> a {f2(fh["odd"])}.</span>')

    mercados = ""
    if ent.get("oddsPre"):
        linhas = "".join(f'<tr><td>{e(k)}</td>'
                         + "".join(f'<td class="n">{f2(x)}</td>' for x in v) + "</tr>"
                         for k, v in ent["oddsPre"].items())
        mercados = f'<table class="mini">{linhas}</table>'

    notas = []
    if ent.get("camposEstimados"):
        notas.append("Campos estimados: " + e(", ".join(ent["camposEstimados"])) + ".")
    if ent.get("derivado"):
        notas.append("Médias vindas dos últimos jogos — peso do mercado elevado para "
                     f'{ent.get("pesoMercado")}.')
    if M.get("divergenciaMandantePP") is not None and abs(M["divergenciaMandantePP"]) > 10:
        notas.append(f'Divergência de {abs(M["divergenciaMandantePP"]):.0f} p.p. entre modelo e '
                     "mercado — confira desfalques e escalação.")

    sec = p.get("mercadoSecundario") or ""
    if p.get("pSecundario") and p.get("oddRecSecundaria"):
        sec += f' — {pc(p["pSecundario"],1)}, odd mínima {f2(p["oddRecSecundaria"])}'
    outros = ", ".join(o["nome"] for o in ent["metodos"][1:])

    corpo = (preco
             + _bloco("Motivo", ent.get("motivoCurto"), largo=True)
             + _bloco("Leitura ao vivo",
                      f'<div class="live-l seguir"><span>Seguir se</span>{e(ent.get("seguir"))}</div>'
                      f'<div class="live-l descartar"><span>Descartar se</span>{e(ent.get("descartar"))}</div>',
                      largo=True)
             + _bloco("Entrada", e(ent.get("entrada")))
             + _bloco("Saída", e(ent.get("saida")))
             + _bloco("Mercado secundário", e(sec) if sec else "")
             + _bloco("Números do modelo", probs)
             + _bloco("Momento dos gols", momento)
             + _bloco("Histórico", "<br>".join(hist))
             + _bloco("Aproveitamento por faixa de favoritismo", faixas)
             + _bloco("Mercado pré-jogo", mercados)
             + _bloco("Jogadores",
                      (f'<b>{e(ent["casa"])}:</b> {e(ent.get("jogadoresCasa") or "—")}<br>'
                       f'<b>{e(ent["fora"])}:</b> {e(ent.get("jogadoresFora") or "—")}')
                      if (ent.get("jogadoresCasa") or ent.get("jogadoresFora")) else "")
             + _bloco("Outros métodos aprovados", e(outros))
             + (f'<div class="notas">{"<br>".join(notas)}</div>' if notas else ""))

    # tudo que a imagem precisa. Os escudos não entram aqui: já estão na página
    # como data: URI e o desenho lê direto do <img>, sem duplicar 13 KB por card.
    dados_img = {
        "data": data_rot,
        "hora": ent.get("hora") or "",
        "etiqueta": tipo_txt,
        "live": live,
        "casa": ent["casa"], "fora": ent["fora"],
        "liga": ent.get("liga") or "",
        "cor": cor,
        "metodo": p["nome"],
        "mercado": p["mercado"],
        "motivo": sem_tags(ent.get("motivoBase") or ent.get("motivoCurto") or ""),
        "seguir": sem_tags(ent.get("seguir") or ""),
        "rotOdd": rot_odd,
        "odd": f2(p["oddRec"]),
        "stake": f'{f2(p["stake"])}%',
        "reais": f'· {brl(p["stake"]/100*banca)}',
        "stakeNum": round(p["stake"], 4),
        "rodape": "Odd mínima em back, máxima em lay.",
    }
    arquivo = "_".join(x for x in [
        (data_rot or "").replace("/", "-"),
        (ent.get("hora") or "").replace(":", "h"),
        _slug(ent["casa"]), "x", _slug(ent["fora"])] if x)

    return (f'<details class="jogo" style="--c:{cor}"'
            f" data-img='{e(json.dumps(dados_img, ensure_ascii=False))}'"
            f' data-arquivo="{e(arquivo)}"'
            f' data-metodo="{e(p["metodo"])}"'
            f' data-live="{"1" if live else "0"}"'
            f' data-status="{e(p["status"])}"'
            f' data-liga="{e(ent.get("liga") or "")}"'
            f' data-hora="{e(ent.get("hora") or "99:99")}"'
            f' data-stake="{p["stake"]:.4f}"'
            f' data-conf="{ent.get("confianca") or 0}"'
            f' data-busca="{e((ent["casa"] + " " + ent["fora"] + " " + (ent.get("liga") or "")).lower())}">'
            f'<summary>{capa}</summary>'
            f'<div class="corpo">{corpo}</div></details>')


def pagina_do_dia(analise, data, voltar="../index.html"):
    cfg = analise["config"]
    entradas = analise["entradas"]
    banca = cfg["geral"]["banca"]
    risco = analise["resumo"].get("exposicaoRiscoPct", 0)
    ligas = sorted({x.get("liga") for x in entradas if x.get("liga") and x["liga"] != "—"})

    cards = "".join(_card(x, cfg, data) for x in entradas)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório — {e(data)}</title>{_cabeca_pwa("../")}<style>{CSS}</style></head><body>
{_topo(data, f"Relatório do dia · {data}")}
<div class="pg">
<div class="sub">{len(entradas)} entrada(s) selecionada(s) de {len(entradas)+len(analise["descartes"])} jogo(s) analisado(s) ·
banca de <b id="k-banca">{brl(banca)}</b> · comissão {cfg["geral"]["comissao"]}%
{("<br>Ligas: " + e(" · ".join(ligas))) if ligas else ""}</div>
<div class="resumo">
  <div><span>Entradas</span><b>{len(entradas)}</b></div>
  <div><span>Ao vivo</span><b>{sum(1 for x in entradas if x.get("aoVivo"))}</b></div>
  <div><span>Exposição</span><b>{risco:.1f}%</b></div>
  <div><span>Em risco</span><b id="k-risco">{brl(risco/100*banca)}</b></div>
  <div><span>Com valor agora</span><b>{sum(1 for x in entradas if x["principal"]["status"]=="VALOR")}</b></div>
  <div><span>Fora dos critérios</span><b>{len(analise["descartes"])}</b></div>
</div>
<div class="acoes">
  <a href="{voltar}">← Todos os dias</a>
  <button onclick="document.querySelectorAll('details.jogo:not(.fora)').forEach(d=>d.open=true)">Expandir todos</button>
  <button onclick="document.querySelectorAll('details.jogo').forEach(d=>d.open=false)">Recolher todos</button>
  <button onclick="window.print()">Imprimir</button>
  {_botao_instalar()}
  <span class="spacer"></span>
  <label class="banca">Banca
    <input class="inp" id="f-banca" type="number" min="1" step="50" value="{banca:.0f}"
           oninput="aplicarBanca(this.value, true)">
    <button class="btn-lim" onclick="bancaPadrao()"
            title="Voltar para a banca de criterios.json">↺</button>
  </label>
</div>
{_filtros(entradas)}
{f'<div class="grade">{cards}</div>' if cards else "<p>Nenhuma entrada aprovada neste dia.</p>"}
<div class="vazio" id="f-vazio" style="display:none">Nenhum quadro com esses filtros.
<a href="#" onclick="limparFiltros();return false">Limpar</a>.</div>
<div class="rodape">Odd recomendada é o preço a partir do qual a entrada tem a margem exigida —
mínima em back, máxima em lay. O botão <b>Imagem</b> em cada quadro baixa um PNG quadrado, pronto
para mandar no grupo. Trocar a <b>banca</b> no topo recalcula os valores em reais na hora — a stake
em % não muda, porque ela já é uma fração da banca. Gerado automaticamente a partir dos PDFs do dia.</div>
{_rodape_legal()}
</div><script>
const BANCA_INICIAL = {banca:.2f};
const RISCO_PCT = {risco:.4f};
const MARCA = {json.dumps(cfg["geral"].get("marca") or "")};
const RAIZ_SITE = "../";
const AVISO_FAZENDA = {json.dumps(AVISO_FAZENDA)};
const AVISO_APOIO = {json.dumps(AVISO_APOIO)};
{JS_BANCA}{JS_IMAGEM}{JS_FILTROS}{JS_PWA}</script></body></html>"""


def pagina_indice(dias, titulo="Mesa de Análise"):
    cartoes = "".join(
        f'<a class="dia" href="{e(d["pasta"])}/index.html"><b>{e(d["data"])}</b>'
        f'<span>{d["entradas"]} entrada(s) · {d["descartes"]} descartado(s)</span></a>'
        for d in dias)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>{_cabeca_pwa("")}<style>{CSS}</style></head><body>
{_topo(titulo, "Relatórios publicados")}
<div class="pg">
<div class="sub">Do mais recente para o mais antigo.</div>
<div class="acoes"><a href="app.html">Abrir o aplicativo →</a>{_botao_instalar()}</div>
<div class="dias">{cartoes or "<p>Nenhum relatório publicado ainda.</p>"}</div>
<div class="rodape">Cada página traz os quadros do dia: partida, mercado sugerido, motivo e
leitura ao vivo. Clique em um quadro para abrir o detalhe.</div>
{_rodape_legal()}
</div><script>const RAIZ_SITE = "./";{JS_PWA}</script></body></html>"""


def escrever_site(destino: Path, dias: list[dict]):
    """`dias` = [{data, pasta, analise}] — escreve as páginas e o índice."""
    destino.mkdir(parents=True, exist_ok=True)
    resumo = []
    for d in sorted(dias, key=lambda x: x["pasta"], reverse=True):
        pasta = destino / d["pasta"]
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "index.html").write_text(
            pagina_do_dia(d["analise"], d["data"]), encoding="utf-8")
        (pasta / "analise.json").write_text(
            json.dumps(d["analise"], ensure_ascii=False, indent=1), encoding="utf-8")
        resumo.append({"data": d["data"], "pasta": d["pasta"],
                       "entradas": len(d["analise"]["entradas"]),
                       "descartes": len(d["analise"]["descartes"])})
    (destino / "index.html").write_text(pagina_indice(resumo), encoding="utf-8")

    # arquivos que tornam o site instalável como aplicativo
    (destino / "manifest.webmanifest").write_text(_manifesto(), encoding="utf-8")
    (destino / "sw.js").write_text(SW_JS, encoding="utf-8")
    _escrever_icones(destino)
    return resumo
