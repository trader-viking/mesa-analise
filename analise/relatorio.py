"""
Geração do site: uma página por dia com a grade de quadros, mais um índice
com o histórico. Sem dependências — só string formatting.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

# as mesmas quatro cores de método do aplicativo (--m1 a --m4)
CORES = {"BACK_FAV": "#4C7EF3", "LAY_ZEBRA": "#A97BF0", "OVER": "#25B49B", "BACK22": "#E0A02F"}
FAIXAS_ROT = ["0–15'", "16–30'", "31–45'", "46–60'", "61–75'", "76–90'"]


def sem_tags(s):
    """A motivação vem com marcação; na capa ela entra como texto puro."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s or ""))).strip()


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


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
.c-abre{text-align:center;color:var(--tx3);font-size:11.5px;border-top:1px solid var(--line);padding-top:6px}
.c-abre .chev{display:inline-block;margin-left:4px;transition:transform .15s}
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
  .topbar,.acoes{display:none!important}
  .pg{padding:0}
  .grade{display:block}
  .jogo{border-color:#ccc;background:#fff;margin-bottom:10px}
  .jogo:not([open]) .cap{aspect-ratio:auto}
  .corpo{display:block!important;background:#fff}
  .bl b,.dia b{color:#000}
}
"""


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


def _card(ent, cfg):
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
          <div><span>stake</span><b>{f2(p["stake"])}% <em>· {brl(p["stake"]/100*banca)}</em></b></div>
        </div>
        <div class="c-abre"><span>Detalhes</span><span class="chev">▾</span></div>
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

    return (f'<details class="jogo" style="--c:{cor}"><summary>{capa}</summary>'
            f'<div class="corpo">{corpo}</div></details>')


def pagina_do_dia(analise, data, voltar="../index.html"):
    cfg = analise["config"]
    entradas = analise["entradas"]
    banca = cfg["geral"]["banca"]
    risco = analise["resumo"].get("exposicaoRiscoPct", 0)
    ligas = sorted({x.get("liga") for x in entradas if x.get("liga") and x["liga"] != "—"})

    cards = "".join(_card(x, cfg) for x in entradas)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório — {e(data)}</title><style>{CSS}</style></head><body>
{_topo(data, f"Relatório do dia · {data}")}
<div class="pg">
<div class="sub">{len(entradas)} entrada(s) selecionada(s) de {len(entradas)+len(analise["descartes"])} jogo(s) analisado(s) ·
banca de {brl(banca)} · comissão {cfg["geral"]["comissao"]}%
{("<br>Ligas: " + e(" · ".join(ligas))) if ligas else ""}</div>
<div class="resumo">
  <div><span>Entradas</span><b>{len(entradas)}</b></div>
  <div><span>Ao vivo</span><b>{sum(1 for x in entradas if x.get("aoVivo"))}</b></div>
  <div><span>Exposição</span><b>{risco:.1f}%</b></div>
  <div><span>Em risco</span><b>{brl(risco/100*banca)}</b></div>
  <div><span>Com valor agora</span><b>{sum(1 for x in entradas if x["principal"]["status"]=="VALOR")}</b></div>
  <div><span>Fora dos critérios</span><b>{len(analise["descartes"])}</b></div>
</div>
<div class="acoes">
  <a href="{voltar}">← Todos os dias</a>
  <button onclick="document.querySelectorAll('details').forEach(d=>d.open=true)">Expandir todos</button>
  <button onclick="document.querySelectorAll('details').forEach(d=>d.open=false)">Recolher todos</button>
  <button onclick="window.print()">Imprimir</button>
</div>
{f'<div class="grade">{cards}</div>' if cards else "<p>Nenhuma entrada aprovada neste dia.</p>"}
<div class="rodape">Odd recomendada é o preço a partir do qual a entrada tem a margem exigida —
mínima em back, máxima em lay. Gerado automaticamente a partir dos PDFs do dia.</div>
</div></body></html>"""


def pagina_indice(dias, titulo="Mesa de Análise"):
    cartoes = "".join(
        f'<a class="dia" href="{e(d["pasta"])}/index.html"><b>{e(d["data"])}</b>'
        f'<span>{d["entradas"]} entrada(s) · {d["descartes"]} descartado(s)</span></a>'
        for d in dias)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title><style>{CSS}</style></head><body>
{_topo(titulo, "Relatórios publicados")}
<div class="pg">
<div class="sub">Do mais recente para o mais antigo.</div>
<div class="acoes"><a href="app.html">Abrir o aplicativo →</a></div>
<div class="dias">{cartoes or "<p>Nenhum relatório publicado ainda.</p>"}</div>
<div class="rodape">Cada página traz os quadros do dia: partida, mercado sugerido, motivo e
leitura ao vivo. Clique em um quadro para abrir o detalhe.</div>
</div></body></html>"""


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
    return resumo
