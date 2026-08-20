"""
Leitura dos relatórios de partida em PDF (1 arquivo = 1 jogo).

Formato esperado: exportação do site com as abas
Geral · Odds · H2H · Desempenho · Gols · Cartões · Escanteios · Jogadores,
com dezenas de páginas repetidas.

Saída: dicionário no esquema que `motor.py` consome.
"""

from __future__ import annotations

import logging
import re
import unicodedata

import pdfplumber

# o PDF traz fontes sem FontBBox; o aviso é inofensivo e polui a saída
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# ícones da fonte do site ocupam a área privada do Unicode e colam no início
# das linhas de tabela, quebrando qualquer regex ancorada em ^
RX_ICONES = re.compile(r"[-�]")
# o nome do time às vezes cai na linha anterior, dependendo de onde o PDF
# quebra as coordenadas verticais — por isso ele é opcional aqui
RX_MANDO = re.compile(
    r"^\s*(?:(.{2,44}?)\s{2,})?(Casa|Fora|Total)\s{2,}(?:Competi[çc][ãa]o|Todas|Todos)\s*$"
)
RX_DATA = re.compile(r"^\d{2}/\d{2}/\d{2,4}$")
FAIXAS_MOMENTO = [(0, 15), (16, 30), (31, 45), (46, 60), (61, 75), (76, 90)]
ROTULOS_NAO_ODD = re.compile(
    r"gols?|chutes?|m[ée]dia|pontos?|posse|posi[çc]|cart|escanteio|xg|jogos?|"
    r"aproveitamento|venceu|perdeu|empatou|marcou|sofreu|total",
    re.I,
)


# ---------------------------------------------------------------- utilidades
def num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ------------------------------------------------------- extração posicional
def pagina_para_texto(page) -> str:
    """Reconstrói as linhas usando as coordenadas das palavras.

    Um espaço simples separa palavras; dois espaços marcam troca de coluna.
    O limiar é relativo à largura média do caractere, então funciona em
    qualquer corpo de fonte.
    """
    linhas: dict[int, list] = {}
    for p in page.extract_words(use_text_flow=False, keep_blank_chars=False):
        linhas.setdefault(round(p["top"] / 2.2), []).append(p)

    saida = []
    for y in sorted(linhas):
        itens = sorted(linhas[y], key=lambda p: p["x0"])
        out, prev, prev_w = "", None, 5.0
        for it in itens:
            larg = (it["x1"] - it["x0"]) / max(1, len(it["text"]))
            if prev is not None:
                gap = it["x0"] - prev
                if gap > 1.6 * prev_w:
                    out += "  "
                elif gap > 0.22 * prev_w:
                    out += " "
            out += it["text"]
            prev, prev_w = it["x1"], larg
        out = RX_ICONES.sub(" ", out)
        out = re.sub(r"[ ]{3,}", "  ", out).strip()
        if out:
            saida.append(out)
    return "\n".join(saida)


def pdf_para_texto(caminho) -> str:
    with pdfplumber.open(caminho) as pdf:
        paginas = [pagina_para_texto(p) for p in pdf.pages]
    return "\n\n──── PÁGINA ────\n\n".join(paginas)


def eh_relatorio_partida(txt: str) -> bool:
    pontos = 0
    for rx in (
        r"Confronto\s*Direto",
        r"Principais\s*Mercados",
        r"Geral\s+Odds\s+H2H",
        r"Tend[êe]ncias",
    ):
        if re.search(rx, txt, re.I):
            pontos += 1
    if re.search(r"Aproveitamento", txt, re.I) and re.search(r"Pontos\s+por\s+Jogo", txt, re.I):
        pontos += 1
    return pontos >= 2


# ----------------------------------------------------------- cabeçalho/times
def _nome_acima(linhas, i):
    """Quando a linha de mando vem sem o nome, ele está logo acima."""
    for k in range(i - 1, max(-1, i - 4), -1):
        c = (linhas[k] or "").strip()
        if not c or re.match(r"^[\d\s.,%()\-]+$", c):
            continue
        if RX_MANDO.match(c) or len(c) > 44 or not re.search(r"[A-Za-zÀ-ÿ]{3}", c):
            return None
        return c
    return None


