"""
Geração do site: uma página por dia com a grade de quadros, mais um índice
com o histórico. Sem dependências — só string formatting.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

CORES = {"BACK_FAV": "#2F5FD0", "LAY_ZEBRA": "#7D4FC4", "OVER": "#1B8C78", "BACK22": "#B47714"}
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


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#F4F5F7;color:#16191F;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.pg{max-width:1180px;margin:0 auto;padding:26px 16px 60px}
a{color:#2F5FD0}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#6B7280;font-size:13.5px;margin-bottom:18px}
.resumo{background:#fff;border:1px solid #E3E6EA;border-radius:12px;padding:14px 18px;margin-bottom:16px;display:flex;gap:28px;flex-wrap:wrap}
.resumo div span{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#8A93A0;font-weight:700}
.resumo div b{font-size:19px}
.acoes{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.acoes button,.acoes a{background:#fff;border:1px solid #D8DDE3;border-radius:8px;padding:7px 13px;font:inherit;font-size:13px;cursor:pointer;color:#414A56;text-decoration:none}
.acoes button:hover,.acoes a:hover{border-color:#A8AEB8}

.grade{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;align-items:stretch}
.jogo{background:#fff;border:1px solid #E3E6EA;border-top:4px solid var(--c);border-radius:12px;overflow:hidden;page-break-inside:avoid;display:flex;flex-direction:column}
.jogo>summary{flex:1;display:flex;flex-direction:column}
.jogo[open]{grid-column:1/-1}
.jogo>summary{list-style:none;cursor:pointer}
.jogo>summary::-webkit-details-marker{display:none}
.cap{display:flex;flex-direction:column;gap:7px;padding:11px 13px;flex:1}
/* o quadrado é o piso: com a motivação o card cresce, e a linha inteira acompanha */
.jogo:not([open]) .cap{aspect-ratio:1/1;justify-content:space-between}
.jogo[open] .cap{flex-direction:row;align-items:center;flex-wrap:wrap;gap:14px 22px;border-bottom:1px solid #EEF0F3;background:#FBFCFD}
.cap:hover{background:#FBFCFD}
.c-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.c-hora{font-variant-numeric:tabular-nums;font-weight:700;color:#414A56;font-size:15px}
.c-jogo .t{display:flex;align-items:center;gap:7px;margin-bottom:3px}
.c-jogo .t b{font-size:13.5px;font-weight:650;line-height:1.25;min-width:0;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.esc{width:22px;height:22px;object-fit:contain;flex:none}
.esc.vazio{width:22px;height:22px;border-radius:50%;background:#EEF0F3;color:#8A93A0;
  display:grid;place-items:center;font-size:11px;font-weight:800;flex:none}
.c-jogo small{display:block;color:#8A93A0;font-size:11px;margin-top:4px}
.c-motivo{margin:5px 0 0;font-size:11.5px;line-height:1.4;color:#4B5563;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
details[open] .c-motivo{display:none}
details[open] .c-jogo .t b{-webkit-line-clamp:none}
.c-merc .met{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--c)}
.c-merc b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:12.5px;font-weight:600;line-height:1.35;margin-top:2px}
.c-vals{border-top:1px solid #F1F3F5;padding-top:6px}
.c-vals div{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:3px}
.c-vals span{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:#8A93A0;font-weight:700}
.c-vals b{font-size:15px;font-variant-numeric:tabular-nums;white-space:nowrap}
.c-vals em{font-style:normal;font-size:12px;font-weight:600;color:#4B5563}
.badge{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.04em;padding:3px 8px;border-radius:20px;white-space:nowrap}
.badge.live{background:#FDEAEA;color:#B3261E;border:1px solid #F3C2C0}
.badge.pre{background:#EDF1FB;color:#2F5FD0;border:1px solid #C9D7F5}
.c-abre{text-align:center;color:#6B7280;font-size:11.5px;border-top:1px solid #F1F3F5;padding-top:6px}
.c-abre .chev{display:inline-block;margin-left:4px;transition:transform .15s}
details[open] .c-abre{border:0;padding:0;margin-left:auto}
details[open] .c-abre .chev{transform:rotate(180deg)}
details[open] .c-vals{border:0;padding:0;display:flex;gap:22px}
details[open] .c-vals div{margin:0;flex-direction:column;align-items:flex-start;gap:0}
details[open] .c-merc b{-webkit-line-clamp:none}

.corpo{padding:6px 16px 16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:0 24px}
.corpo>.alerta,.corpo>.ok,.corpo>.neutro,.corpo>.notas{grid-column:1/-1}
.bl{padding:12px 0;border-bottom:1px solid #F1F3F5;min-width:0}
.bl.wide{grid-column:1/-1}
.bl h4{margin:0 0 5px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#8A93A0;font-weight:700}
.alerta{margin:10px 0;background:#FFF6E5;border:1px solid #F0DCB0;color:#7A5A10;border-radius:8px;padding:9px 12px;font-size:13.5px}
.ok{margin:10px 0;background:#E9F8F0;border:1px solid #B6E3CC;color:#14663F;border-radius:8px;padding:9px 12px;font-size:13.5px}
.neutro{margin:10px 0;background:#F3F5F7;border:1px solid #DFE4E9;color:#4B5563;border-radius:8px;padding:9px 12px;font-size:13.5px}
.live-l{display:flex;gap:10px;margin-bottom:6px;font-size:14px}
.live-l span{flex:none;width:92px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;font-weight:700;padding-top:3px}
.seguir span{color:#14804A}
.descartar span{color:#C0392B}
.notas{margin-top:12px;background:#FFFBEF;border:1px solid #F0E3C0;border-radius:8px;padding:10px 12px;font-size:12.5px;color:#7A5A10}
table.mini{width:100%;border-collapse:collapse;font-size:12.5px}
table.mini td{padding:3px 6px;border-bottom:1px solid #F4F6F8}
table.mini td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.mini tr.dentro td{color:#14663F;font-weight:600}
td.barra{width:45%}
td.barra i{display:block;height:6px;border-radius:3px;background:#CBD2DA}
tr.dentro td.barra i{background:#1B8C78}
.mono{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px}
.mut{color:#8A93A0}
h3{font-size:16px;margin:30px 0 10px}
.rodape{margin-top:24px;color:#8A93A0;font-size:12.5px;line-height:1.6}
.dias{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
.dia{background:#fff;border:1px solid #E3E6EA;border-radius:12px;padding:15px 17px;text-decoration:none;color:inherit;display:block}
.dia:hover{border-color:#A8AEB8}
.dia b{display:block;font-size:17px;margin-bottom:5px}
.dia span{color:#6B7280;font-size:13px}
@media (max-width:1080px){ .grade{grid-template-columns:repeat(3,minmax(0,1fr))} }
@media (max-width:820px){ .grade{grid-template-columns:repeat(2,minmax(0,1fr))} }
@media (max-width:520px){ .grade{grid-template-columns:1fr} .jogo:not([open]) .cap{aspect-ratio:auto} }
@media print{
  body{background:#fff}.pg{padding:0}.acoes{display:none}
  .grade{display:block}.jogo{border-color:#ccc;margin-bottom:10px}
  .jogo:not([open]) .cap{aspect-ratio:auto}.corpo{display:block!important}
}
"""


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
<title>Relatório — {e(data)}</title><style>{CSS}</style></head><body><div class="pg">
<h1>Relatório do dia — {e(data)}</h1>
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
<title>{e(titulo)}</title><style>{CSS}</style></head><body><div class="pg">
<h1>{e(titulo)}</h1>
<div class="sub">Relatórios publicados, do mais recente para o mais antigo.</div>
<div class="acoes"><a href="app.html">Abrir a Mesa de Análise (aplicativo)</a></div>
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
