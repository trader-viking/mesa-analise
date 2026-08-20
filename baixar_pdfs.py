#!/usr/bin/env python3
"""
Mesa de Análise — baixador de PDFs.

Abre cada partida no site e salva a página como PDF, do mesmo jeito que você
faz à mão, e já guarda o arquivo em pdfs/<data>/<liga>/ com o nome certo.

    python3 baixar_pdfs.py --login              entra na sua conta (uma vez só)
    python3 baixar_pdfs.py                      baixa as partidas de hoje
    python3 baixar_pdfs.py --quando amanha      baixa as partidas de amanhã
    python3 baixar_pdfs.py --urls urls.txt      baixa só os links do arquivo

Como o nome do arquivo é decidido
---------------------------------
Depois de imprimir, o script lê o próprio PDF com o mesmo leitor da análise e
tira dali horário, times e liga. Ou seja: ele não precisa saber onde o site
mostra essas informações na tela — basta o PDF sair certo.

Sua sessão fica em .sessao.json e suas credenciais nunca entram no código.
Os dois estão no .gitignore.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "analise"))

PDFS = RAIZ / "pdfs"
SESSAO = RAIZ / ".sessao.json"
CONFIG = RAIZ / "analise" / "site.json"
TEMP = RAIZ / ".baixando"

CONFIG_PADRAO = {
    "base": "https://clube.theoborges.com/",
    "pagina_do_dia": "https://clube.theoborges.com/matches?dia={quando}",
    "seletor_links_partida": "",
    "padrao_link_partida": r"/match",
    "abas": ["Geral", "Odds", "H2H", "Desempenho", "Gols", "Cartões", "Escanteios", "Jogadores"],
    "esperaMs": 1200,
    "rolarAntesDeImprimir": True,
    "pdf": {"format": "A4", "print_background": True,
            "margin": {"top": "10mm", "bottom": "10mm", "left": "8mm", "right": "8mm"}},
}


def carregar_config():
    cfg = dict(CONFIG_PADRAO)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    return cfg


def limpar_nome(s):
    """Nome de arquivo seguro, sem acento nem caractere proibido."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Za-z0-9]+", "", s)
    return s or "Time"


def limpar_pasta(s):
    """Nome de pasta válido nos dois sistemas. Acento fica; separador e proibido, não."""
    s = re.sub(r'[\\/:*?"<>|]+', "-", str(s or "").strip()) or "Sem liga"
    return s.rstrip(". ") or "Sem liga"


def pasta_do_dia(dia_arg, jogo):
    """Prioridade: o dia que você passou > a data do PDF > hoje."""
    if dia_arg:
        return dia_arg
    d = jogo.get("data")            # vem como "15/08"
    if d and re.match(r"^\d{2}/\d{2}$", d):
        return f'{d[:2]}-{d[3:]}-{date.today().year}'
    return date.today().strftime("%d-%m-%Y")


# ---------------------------------------------------------------- navegador
def abrir_navegador(pw, visivel, usar_sessao=True):
    nav = pw.chromium.launch(headless=not visivel)
    ctx_args = {"viewport": {"width": 1440, "height": 2200}}
    if usar_sessao and SESSAO.exists():
        ctx_args["storage_state"] = str(SESSAO)
    return nav, nav.new_context(**ctx_args)


def fazer_login(cfg):
    from playwright.sync_api import sync_playwright

    if not cfg["base"]:
        print("Preencha 'base' em analise/site.json com o endereço do site.")
        return 1
    with sync_playwright() as pw:
        nav, ctx = abrir_navegador(pw, visivel=True, usar_sessao=False)
        pg = ctx.new_page()
        pg.goto(cfg["base"], wait_until="domcontentloaded")
        print("\nUma janela do navegador abriu.")
        print("Entre na sua conta normalmente e deixe a página de partidas aberta.")
        input("Quando terminar, volte aqui e aperte Enter... ")
        ctx.storage_state(path=str(SESSAO))
        nav.close()
    print(f"Sessão guardada em {SESSAO.name}. Não precisa fazer isso de novo enquanto ela valer.")
    return 0


def preparar_pagina(pg, cfg):
    """Abre as abas e rola a página, para tudo estar renderizado na hora de imprimir."""
    for aba in cfg.get("abas") or []:
        try:
            alvo = pg.get_by_text(aba, exact=True).first
            if alvo.count() and alvo.is_visible():
                alvo.click(timeout=2500)
                pg.wait_for_timeout(cfg["esperaMs"])
        except Exception:
            pass          # aba que não existe nesta partida é só ignorada
    if cfg.get("rolarAntesDeImprimir"):
        try:
            pg.evaluate("""async () => {
              const passo = 700;
              for (let y = 0; y < document.body.scrollHeight; y += passo){
                window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120));
              }
              window.scrollTo(0, 0);
            }""")
        except Exception:
            pass
    pg.wait_for_timeout(cfg["esperaMs"])