def times_do_relatorio(linhas, arquivo):
    achados = []
    for i, l in enumerate(linhas):
        m = RX_MANDO.match(l)
        if not m:
            continue
        nome = (m.group(1) or "").strip() or _nome_acima(linhas, i)
        if not nome:
            continue
        achados.append({"time": nome, "mando": m.group(2), "linha": i})

    m_arq = re.search(r"(?:\d+_)?\d{1,2}h\d{2}_(.+?)_x_(.+?)\.pdf$", str(arquivo or ""), re.I)
    if len(achados) >= 2:
        casa = next((a for a in achados if a["mando"] == "Casa"), achados[0])
        fora = next((a for a in achados if a is not casa and a["time"] != casa["time"]), None)
        if fora is None:
            # o nome do visitante não sobreviveu à extração: pega do arquivo
            outra = next((a for a in achados if a is not casa and a["mando"] != casa["mando"]), achados[1])
            if m_arq:
                outra = dict(outra, time=m_arq.group(2).replace("_", " "))
            fora = outra
        return casa, fora
    # reserva: o nome do arquivo traz horário e times
    m = re.search(r"(?:\d+_)?(\d{1,2})h(\d{2})_(.+?)_x_(.+?)\.pdf$", str(arquivo or ""), re.I)
    if m:
        return ({"time": m.group(3).replace("_", " "), "mando": "Casa", "linha": -1},
                {"time": m.group(4).replace("_", " "), "mando": "Fora", "linha": -1})
    return None, None


# ------------------------------------------------- faixa dos últimos jogos
def ler_faixa_jogos(linhas, i_cabec):
    """Adversários → (AP) → placares → V/E/D. A ordem lida é do mais antigo
    para o mais recente, por isso invertemos no fim."""
    if i_cabec < 0:
        return None
    placares = resultados = None
    for k in range(i_cabec + 1, min(len(linhas), i_cabec + 8)):
        l = linhas[k]
        if RX_MANDO.match(l):
            break
        if placares is None:
            ps = re.findall(r"(\d{1,2})\s*-\s*(\d{1,2})", l)
            if len(ps) >= 3:
                placares = [(int(a), int(b)) for a, b in ps]
                continue
        elif resultados is None:
            rs = re.findall(r"\b[VED]\b", l)
            if len(rs) >= 3:
                resultados = rs
                break
    if not placares:
        return None
    jogos = []
    for i, (gf, ga) in enumerate(placares):
        res = resultados[i] if resultados and i < len(resultados) else None
        if not res:
            res = "V" if gf > ga else ("E" if gf == ga else "D")
        jogos.append({"gf": gf, "ga": ga, "res": res})
    jogos.reverse()
    return jogos


def orientar(jogos, sem_derrota=None, vitorias=None):
    """A ordem correta é a que reproduz as Tendências do próprio PDF."""
    def invicto(arr):
        n = 0
        for j in arr:
            if j["res"] == "D":
                break
            n += 1
        return n

    def vits(arr):
        n = 0
        for j in arr:
            if j["res"] != "V":
                break
            n += 1
        return n

    def nota(arr):
        s = 0
        if sem_derrota is not None and invicto(arr) == sem_derrota:
            s += 1
        if vitorias is not None and vits(arr) == vitorias:
            s += 1
        return s

    inv = list(reversed(jogos))
    return inv if nota(inv) > nota(jogos) else jogos


def stats_da_faixa(jogos):
    n = len(jogos)
    if not n:
        return None
    u5 = jogos[:5]
    pts5 = sum(3 if j["res"] == "V" else (1 if j["res"] == "E" else 0) for j in u5)
    return {
        "n": n,
        "gm": sum(j["gf"] for j in jogos) / n,
        "gs": sum(j["ga"] for j in jogos) / n,
        "over25": sum(1 for j in jogos if j["gf"] + j["ga"] > 2.5) / n * 100,
        "btts": sum(1 for j in jogos if j["gf"] > 0 and j["ga"] > 0) / n * 100,
        "ppj": sum(3 if j["res"] == "V" else (1 if j["res"] == "E" else 0) for j in jogos) / n,
        "forma": "".join(j["res"] for j in u5),
        "aprov": pts5 / (3 * len(u5)) * 100,
        "derrotas5": sum(1 for j in u5 if j["res"] == "D"),
        "placares": " ".join(f'{j["gf"]}-{j["ga"]}' for j in jogos),
    }


