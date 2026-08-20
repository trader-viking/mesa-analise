#!/usr/bin/env python3
"""
Mesa de Análise — comando único de publicação.

    python3 publicar.py              analisa os PDFs e gera o site
    python3 publicar.py --push       gera o site e publica no GitHub
    python3 publicar.py --dia 15-08-2026    processa só um dia
    python3 publicar.py --sem-cache  reprocessa PDFs já lidos

Estrutura esperada dos PDFs (a mesma que você já usa):

    pdfs/
      15-08-2026/
        Brasileirão/
          004_16h00_Grêmio_x_São_Paulo.pdf
        Premier League/
          001_11h00_Arsenal_x_Everton.pdf

Os PDFs ficam de fora do repositório (veja .gitignore). O que vai para o
GitHub é só a pasta `site/`, com poucos KB por dia.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "analise"))

import leitor_pdf  # noqa: E402
import motor  # noqa: E402
import relatorio  # noqa: E402

PDFS = RAIZ / "pdfs"
SITE = RAIZ / "site"
CACHE = RAIZ / ".cache"
CRITERIOS = RAIZ / "analise" / "criterios.json"


def carregar_criterios():
    if CRITERIOS.exists():
        return json.loads(CRITERIOS.read_text(encoding="utf-8"))
    return {}


def varrer(dia_filtro=None):
    """Devolve {data: [(caminho, liga)]} a partir de pdfs/<data>/<liga>/*.pdf."""
    if not PDFS.exists():
        return {}
    dias: dict[str, list] = {}
    for pdf in sorted(PDFS.rglob("*.pdf")):
        rel = pdf.relative_to(PDFS).parts
        if len(rel) >= 3:
            data, liga = rel[0], rel[-2]
        elif len(rel) == 2:
            data, liga = rel[0], None
        else:
            data, liga = "sem-data", None
        if dia_filtro and data != dia_filtro:
            continue
        dias.setdefault(data, []).append((pdf, liga))
    return dias


def ler_com_cache(pdf: Path, usar_cache=True):
    """Ler 71 páginas leva alguns segundos; o cache evita reprocessar."""
    CACHE.mkdir(exist_ok=True)
    chave = CACHE / (str(pdf.relative_to(PDFS)).replace("/", "__") + ".json")
    if usar_cache and chave.exists() and chave.stat().st_mtime >= pdf.stat().st_mtime:
        return json.loads(chave.read_text(encoding="utf-8"))
    jogo = leitor_pdf.ler_pdf(pdf)
    if jogo:
        chave.write_text(json.dumps(jogo, ensure_ascii=False), encoding="utf-8")
    return jogo


def processar(dia_filtro=None, usar_cache=True):
    cfg = carregar_criterios()
    dias = varrer(dia_filtro)
    if not dias:
        print(f"Nenhum PDF encontrado em {PDFS}/. Estrutura esperada: pdfs/<data>/<liga>/arquivo.pdf")
        return []

    saida = []
    for data, arquivos in sorted(dias.items(), reverse=True):
        print(f"\n=== {data} — {len(arquivos)} PDF(s) ===")
        jogos, falhas = [], []
        t0 = time.time()
        for pdf, liga in arquivos:
            try:
                jogo = ler_com_cache(pdf, usar_cache)
            except Exception as exc:  # PDF corrompido, protegido, etc.
                falhas.append(f"{pdf.name}: {exc}")
                continue
            if not jogo:
                falhas.append(f"{pdf.name}: formato não reconhecido")
                continue
            if liga:
                jogo["liga"] = liga          # a pasta manda mais que o cabeçalho
                jogo.setdefault("origem", {})["liga"] = "pasta"
            jogos.append(jogo)
            print(f'  ok  {jogo["hora"]}  {jogo["casa"]} x {jogo["fora"]}'
                  + ("  [médias derivadas]" if jogo.get("derivado") else ""))
        for f in falhas:
            print(f"  !!  {f}")
        if not jogos:
            continue

        analise = motor.analisar({"config": cfg, "jogos": jogos})
        r = analise["resumo"]
        print(f'  → {r["entradas"]} entrada(s), {r["descartes"]} descartado(s), '
              f'exposição {r.get("exposicaoRiscoPct", 0):.1f}%  ({time.time()-t0:.1f}s)')
        saida.append({"data": data, "pasta": data, "analise": analise})
    return saida


def copiar_app():
    """Leva o aplicativo standalone junto, se ele estiver no repositório."""
    for nome in ("mesa-analise-trading.html", "app.html"):
        origem = RAIZ / nome
        if origem.exists():
            (SITE / "app.html").write_text(origem.read_text(encoding="utf-8"), encoding="utf-8")
            return True
    return False


def git(*args, checar=True):
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)
    if checar and r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)} falhou:\n{r.stderr.strip()}')
    return r.stdout.strip()


def publicar_no_github(mensagem):
    if not (RAIZ / ".git").exists():
        print("\nEste diretório ainda não é um repositório git. Rode os comandos do README.")
        return
    git("add", "site", "analise", "publicar.py", "README.md", checar=False)
    status = git("status", "--porcelain", "site", "analise")
    if not status:
        print("\nNada mudou desde a última publicação.")
        return
    git("commit", "-m", mensagem)
    git("push")
    print("\nPublicado. O GitHub Pages atualiza em 1 a 2 minutos.")


def main():
    ap = argparse.ArgumentParser(description="Analisa os PDFs e publica o site.")
    ap.add_argument("--push", action="store_true", help="commita e envia para o GitHub")
    ap.add_argument("--dia", help="processa só este dia (nome da pasta)")
    ap.add_argument("--sem-cache", action="store_true", help="reprocessa todos os PDFs")
    args = ap.parse_args()

    dias = processar(args.dia, usar_cache=not args.sem_cache)
    if not dias:
        return 1

    resumo = relatorio.escrever_site(SITE, dias)
    copiar_app()
    print(f'\nSite gerado em {SITE}/ — {len(resumo)} dia(s).')
    print(f'Abra {SITE / "index.html"} no navegador para conferir.')

    if args.push:
        publicar_no_github(f'Relatório de {", ".join(d["data"] for d in dias)}')
    else:
        print("\nRode com --push para publicar no GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