def coletar_urls(cfg, dia, urls_arquivo, quando="hoje"):
    """Do arquivo de URLs, ou da página do dia se ela estiver configurada."""
    if urls_arquivo:
        caminho = Path(urls_arquivo)
        if not caminho.exists():
            print(f"Arquivo {caminho} não encontrado.")
            return []
        return [l.strip() for l in caminho.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")]

    if not cfg["pagina_do_dia"]:
        print("Sem lista de partidas. Use --urls urls.txt, ou preencha 'pagina_do_dia'\n"
              "em analise/site.json.")
        return []

    from playwright.sync_api import sync_playwright
    iso = ""
    if dia:
        try:
            iso = datetime.strptime(dia, "%d-%m-%Y").strftime("%Y-%m-%d")
        except ValueError:
            iso = dia
    alvo = (cfg["pagina_do_dia"]
            .replace("{quando}", quando or "hoje")
            .replace("{data}", iso or "")
            .replace("{dia}", dia or ""))

    print(f"Abrindo {alvo}")
    with sync_playwright() as pw:
        nav, ctx = abrir_navegador(pw, visivel=False)
        pg = ctx.new_page()
        pg.goto(alvo, wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(cfg["esperaMs"])

        if "login" in pg.url or "senha" in (pg.title() or "").lower():
            nav.close()
            print("O site pediu login. Rode `python3 baixar_pdfs.py --login` de novo.")
            return []

        if cfg.get("seletor_links_partida"):
            hrefs = pg.eval_on_selector_all(
                cfg["seletor_links_partida"], "els => els.map(e => e.href).filter(Boolean)")
        else:
            # sem seletor configurado: pega todo link que pareça de partida
            hrefs = pg.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            padrao = re.compile(cfg.get("padrao_link_partida") or r"/match")
            base_lista = alvo.split("?")[0]
            hrefs = [h for h in hrefs if h and padrao.search(h) and h.split("?")[0] != base_lista]
        nav.close()

    vistos, saida = set(), []
    for h in hrefs:
        if h not in vistos:
            vistos.add(h)
            saida.append(h)
    if not saida:
        print("A página abriu, mas nenhum link de partida foi reconhecido.\n"
              "Ajuste 'seletor_links_partida' ou 'padrao_link_partida' em analise/site.json,\n"
              "ou use --urls urls.txt com os links colados à mão.")
    return saida


def baixar(urls, cfg, dia, forcar=False):
    from playwright.sync_api import sync_playwright
    import leitor_pdf

    TEMP.mkdir(exist_ok=True)
    salvos, pulados, falhas = [], 0, []

    with sync_playwright() as pw:
        nav, ctx = abrir_navegador(pw, visivel=False)
        pg = ctx.new_page()
        for i, url in enumerate(urls, 1):
            bruto = TEMP / f"partida_{i:03d}.pdf"
            try:
                pg.goto(url, wait_until="networkidle", timeout=60000)
                preparar_pagina(pg, cfg)
                pg.pdf(path=str(bruto), **cfg["pdf"])
            except Exception as exc:
                falhas.append(f"{url} — {exc}")
                continue

            jogo = None
            try:
                jogo = leitor_pdf.ler_pdf(bruto)
            except Exception:
                pass
            if not jogo:
                falhas.append(f"{url} — PDF saiu, mas o leitor não reconheceu o formato "
                              f"(guardado em {bruto.relative_to(RAIZ)})")
                continue

            pasta = PDFS / pasta_do_dia(dia, jogo) / limpar_pasta(jogo.get("liga"))
            pasta.mkdir(parents=True, exist_ok=True)
            hora = (jogo.get("hora") or "00:00").replace(":", "h")
            nome = f'{i:03d}_{hora}_{limpar_nome(jogo["casa"])}_x_{limpar_nome(jogo["fora"])}.pdf'
            destino = pasta / nome

            if destino.exists() and not forcar:
                bruto.unlink(missing_ok=True)
                pulados += 1
                print(f'  = {nome}  (já existe)')
                continue

            shutil.move(str(bruto), str(destino))
            salvos.append(destino)
            print(f'  ✓ {jogo["hora"]}  {jogo["casa"]} x {jogo["fora"]}  →  {destino.relative_to(RAIZ)}')
        nav.close()

    if not any(TEMP.iterdir()):
        TEMP.rmdir()
    return salvos, pulados, falhas


def main():
    ap = argparse.ArgumentParser(description="Baixa os PDFs das partidas do site.")
    ap.add_argument("--login", action="store_true", help="abre o navegador para você entrar na conta")
    ap.add_argument("--urls", help="arquivo com um endereço de partida por linha")
    ap.add_argument("--quando", default="hoje", choices=["hoje", "amanha"],
                    help="qual lista do site abrir (padrão: hoje)")
    ap.add_argument("--dia", help="força a pasta do dia, no formato 15-08-2026")
    ap.add_argument("--forcar", action="store_true", help="rebaixa mesmo se o arquivo já existir")
    args = ap.parse_args()

    cfg = carregar_config()

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("O Playwright não está instalado. Rode:\n"
              "  pip install playwright\n"
              "  python3 -m playwright install chromium")
        return 1

    if args.login:
        return fazer_login(cfg)

    if not SESSAO.exists():
        print("Você ainda não entrou na sua conta. Rode primeiro:\n"
              "  python3 baixar_pdfs.py --login")
        return 1

    urls = coletar_urls(cfg, args.dia, args.urls, args.quando)
    if not urls:
        return 1
    print(f"{len(urls)} partida(s) para baixar.\n")

    t0 = time.time()
    salvos, pulados, falhas = baixar(urls, cfg, args.dia, args.forcar)

    print(f"\n{len(salvos)} baixado(s), {pulados} já existia(m), {len(falhas)} falha(s) "
          f"({time.time()-t0:.0f}s)")
    for f in falhas:
        print(f"  !! {f}")
    if falhas and not salvos:
        print("\nSe todas falharam, provavelmente a sessão expirou. "
              "Rode `python3 baixar_pdfs.py --login` de novo.")
    if salvos:
        print("\nAgora rode:  python3 publicar.py --push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