# --------------------------------------------------------- tabelas rotuladas
def par_do_relatorio(txt, rotulo, pct=False, trio=False, nao_zero=False):
    """`Rótulo  valor_casa  valor_fora`.

    Em campos percentuais o `%` é obrigatório: sem ele a linha de ODDS
    ("Over 2.5 Gols  1.60  2.30") seria lida como se fosse percentual.
    """
    suf = r"\s*%" if pct else ""
    extra = r"(?:\s{1,}-?[\d.,]+\s*%?)?" if trio else ""
    rx = re.compile(
        rf"^\s*{rotulo}\s{{1,}}(-?[\d.,]+){suf}\s{{1,}}(-?[\d.,]+){suf}{extra}\s*$",
        re.I | re.M,
    )
    m = rx.search(txt)
    if not m:
        return None, None
    a, b = num(m.group(1)), num(m.group(2))
    if a is None or b is None:
        return None, None
    if nao_zero and a == 0 and b == 0:
        return None, None
    return a, b


# ------------------------------------------------------- momento dos gols
def momento_do_relatorio(txt):
    """Linhas `0 - 15  M  S  x%  y%`, uma tabela por time. Somamos os gols
    marcados das tabelas distintas para obter o perfil do confronto."""
    linhas = txt.split("\n")
    blocos = []
    for i, l in enumerate(linhas):
        if not re.match(r"^\s*0\s*-\s*15\b", l):
            continue
        bloco, ok = [], True
        for ini, fim in FAIXAS_MOMENTO:
            alvo = re.compile(rf"^\s*{ini}\s*-\s*{fim}\s+(\d+)\s+(\d+)")
            achou = None
            for k in range(i, min(len(linhas), i + 14)):
                m = alvo.match(linhas[k])
                if m:
                    achou = (int(m.group(1)), int(m.group(2)))
                    break
            if not achou:
                ok = False
                break
            bloco.append(achou)
        if ok:
            blocos.append(bloco)
    if not blocos:
        return None
    vistos, unicos = set(), []
    for b in blocos:
        chave = "|".join(f"{x}/{y}" for x, y in b)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(b)
    soma = [0] * 6
    for b in unicos:
        for i, (marcado, _sofrido) in enumerate(b):
            soma[i] += marcado
    return soma if sum(soma) > 0 else None


# ------------------------------------------------------------- jogadores
def eh_nome_pessoa(s):
    s = (s or "").strip()
    if not s or len(s) < 5 or len(s) > 46:
        return False
    if re.search(r"[\d%/:]", s):
        return False
    if re.match(r"^(jogador|influentes|goleadores|ver todos|tend[êe]ncias|ambas|confronto|"
                r"resultado|over|under|primeiro|segundo)", s, re.I):
        return False
    return bool(re.match(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.'´\- ]+\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.'´\- ]+$", s))


def jogadores_do_relatorio(linhas, nome_time):
    alvo = re.sub(r"\s+", "", nome_time).lower()
    nomes, dentro = [], False
    for i, l in enumerate(linhas):
        t = l.strip()
        if re.match(r"^(Jogadores|Influentes\s+Goleadores|Jogador\s+[GJ]\b)", t, re.I):
            dentro = True
        elif re.match(r"^Ver todos os jogadores", t, re.I):
            dentro = False
        if not dentro or re.sub(r"\s+", "", t).lower() != alvo:
            continue
        for k in range(i - 1, max(-1, i - 4), -1):
            c = linhas[k].strip()
            if not c or re.match(r"^[\d\s.,%()\-]+$", c):
                continue
            if eh_nome_pessoa(c) and c not in nomes:
                nomes.append(c)
            break
    return ", ".join(nomes[:4]) or None


# ------------------------------------------- histórico com odds (aba H2H)
def historico_com_odds(texto, nome_casa, nome_fora):
    reg = re.search(r"(?:^|\n)\s*H2H[\s\S]{0,1600}?(?=Confronto\s*Direto|$)", texto, re.I)
    if not reg:
        return None
    blocos, atual = [], []
    for l in reg.group(0).split("\n"):
        t = l.strip()
        if not t:
            continue
        atual.append(t)
        if RX_DATA.match(t):
            blocos.append(atual)
            atual = []
    if not blocos:
        return None

    # "AP" é desenhado abaixo do placar, então cai no início do bloco seguinte
    for i in range(1, len(blocos)):
        if blocos[i] and blocos[i][0].strip().upper() == "AP":
            blocos[i].pop(0)
            blocos[i - 1].append("AP")

    alvo_casa, alvo_fora = sem_acento(nome_casa), sem_acento(nome_fora)
    jogos = []
    for bl in blocos:
        data = next((x.strip() for x in bl if RX_DATA.match(x.strip())), None)
        teve_ap = any(x.strip().upper() == "AP" for x in bl)
        odd = gc = gf = None
        nomes = []
        for l in bl:
            t = l.strip()
            if RX_DATA.match(t) or t.upper() == "AP":
                continue
            mo = re.search(r"(?:^|\s)(\d{1,3}[.,]\d{2})(?:\s|$)", t)
            mp = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})", t)
            if mo and odd is None:
                v = num(mo.group(1))
                if v and 1.01 <= v <= 200:
                    odd = v
            if mp and gc is None:
                gc, gf = int(mp.group(1)), int(mp.group(2))
            limpo = re.sub(r"\d{1,3}[.,]\d{2}", "", t)
            limpo = re.sub(r"\d{1,2}\s*-\s*\d{1,2}", "", limpo).strip()
            if (len(limpo) > 2 and re.search(r"[A-Za-zÀ-ÿ]{3}", limpo)
                    and not re.match(r"^(H2H|Liga|Partida|Press[ãa]o|Odd|Placar)$", limpo, re.I)):
                nomes.append(limpo)
        if odd is None or gc is None or not nomes:
            continue
        i_nosso = next((i for i, n in enumerate(nomes)
                        if sem_acento(n) in (alvo_casa, alvo_fora)), -1)
        if i_nosso < 0:
            continue
        somos_mandante = i_nosso == 0
        gp, gs = (gc, gf) if somos_mandante else (gf, gc)
        # placar com AP é o resultado após prorrogação; para o 1X2, que é o que
        # a odd daquele jogo precificava, o tempo normal terminou empatado
        res = "E" if teve_ap else ("V" if gp > gs else ("E" if gp == gs else "D"))
        jogos.append({"data": data, "odd": odd, "gp": gp, "gs": gs, "ap": teve_ap,
                      "mando": "C" if somos_mandante else "F", "res": res})
    return jogos or None


# ------------------------------------------------ todas as odds do pré-jogo
def todas_as_odds(texto):
    paginas = re.split(r"──── PÁGINA ────", texto)
    alvo = [p for p in paginas
            if re.search(r"Resultado\s*ao\s*Intervalo", p, re.I)
            or re.search(r"Mandante\s+Empate\s+Visitante", p, re.I)]
    if not alvo:
        return None
    odds = {}
    for l in "\n".join(alvo).split("\n"):
        m = re.match(r"^\s*(.{3,46}?)\s{1,}(\d{1,3}[.,]\d{2})"
                     r"(?:\s{1,}(\d{1,3}[.,]\d{2}))?(?:\s{1,}(\d{1,3}[.,]\d{2}))?\s*$", l)
        if not m:
            continue
        rot = m.group(1).strip()
        linha_de_gols = (re.match(r"^[\d.,]+\s*gols?$", rot, re.I)
                         or re.search(r"\b(over|under|mais de|menos de|handicap|asi[áa]tico)\b", rot, re.I))
        if not linha_de_gols and ROTULOS_NAO_ODD.search(rot):
            continue
        vals = [num(v) for v in (m.group(2), m.group(3), m.group(4)) if v]
        vals = [v for v in vals if v and 1.01 <= v <= 200]
        if vals and rot not in odds:
            odds[rot] = vals
    return odds or None


# ============================================================== parser principal
def analisar_relatorio(texto, arquivo=None):
    linhas = texto.split("\n")
    casa, fora = times_do_relatorio(linhas, arquivo)
    if not casa:
        return None

    j = {"arquivo": str(arquivo or ""), "casa": casa["time"], "fora": fora["time"],
         "formato": "relatorio", "origem": {}}

    def marcar(campo, src):
        j["origem"][campo] = src

    # ---- liga, horário, data ----
    m = re.search(r"^\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .']{2,24})\s*-\s*([^\n]{3,60})$", texto, re.M)
    j["liga"] = f"{m.group(1).strip()} - {m.group(2).strip()}" if m else "—"
    m_arq = re.search(r"(\d{1,2})h(\d{2})", str(arquivo or ""), re.I)
    m_hora = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", texto)
    if m_arq:
        j["hora"] = f"{m_arq.group(1).zfill(2)}:{m_arq.group(2)}"
    elif m_hora:
        j["hora"] = f"{m_hora.group(1).zfill(2)}:{m_hora.group(2)}"
    else:
        j["hora"] = "--:--"
    m = re.search(r"\b(\d{2}/\d{2})\s*-\s*[A-Za-zÀ-ÿ]", texto)
    if m:
        j["data"] = m.group(1)

    # ---- odds (a aba Odds é a fonte mais confiável) ----
    m = re.search(r"^\s*Resultado\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)\s*$", texto, re.M)
    if m:
        j["oddCasa"], j["oddEmpate"], j["oddFora"] = (num(m.group(1)), num(m.group(2)), num(m.group(3)))
        marcar("odds", "aba Odds")
    for rx, campos in [
        (r"Resultado\s*ao\s*Intervalo\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)",
         ("oddCasaHT", "oddEmpateHT", "oddForaHT")),
        (r"Resultado\s*no\s*2[ºo°]\s*Tempo\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)",
         ("oddCasa2T", "oddEmpate2T", "oddFora2T")),
    ]:
        mm = re.search(rx, texto, re.I)
        if mm:
            for campo, val in zip(campos, mm.groups()):
                j[campo] = num(val)
    m = re.search(r"^\s*(?:Over\s*)?2[.,]5\s*Gols\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)\s*$", texto, re.I | re.M)
    if m:
        j["oddOver25"], j["oddUnder25"] = num(m.group(1)), num(m.group(2))
        marcar("over25", "aba Odds")
    m = re.search(r"^\s*Ambas\s*Marcam\s{1,}(\d+[.,]\d+)\s{1,}(\d+[.,]\d+)\s*$", texto, re.I | re.M)
    if m:
        j["oddBtts"], j["oddNaoBtts"] = num(m.group(1)), num(m.group(2))

    # ---- tendências (orientam a faixa e servem de reserva) ----
    tend = {}
    bt = re.search(r"Tend[êe]ncias[\s\S]{0,700}", texto, re.I)
    if bt:
        b = bt.group(0)
        mm = re.search(r"Sem\s*derrota\s{1,}(\d+)", b, re.I)
        tend["sem_derrota"] = int(mm.group(1)) if mm else None
        mm = re.search(r"Vit[óo]rias\s{1,}(\d+)", b, re.I)
        tend["vitorias"] = int(mm.group(1)) if mm else None
        tend["over"] = [(int(a), int(c)) for a, c in
                        re.findall(r"Mais\s*de\s*2[.,]5\s*Gols\s{1,}(\d+)\s*/\s*(\d+)", b, re.I)]
        tend["ambas"] = [(int(a), int(c)) for a, c in
                         re.findall(r"Ambas\s*marcam\s{1,}(\d+)\s*/\s*(\d+)", b, re.I)]

    # ---- faixas dos últimos jogos ----
    f_casa = ler_faixa_jogos(linhas, casa["linha"])
    f_fora = ler_faixa_jogos(linhas, fora["linha"])
    s_casa = stats_da_faixa(orientar(f_casa, tend.get("sem_derrota"), None)) if f_casa else None
    s_fora = stats_da_faixa(orientar(f_fora, None, tend.get("vitorias"))) if f_fora else None
    j["faixaCasa"], j["faixaFora"] = s_casa, s_fora
    if s_casa:
        j["mandoFaixaCasa"] = casa["mando"]
    if s_fora:
        j["mandoFaixaFora"] = fora["mando"]

    # ---- tabelas agregadas (só valem quando não estão zeradas) ----
    jogos_c, jogos_f = par_do_relatorio(texto, "Total de Jogos")
    tem_agregado = (jogos_c or 0) > 0 or (jogos_f or 0) > 0

    def aplicar(campo_c, campo_f, par, fonte):
        if par[0] is None:
            return False
        j[campo_c], j[campo_f] = par
        marcar(campo_c, fonte)
        return True

    ok = False
    if tem_agregado:
        ok = aplicar("gmCasa", "gmFora",
                     par_do_relatorio(texto, "Gols Marcados", nao_zero=True), "tabela Aproveitamento")
        aplicar("gsCasa", "gsFora",
                par_do_relatorio(texto, "Gols Sofridos", nao_zero=True), "tabela Aproveitamento")
    if not ok:
        ok = aplicar("gmCasa", "gmFora",
                     par_do_relatorio(texto, r"M[ée]dia Gols Marcados", nao_zero=True), "aba Gols")
        aplicar("gsCasa", "gsFora",
                par_do_relatorio(texto, r"M[ée]dia Gols Sofridos", nao_zero=True), "aba Gols")
    if not ok and s_casa and s_fora:
        j["gmCasa"], j["gsCasa"] = s_casa["gm"], s_casa["gs"]
        j["gmFora"], j["gsFora"] = s_fora["gm"], s_fora["gs"]
        marcar("gmCasa", f'média dos últimos {s_casa["n"]} jogos')
        marcar("gsCasa", f'média dos últimos {s_casa["n"]} jogos')
        j["derivado"] = True

    if not aplicar("ppjCasa", "ppjFora",
                   par_do_relatorio(texto, "Pontos por Jogo", nao_zero=True), "tabela Aproveitamento"):
        if s_casa and s_fora:
            j["ppjCasa"], j["ppjFora"] = s_casa["ppj"], s_fora["ppj"]
            marcar("ppjCasa", f'últimos {s_casa["n"]} jogos')
    aplicar("posCasa", "posFora", par_do_relatorio(texto, r"Posi[çc][ãa]o"), "tabela Aproveitamento")

    if not aplicar("over25Casa", "over25Fora",
                   par_do_relatorio(texto, r"Over 2[.,]5 Gols", pct=True, trio=True, nao_zero=True), "aba Gols"):
        if len(tend.get("over") or []) >= 2:
            j["over25Casa"] = tend["over"][0][0] / tend["over"][0][1] * 100
            j["over25Fora"] = tend["over"][1][0] / tend["over"][1][1] * 100
            marcar("over25Casa", "Tendências (recorte recente)")
        elif s_casa and s_fora:
            j["over25Casa"], j["over25Fora"] = s_casa["over25"], s_fora["over25"]
            marcar("over25Casa", f'últimos {s_casa["n"]} jogos')

    if not aplicar("bttsCasa", "bttsFora",
                   par_do_relatorio(texto, "Ambas Marcam", pct=True, nao_zero=True), "tabela Aproveitamento"):
        if len(tend.get("ambas") or []) >= 2:
            j["bttsCasa"] = tend["ambas"][0][0] / tend["ambas"][0][1] * 100
            j["bttsFora"] = tend["ambas"][1][0] / tend["ambas"][1][1] * 100
            marcar("bttsCasa", "Tendências (recorte recente)")
        elif s_casa and s_fora:
            j["bttsCasa"], j["bttsFora"] = s_casa["btts"], s_fora["btts"]
            marcar("bttsCasa", f'últimos {s_casa["n"]} jogos')

    aplicar("xgCasa", "xgFora", par_do_relatorio(texto, "xG - A Favor", nao_zero=True), "aba Desempenho")
    aplicar("xgaCasa", "xgaFora", par_do_relatorio(texto, "xG - Contra", nao_zero=True), "aba Desempenho")

    if s_casa:
        j["formaCasa"], j["derrCasa"], j["aprovCasa"] = s_casa["forma"], s_casa["derrotas5"], s_casa["aprov"]
        marcar("formaCasa", f'últimos {min(5, s_casa["n"])} jogos')
    if s_fora:
        j["formaFora"], j["derrFora"], j["aprovFora"] = s_fora["forma"], s_fora["derrotas5"], s_fora["aprov"]

    mom = momento_do_relatorio(texto)
    if mom:
        j["momento"] = mom
        marcar("momento", "tabela Tempo/Marcado da aba Gols")

    h2h = re.search(r"Confronto\s*Direto[\s\S]{0,220}", texto, re.I)
    if h2h:
        b = h2h.group(0)
        v = re.search(r"Vit[óo]rias\s{1,}(\d+)", b, re.I)
        sd = re.search(r"Sem\s*derrota\s{1,}(\d+)", b, re.I)
        o = re.search(r"Mais\s*de\s*2[.,]5\s*Gols\s{1,}(\d+)\s*/\s*(\d+)", b, re.I)
        partes = [f"{v.group(1)} vitórias" if v else None,
                  f"{sd.group(1)} sem derrota" if sd else None,
                  f"over 2.5 em {o.group(1)}/{o.group(2)}" if o else None]
        j["h2h"] = " · ".join(p for p in partes if p) or None

    hist = historico_com_odds(texto, j["casa"], j["fora"])
    if hist:
        j["historicoOdds"] = hist
        marcar("historicoOdds", "aba H2H")

    odds_pre = todas_as_odds(texto)
    if odds_pre:
        j["oddsPre"] = odds_pre
        marcar("oddsPre", f"aba Odds ({len(odds_pre)} mercados)")

    j["jogadoresCasa"] = jogadores_do_relatorio(linhas, j["casa"])
    j["jogadoresFora"] = jogadores_do_relatorio(linhas, j["fora"])
    return j


def ler_pdf(caminho):
    """Lê um PDF de partida e devolve o dicionário do jogo (ou None)."""
    texto = pdf_para_texto(caminho)
    if not eh_relatorio_partida(texto):
        return None
    jogo = analisar_relatorio(texto, caminho)
    if jogo:
        esc = escudos_do_pdf(caminho)
        if esc:
            jogo["escudos"] = esc
            jogo.setdefault("origem", {})["escudos"] = "imagens da capa do PDF"
    return jogo


# ============================================================== escudos
# Os escudos vêm embutidos no PDF. Na primeira página, os dois maiores
# desenhos são os dos times do confronto: o da esquerda é o mandante.
def _imagens_da_capa(caminho):
    with pdfplumber.open(caminho) as pdf:
        if not pdf.pages:
            return []
        return [{"nome": im.get("name"), "x": im["x0"], "top": im["top"],
                 "w": im["width"], "h": im["height"]}
                for im in pdf.pages[0].images if im.get("name")]


def escudos_do_pdf(caminho, lado=72):
    """Devolve {'casa': <data URI png>, 'fora': ...} ou {} se não achar."""
    try:
        import io
        import base64
        import pypdf
        from PIL import Image
    except ImportError:
        return {}

    try:
        marcas = _imagens_da_capa(caminho)
        # a página também desenha faixas de fundo; o escudo é quadrado e pequeno
        cand = [m for m in marcas
                if 18 <= m["w"] <= 90 and abs(m["w"] - m["h"]) / max(m["w"], m["h"]) < 0.2]
        if len(cand) < 2:
            return {}
        maiores = sorted(cand, key=lambda m: -(m["w"] * m["h"]))[:2]
        casa, fora = sorted(maiores, key=lambda m: m["x"])

        leitor = pypdf.PdfReader(caminho)
        brutas = {im.name.rsplit(".", 1)[0]: im.data for im in leitor.pages[0].images}

        def png(marca):
            dados = brutas.get(str(marca["nome"]))
            if not dados:
                return None
            img = Image.open(io.BytesIO(dados)).convert("RGBA")
            img.thumbnail((lado, lado), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        return {k: v for k, v in (("casa", png(casa)), ("fora", png(fora))) if v}
    except Exception:
        return {}      # escudo é enfeite: nunca deve derrubar a análise
