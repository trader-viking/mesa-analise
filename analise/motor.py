#!/usr/bin/env python3
"""
Motor de análise dos métodos Back Favorito, Lay Zebra, Over Limite e Back 2x2.

Entrada : JSON com {"config": {...opcional...}, "jogos": [ {...}, ... ]}
Saída   : JSON com, para cada jogo, o modelo calculado, os métodos aprovados
          (com odd recomendada, EV, stake) e os motivos de bloqueio.

Uso:
    python3 analisar.py jogos.json > analise.json
    cat jogos.json | python3 analisar.py > analise.json

Todo o cálculo é determinístico. Nunca estime probabilidade, odd justa,
EV ou stake de cabeça — rode este script e use os números que ele devolver.
"""

import json
import math
import sys

# ----------------------------------------------------------------------------
# Configuração padrão — reflete os critérios operacionais em vigor.
# Qualquer chave pode ser sobrescrita pelo bloco "config" do JSON de entrada.
# ----------------------------------------------------------------------------
CFG_PADRAO = {
    "geral": {
        "banca": 1000.0,
        "comissao": 6.5,          # % da exchange
        "kelly": 0.25,            # fração de Kelly
        "stakeMax": 3.0,          # % da banca
        "stakeMin": 0.5,
        "evMin": 3.0,             # margem para mercados secundários
        "confMin": 45.0,
        "pesoMercado": 0.50,      # peso das odds no blend com o modelo
        "pesoMercadoDerivado": 0.75,  # quando as médias vêm dos últimos jogos
        "fatorMando": 1.12,
        "maxEntradas": 0,
        "exigirValor": False,     # True = só lista se a odd do PDF já tiver valor
        "permitirEstimativa": True,
        "marca": "",              # @ do dono, vira marca d'água nas imagens
    },
    "ligas": {"lista": ""},       # vazio = todas as ligas passam
    "faixas": {"superFav": 1.50, "favorito": 2.20, "parelho": 3.20},
    "BACK_FAV": {
        "on": True, "prioridade": 1, "probMin": 60.0,
        "exigirCasaOuSuperior": True, "superiorPPJ": 0.50, "superiorPos": 6,
        "aprovAdvMax": 40.0, "oddMin": 1.01, "oddMax": 3.00, "evMin": 3.0,
    },
    "LAY_ZEBRA": {
        "on": True, "prioridade": 2, "probMax": 20.0,
        "derrotas5Min": 3, "gsZebraMin": 2.0,
        "liabMax": 9.0, "oddMin": 1.01, "oddMax": 30.0, "evMin": 3.0,
    },
    "OVER": {
        "on": True, "prioridade": 3, "minutoGatilho": 65, "minutoFim": 70,
        "probMin": 55.0, "shareFinalMin": 30.0, "lambdaTotalMin": 2.60,
        "oddMin": 1.50, "evMin": 3.0,
    },
    "BACK22": {
        "on": True, "prioridade": 4, "over25Min": 60.0, "bttsMin": 60.0,
        "gsAmbosMin": 1.2, "evMin": 3.0, "mercado": "BTTS + Over 2.5",
    },
}

METODOS = {
    "BACK_FAV": "Back Favorito",
    "LAY_ZEBRA": "Lay Zebra",
    "OVER": "Over Limite",
    "BACK22": "Back 2x2",
}

FAIXAS = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 90)]
FAIXAS_ROT = ["0-15'", "16-30'", "31-45'", "46-60'", "61-75'", "76-90'"]
MOMENTO_PADRAO = [11.5, 14.5, 18.0, 17.0, 18.5, 20.5]


# ----------------------------------------------------------------------------
# utilitários
# ----------------------------------------------------------------------------
def num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def clamp(v, a, b):
    return max(a, min(b, v))


def poisson(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    logp = -lam + k * math.log(lam)
    for i in range(2, k + 1):
        logp -= math.log(i)
    return math.exp(logp)


def modelar(lc, lf, mx=9):
    pc = [poisson(i, lc) for i in range(mx + 1)]
    pf = [poisson(i, lf) for i in range(mx + 1)]
    p1 = px = p2 = btts = total = 0.0
    gols = [0.0] * (2 * mx + 1)
    placares = []
    for i in range(mx + 1):
        for j in range(mx + 1):
            p = pc[i] * pf[j]
            total += p
            if i > j:
                p1 += p
            elif i == j:
                px += p
            else:
                p2 += p
            if i > 0 and j > 0:
                btts += p
            gols[i + j] += p
            placares.append({"c": i, "f": j, "p": p})
    over = {}
    for L in (0.5, 1.5, 2.5, 3.5, 4.5):
        over[L] = sum(gols[g] for g in range(len(gols)) if g > L) / total
    placares.sort(key=lambda o: -o["p"])
    return {
        "p1": p1 / total, "px": px / total, "p2": p2 / total,
        "btts": btts / total, "over": over,
        "placares": [{"c": o["c"], "f": o["f"], "p": o["p"] / total} for o in placares[:6]],
        "lc": lc, "lf": lf, "lt": lc + lf,
    }


def desmargem(odds):
    inv = [1 / o if (o and o > 1) else None for o in odds]
    if any(v is None for v in inv):
        return None
    s = sum(inv)
    return {"probs": [v / s for v in inv], "overround": s - 1}


def inferir_lambdas(pm, p_over25=None):
    melhor = {"e": 1e9, "lc": 1.3, "lf": 1.1}

    def testar(lt, sup):
        lc, lf = (lt + sup) / 2, (lt - sup) / 2
        if lc < 0.05 or lf < 0.05:
            return
        M = modelar(lc, lf, 8)
        e = (M["p1"] - pm[0]) ** 2 + (M["px"] - pm[1]) ** 2 + (M["p2"] - pm[2]) ** 2
        if p_over25 is not None:
            e += 2 * (M["over"][2.5] - p_over25) ** 2
        if e < melhor["e"]:
            melhor.update({"e": e, "lc": lc, "lf": lf})

    lt = 1.4
    while lt <= 4.6:
        sup = -2.2
        while sup <= 2.2:
            testar(lt, sup)
            sup += 0.1
        lt += 0.1
    b_lt, b_sup = melhor["lc"] + melhor["lf"], melhor["lc"] - melhor["lf"]
    lt = max(0.6, b_lt - 0.15)
    while lt <= b_lt + 0.15:
        sup = b_sup - 0.15
        while sup <= b_sup + 0.15:
            testar(lt, sup)
            sup += 0.025
        lt += 0.025
    return melhor["lc"], melhor["lf"]


def share_janela(buckets, ini, fim):
    tot = sum(buckets) or 1.0
    s = 0.0
    for i, (a, z) in enumerate(FAIXAS):
        sob = max(0.0, min(z, fim) - max(a, ini))
        if sob > 0:
            s += buckets[i] * (sob / (z - a))
    return s / tot


def ler_forma(f):
    if not f:
        return None
    s = "".join(c for c in str(f).upper() if c in "VEDWLGP")
    if len(s) < 3:
        return None
    ingles = ("W" in s) or ("L" in s)
    mapa = {"W": 3, "D": 1, "L": 0} if ingles else {"V": 3, "E": 1, "D": 0, "G": 3, "P": 0}
    derrota = "L" if ingles else "D"
    pts = n = der = 0
    for c in s:
        if c not in mapa:
            continue
        n += 1
        pts += mapa[c]
        if c == derrota:
            der += 1
    if not n:
        return None
    return {"aprov": pts / (3 * n) * 100, "derrotas": der, "jogos": n, "seq": s}


def est_over25(gm, gs):
    L = gm + gs
    return (1 - math.exp(-L) * (1 + L + L * L / 2)) * 100


def est_btts(gm, gs):
    return (1 - math.exp(-gm)) * (1 - math.exp(-gs)) * 100


def odd_recomendada(p, ev_min, com):
    if p <= 0.0001:
        return 99.0
    return 1 + (ev_min / 100 + 1 - p) / (p * (1 - com))


def odd_max_lay(p, ev_min, com):
    if p <= 0.0001:
        return 99.0
    return 1 + ((1 - p) * (1 - com) - ev_min / 100) / p


def ev_back(p, odd, com):
    return p * (odd - 1) * (1 - com) - (1 - p)


def ev_lay(p, odd, com):
    return (1 - p) * (1 - com) - p * (odd - 1)


def kelly(p, odd, fracao, com):
    g = (odd - 1) * (1 - com)
    if g <= 0:
        return 0.0
    return max(0.0, ((p * g - (1 - p)) / g) * fracao)


ROTULOS_FAIXA = {"superFav": "Super Favorito", "favorito": "Favorito",
                 "parelho": "Parelho", "naoFav": "Não Favorito"}


def faixa_da_odd(odd, cortes):
    if odd is None:
        return None
    if odd <= cortes["superFav"]:
        return "superFav"
    if odd <= cortes["favorito"]:
        return "favorito"
    if odd <= cortes["parelho"]:
        return "parelho"
    return "naoFav"


def agrupar_por_faixa(jogos, cortes):
    out = {k: {"n": 0, "v": 0, "e": 0, "d": 0, "pts": 0, "aprov": None, "odds": []}
           for k in ROTULOS_FAIXA}
    for j in jogos or []:
        f = faixa_da_odd(j.get("odd"), cortes)
        if not f:
            continue
        b = out[f]
        b["n"] += 1
        b["odds"].append(j["odd"])
        if j["res"] == "V":
            b["v"] += 1; b["pts"] += 3
        elif j["res"] == "E":
            b["e"] += 1; b["pts"] += 1
        else:
            b["d"] += 1
    for b in out.values():
        if b["n"]:
            b["aprov"] = b["pts"] / (3 * b["n"]) * 100
    return out


def liga_permitida(liga, lista):
    itens = [x.strip().lower() for x in str(lista or "").replace(";", ",").replace("\n", ",").split(",") if x.strip()]
    if not itens:
        return True
    L = str(liga or "").strip().lower()
    if not L or L == "—":
        return False
    return any(x in L or L in x for x in itens)


# ----------------------------------------------------------------------------
# preparação do jogo
# ----------------------------------------------------------------------------
CHAVES_COMPLETUDE = ["gmCasa", "gsCasa", "gmFora", "gsFora", "ppjCasa", "ppjFora",
                     "oddCasa", "oddFora", "formaCasa", "formaFora",
                     "over25Casa", "bttsCasa", "momento"]


def preparar(j, cfg):
    G = cfg["geral"]
    A = {"j": j, "estimados": [], "bloqueios": []}

    dm = desmargem([num(j.get("oddCasa")), num(j.get("oddEmpate")), num(j.get("oddFora"))])
    A["mercado"] = ({"p1": dm["probs"][0], "px": dm["probs"][1], "p2": dm["probs"][2],
                     "overround": dm["overround"]} if dm else None)

    o25 = num(j.get("oddOver25"))
    u25 = num(j.get("oddUnder25"))
    if o25 and u25:
        p_over25 = (1 / o25) / ((1 / o25) + (1 / u25))
    elif o25:
        p_over25 = clamp(1 / o25 * 0.94, 0.02, 0.97)
    else:
        p_over25 = None

    gmC, gsC = num(j.get("gmCasa")), num(j.get("gsCasa"))
    gmF, gsF = num(j.get("gmFora")), num(j.get("gsFora"))
    xgC, xgF = num(j.get("xgCasa")), num(j.get("xgFora"))
    lc = lf = None
    fonte = None
    if None not in (gmC, gsC, gmF, gsF):
        lc = (gmC + gsF) / 2 * G["fatorMando"]
        lf = (gmF + gsC) / 2
        if xgC is not None and xgF is not None:
            lc, lf = (lc * 2 + xgC) / 3, (lf * 2 + xgF) / 3
        fonte = "estatísticas do PDF"
    elif xgC is not None and xgF is not None:
        lc, lf, fonte = xgC * G["fatorMando"], xgF, "xG do PDF"

    if A["mercado"]:
        ilc, ilf = inferir_lambdas([A["mercado"]["p1"], A["mercado"]["px"], A["mercado"]["p2"]], p_over25)
        if lc is None:
            lc, lf, fonte = ilc, ilf, "odds do PDF (λ inferido)"
        else:
            lc, lf = (lc + ilc) / 2, (lf + ilf) / 2
            fonte = (fonte or "") + " + odds"

    if lc is None or lf is None:
        A["erro"] = "Sem odds e sem médias de gols — impossível modelar."
        return A

    A["fonte"] = fonte
    A["lc"], A["lf"] = clamp(lc, 0.08, 5), clamp(lf, 0.08, 5)
    A["M"] = modelar(A["lc"], A["lf"])

    mom = j.get("momento")
    if isinstance(mom, list) and len(mom) == 6 and all(num(v) is not None for v in mom):
        A["momento"] = [num(v) for v in mom]
        A["momentoFonte"] = "tabela MOMENTO DOS GOLS do PDF"
    else:
        t1 = (num(j.get("g1tCasa")) or 0) + (num(j.get("g1tFora")) or 0)
        t2 = (num(j.get("g2tCasa")) or 0) + (num(j.get("g2tFora")) or 0)
        if t1 > 0 and t2 > 0:
            r1 = clamp(t1 / (t1 + t2), 0.25, 0.60)
            p1, p2 = MOMENTO_PADRAO[:3], MOMENTO_PADRAO[3:]
            s1, s2 = sum(p1), sum(p2)
            A["momento"] = [v / s1 * r1 * 100 for v in p1] + [v / s2 * (1 - r1) * 100 for v in p2]
            A["momentoFonte"] = "gols por tempo do PDF, distribuídos no padrão de 15 min"
        else:
            A["momento"] = list(MOMENTO_PADRAO)
            A["momentoFonte"] = "distribuição padrão do futebol (o PDF não trouxe a tabela)"
            A["estimados"].append("momento dos gols")

    A["r1"] = share_janela(A["momento"], 0, 45)
    A["l1t"] = A["M"]["lt"] * A["r1"]
    A["l2t"] = A["M"]["lt"] * (1 - A["r1"])
    A["pGol1t"] = 1 - math.exp(-A["l1t"])
    A["pGol2t"] = 1 - math.exp(-A["l2t"])

    # médias tiradas de uma faixa de últimos jogos não corrigem a força do
    # adversário; nesse caso o mercado, que precifica contexto, pesa mais
    A["pesoUsado"] = clamp(G.get("pesoMercadoDerivado", G["pesoMercado"]), 0, 1) \
        if j.get("derivado") else clamp(G["pesoMercado"], 0, 1)
    w = A["pesoUsado"] if A["mercado"] else 0.0
    mp = A["mercado"] or {"p1": 0, "px": 0, "p2": 0}
    p1 = w * mp["p1"] + (1 - w) * A["M"]["p1"]
    px = w * mp["px"] + (1 - w) * A["M"]["px"]
    p2 = w * mp["p2"] + (1 - w) * A["M"]["p2"]
    s = p1 + px + p2
    A["p1"], A["px"], A["p2"] = p1 / s, px / s, p2 / s

    fC, fF = ler_forma(j.get("formaCasa")), ler_forma(j.get("formaFora"))
    A["formaCasa"], A["formaFora"] = fC, fF

    def aprov(dirn, forma, ppj):
        v = num(j.get("aprov" + dirn))
        if v is not None:
            return {"v": v, "src": "PDF"}
        if forma:
            return {"v": forma["aprov"], "src": "últimos %d do PDF" % forma["jogos"]}
        if ppj is not None and G["permitirEstimativa"]:
            return {"v": ppj / 3 * 100, "src": "estimado por pts/jogo"}
        return {"v": None, "src": None}

    def derr(dirn, forma, ppj):
        v = num(j.get("derr" + dirn))
        if v is not None:
            return {"v": v, "src": "PDF"}
        if forma:
            return {"v": forma["derrotas"], "src": "sequência " + forma["seq"]}
        if ppj is not None and G["permitirEstimativa"]:
            return {"v": round(clamp((1.6 - ppj) * 3.2, 0, 5)), "src": "estimado por pts/jogo"}
        return {"v": None, "src": None}

    ppjC, ppjF = num(j.get("ppjCasa")), num(j.get("ppjFora"))
    A["aprovCasa"], A["aprovFora"] = aprov("Casa", fC, ppjC), aprov("Fora", fF, ppjF)
    A["derrCasa"], A["derrFora"] = derr("Casa", fC, ppjC), derr("Fora", fF, ppjF)

    def pct_campo(chave, est_fn, dirn, gm, gs):
        v = num(j.get(chave + dirn))
        if v is not None:
            return {"v": v, "src": "PDF"}
        if gm is not None and gs is not None and G["permitirEstimativa"]:
            return {"v": est_fn(gm, gs), "src": "estimado pelas médias"}
        return {"v": None, "src": None}

    A["o25Casa"] = pct_campo("over25", est_over25, "Casa", gmC, gsC)
    A["o25Fora"] = pct_campo("over25", est_over25, "Fora", gmF, gsF)
    A["btCasa"] = pct_campo("btts", est_btts, "Casa", gmC, gsC)
    A["btFora"] = pct_campo("btts", est_btts, "Fora", gmF, gsF)
    # o visitante também é auditado: o critério de aproveitamento do Back Favorito
    # olha justamente o adversário, e um valor estimado ali muda a decisão
    for nome, oc, of_ in [("aproveitamento", A["aprovCasa"], A["aprovFora"]),
                          ("derrotas em 5", A["derrCasa"], A["derrFora"]),
                          ("over 2.5 por time", A["o25Casa"], A["o25Fora"]),
                          ("ambas marcam", A["btCasa"], A["btFora"])]:
        if any(o["src"] and "estimad" in o["src"] for o in (oc, of_)) and nome not in A["estimados"]:
            A["estimados"].append(nome)

    comp = sum(1 for k in CHAVES_COMPLETUDE if j.get(k) not in (None, "")) / len(CHAVES_COMPLETUDE)
    align = 1.0
    if A["mercado"]:
        align = 1 - clamp(abs(A["M"]["p1"] - A["mercado"]["p1"]) + abs(A["M"]["p2"] - A["mercado"]["p2"]), 0, 1)
    A["divergencia"] = abs(A["M"]["p1"] - A["mercado"]["p1"]) if A["mercado"] else None
    A["conf"] = clamp(100 * (0.5 * comp + 0.5 * align) * (1 if A["mercado"] else 0.78), 0, 97)

    oc, of_ = num(j.get("oddCasa")), num(j.get("oddFora"))
    casa_fav = (oc <= of_) if (A["mercado"] and oc and of_) else (A["p1"] >= A["p2"])
    pick = lambda c, f: c if casa_fav else f
    A["fav"] = {"lado": "casa" if casa_fav else "fora", "time": pick(j.get("casa"), j.get("fora")),
                "p": pick(A["p1"], A["p2"]), "odd": pick(oc, of_),
                "ppj": pick(ppjC, ppjF), "pos": pick(num(j.get("posCasa")), num(j.get("posFora"))),
                "gs": pick(gsC, gsF), "aprov": pick(A["aprovCasa"], A["aprovFora"]),
                "derr": pick(A["derrCasa"], A["derrFora"])}
    A["zeb"] = {"lado": "fora" if casa_fav else "casa", "time": pick(j.get("fora"), j.get("casa")),
                "p": pick(A["p2"], A["p1"]), "odd": pick(of_, oc),
                "ppj": pick(ppjF, ppjC), "pos": pick(num(j.get("posFora")), num(j.get("posCasa"))),
                "gs": pick(gsF, gsC), "aprov": pick(A["aprovFora"], A["aprovCasa"]),
                "derr": pick(A["derrFora"], A["derrCasa"])}
    A["dc"] = A["fav"]["p"] + A["px"]
    cortes = cfg.get("faixas", CFG_PADRAO["faixas"])
    A["cortes"] = cortes
    if j.get("historicoOdds"):
        A["faixasHist"] = agrupar_por_faixa(j["historicoOdds"], cortes)
        A["nHist"] = len(j["historicoOdds"])

    def faixa_de(odd):
        if odd is None or "faixasHist" not in A:
            return None
        f = faixa_da_odd(odd, cortes)
        return dict(A["faixasHist"][f], chave=f, nome=ROTULOS_FAIXA[f])

    A["fav"]["faixa"] = faixa_de(A["fav"]["odd"])
    A["zeb"]["faixa"] = faixa_de(A["zeb"]["odd"])
    A["ligaOk"] = liga_permitida(j.get("liga"), cfg["ligas"]["lista"])
    return A


# ----------------------------------------------------------------------------
# avaliação dos métodos
# ----------------------------------------------------------------------------
def avaliar(A, cfg):
    G = cfg["geral"]
    com = G["comissao"] / 100
    j = A["j"]
    ops = []

    if not A["ligaOk"]:
        A["bloqueios"].append('Liga "%s" fora da lista de ligas permitidas.' % j.get("liga"))
        return ops

    def montar(metodo, c, d):
        eh_lay = d["tipo"] == "lay"
        odd_rec = (odd_max_lay(d["pOcorrer"], c["evMin"], com) if eh_lay
                   else odd_recomendada(d["p"], c["evMin"], com))
        odd_uso = d.get("odd") or None
        if odd_uso is None:
            status = "SEM PREÇO"
        elif eh_lay:
            status = "VALOR" if odd_uso <= odd_rec else "AGUARDAR"
        else:
            status = "VALOR" if odd_uso >= odd_rec else "AGUARDAR"
        odd_op = odd_uso if status == "VALOR" else odd_rec

        ev = stake = liab = None
        if eh_lay:
            if odd_uso:
                ev = ev_lay(d["pOcorrer"], odd_uso, com)
            teto = c.get("liabMax", G["stakeMax"] * 3)
            o_eq = odd_op / (odd_op - 1)
            liab = min(kelly(1 - d["pOcorrer"], o_eq, G["kelly"], com) * 100, teto)
            stake = clamp(liab / (odd_op - 1), G["stakeMin"], G["stakeMax"])
            liab = stake * (odd_op - 1)
            if liab > teto:
                liab = teto
                stake = liab / (odd_op - 1)
        else:
            if odd_uso:
                ev = ev_back(d["p"], odd_uso, com)
            stake = clamp(kelly(d["p"], odd_op, G["kelly"], com) * 100, G["stakeMin"], G["stakeMax"])

        o = dict(d)
        if d.get("pSecundario"):
            o_sec = odd_recomendada(d["pSecundario"], G["evMin"], com)
        else:
            o_sec = None
        o.update({"oddRecSecundaria": o_sec,
                  "metodo": metodo, "nome": METODOS[metodo], "oddRec": odd_rec, "oddPdf": odd_uso,
                  "oddOperacional": odd_op, "ev": ev, "stake": stake, "liability": liab,
                  "status": status,
                  "temValor": (status == "VALOR") if G["exigirValor"] else True})
        return o

    # ---------------- BACK FAVORITO ----------------
    cF = cfg["BACK_FAV"]
    if cF["on"]:
        f, z = A["fav"], A["zeb"]
        m, ok = [], []
        if f["p"] * 100 < cF["probMin"]:
            m.append("vitória do favorito %.1f%% < %g%%" % (f["p"] * 100, cF["probMin"]))
        else:
            ok.append("prob. de vitória %.1f%% ≥ %g%%" % (f["p"] * 100, cF["probMin"]))
        if cF["exigirCasaOuSuperior"]:
            em_casa = f["lado"] == "casa"
            dppj = (f["ppj"] - z["ppj"]) if (f["ppj"] is not None and z["ppj"] is not None) else None
            dpos = (z["pos"] - f["pos"]) if (f["pos"] is not None and z["pos"] is not None) else None
            superior = (dppj is not None and dppj >= cF["superiorPPJ"]) or (dpos is not None and dpos >= cF["superiorPos"])
            if not em_casa and not superior:
                m.append("favorito joga fora e não é claramente superior")
            else:
                ok.append("favorito em casa" if em_casa else
                          "favorito superior na tabela (%s)" % (("+%.2f pts/jogo" % dppj) if dppj is not None else ("+%g posições" % dpos)))
        if z["aprov"]["v"] is None:
            m.append("aproveitamento recente do adversário não disponível")
        elif z["aprov"]["v"] >= cF["aprovAdvMax"]:
            m.append("aproveitamento do adversário %.0f%% ≥ %g%%" % (z["aprov"]["v"], cF["aprovAdvMax"]))
        else:
            ok.append("adversário com %.0f%% de aproveitamento (%s)" % (z["aprov"]["v"], z["aprov"]["src"]))
        if f["odd"] and not (cF["oddMin"] <= f["odd"] <= cF["oddMax"]):
            m.append("odd %.2f fora da guarda %g–%g" % (f["odd"], cF["oddMin"], cF["oddMax"]))
        if not m:
            ops.append(montar("BACK_FAV", cF, {
                "tipo": "back", "p": f["p"], "odd": f["odd"], "criterios": ok,
                "mercado": "Back %s (vitória)" % f["time"],
                "mercadoSecundario": "Dupla chance %s ou empate" % f["time"],
                "pSecundario": A["dc"]}))
        else:
            A["bloqueios"].append("Back Favorito: " + "; ".join(m))

    # ---------------- LAY ZEBRA ----------------
    cL = cfg["LAY_ZEBRA"]
    if cL["on"]:
        z = A["zeb"]
        m, ok = [], []
        if z["p"] * 100 > cL["probMax"]:
            m.append("vitória da zebra %.1f%% > %g%%" % (z["p"] * 100, cL["probMax"]))
        else:
            ok.append("prob. de vitória da zebra %.1f%% ≤ %g%%" % (z["p"] * 100, cL["probMax"]))
        ok_derr = z["derr"]["v"] is not None and z["derr"]["v"] >= cL["derrotas5Min"]
        ok_gs = z["gs"] is not None and z["gs"] >= cL["gsZebraMin"]
        if not ok_derr and not ok_gs:
            m.append("zebra não cumpre a fragilidade exigida (%s derrota(s) em 5, %s gols sofridos/jogo)"
                     % (z["derr"]["v"], ("%.2f" % z["gs"]) if z["gs"] is not None else "n/d"))
        else:
            if ok_derr:
                ok.append("%g derrotas nos últimos 5 (%s)" % (z["derr"]["v"], z["derr"]["src"]))
            if ok_gs:
                ok.append("sofre %.2f gols por jogo ≥ %g" % (z["gs"], cL["gsZebraMin"]))
        if z["odd"] and not (cL["oddMin"] <= z["odd"] <= cL["oddMax"]):
            m.append("odd %.2f fora da guarda %g–%g" % (z["odd"], cL["oddMin"], cL["oddMax"]))
        if not m:
            ops.append(montar("LAY_ZEBRA", cL, {
                "tipo": "lay", "p": 1 - z["p"], "pOcorrer": z["p"], "odd": z["odd"], "criterios": ok,
                "mercado": "Lay %s" % z["time"],
                "mercadoSecundario": "Proteção: back %s no intervalo se sair 0-0" % A["fav"]["time"],
                "pSecundario": None}))
        else:
            A["bloqueios"].append("Lay Zebra: " + "; ".join(m))

    # ---------------- OVER LIMITE (ao vivo) ----------------
    cO = cfg["OVER"]
    if cO["on"]:
        m, ok = [], []
        ini = int(clamp(cO["minutoGatilho"], 0, 89))
        fim_janela = int(cO["minutoFim"])
        share = share_janela(A["momento"], ini, 90)
        lam_jan = A["M"]["lt"] * share
        p_mais1 = 1 - math.exp(-lam_jan)
        lam_min = cO.get("lambdaTotalMin", 0)
        if lam_min > 0 and A["M"]["lt"] < lam_min:
            m.append("jogo travado: λ total %.2f abaixo de %g" % (A["M"]["lt"], lam_min))
        elif lam_min > 0:
            ok.append("λ total do jogo %.2f ≥ %g" % (A["M"]["lt"], lam_min))
        if share * 100 < cO["shareFinalMin"]:
            m.append("só %.1f%% dos gols saem após o minuto %d (mínimo %g%%)" % (share * 100, ini, cO["shareFinalMin"]))
        else:
            ok.append("%.1f%% dos gols do jogo saem após o minuto %d" % (share * 100, ini))
        if p_mais1 * 100 < cO["probMin"]:
            m.append("probabilidade de +1 gol na janela %.1f%% < %g%%" % (p_mais1 * 100, cO["probMin"]))
        else:
            ok.append("+1 gol entre %d' e 90': %.1f%%" % (ini, p_mais1 * 100))
        rec = odd_recomendada(p_mais1, cO["evMin"], com)
        if rec < cO["oddMin"]:
            m.append("odd justa ao vivo (%.2f) abaixo do mínimo de %g" % (rec, cO["oddMin"]))
        if not m:
            ops.append(montar("OVER", cO, {
                "tipo": "back", "p": p_mais1, "odd": None, "aoVivo": True, "criterios": ok,
                "janela": [ini, fim_janela], "shareJanela": share, "lambdaJanela": lam_jan,
                "mercado": "AO VIVO %d'-%d' · Over (gols atuais + 0.5)" % (ini, fim_janela),
                "mercadoSecundario": "Se o gol sair antes do gatilho, repetir a entrada na linha nova",
                "pSecundario": None}))
        else:
            A["bloqueios"].append("Over Limite: " + "; ".join(m))

    # ---------------- BACK 2x2 ----------------
    cB = cfg["BACK22"]
    if cB["on"]:
        m, ok = [], []
        o25 = ((A["o25Casa"]["v"] + A["o25Fora"]["v"]) / 2
               if (A["o25Casa"]["v"] is not None and A["o25Fora"]["v"] is not None) else None)
        bt = ((A["btCasa"]["v"] + A["btFora"]["v"]) / 2
              if (A["btCasa"]["v"] is not None and A["btFora"]["v"] is not None) else None)
        gsC, gsF = num(j.get("gsCasa")), num(j.get("gsFora"))
        if o25 is None:
            m.append("over 2.5 por time indisponível")
        elif o25 < cB["over25Min"]:
            m.append("over 2.5 médio %.0f%% < %g%%" % (o25, cB["over25Min"]))
        else:
            ok.append("over 2.5 médio dos dois times %.0f%% (%s)" % (o25, A["o25Casa"]["src"]))
        if bt is None:
            m.append("ambas marcam por time indisponível")
        elif bt < cB["bttsMin"]:
            m.append("ambas marcam médio %.0f%% < %g%%" % (bt, cB["bttsMin"]))
        else:
            ok.append("ambas marcam médio %.0f%%" % bt)
        if gsC is None or gsF is None:
            m.append("gols sofridos indisponíveis")
        elif gsC < cB["gsAmbosMin"] or gsF < cB["gsAmbosMin"]:
            m.append("defesas não sofrem o bastante (%.2f e %.2f, mínimo %g nos dois)" % (gsC, gsF, cB["gsAmbosMin"]))
        else:
            ok.append("as duas defesas sofrem ≥ %g (%.2f e %.2f)" % (cB["gsAmbosMin"], gsC, gsF))
        if not m:
            mk = cB.get("mercado", "BTTS + Over 2.5")
            p22 = poisson(2, A["lc"]) * poisson(2, A["lf"])
            probs = {
                "BTTS + Over 2.5": A["M"]["btts"] - poisson(1, A["lc"]) * poisson(1, A["lf"]),
                "Ambas Marcam": A["M"]["btts"],
                "Over 2.5": A["M"]["over"][2.5],
                "Placar exato 2-2": p22,
            }
            p = clamp(probs.get(mk, A["M"]["btts"]), 0.005, 0.99)
            odd_mk = (num(j.get("oddBtts")) if mk == "Ambas Marcam"
                      else num(j.get("oddOver25")) if mk == "Over 2.5" else None)
            ops.append(montar("BACK22", cB, {
                "tipo": "back", "p": p, "odd": odd_mk, "criterios": ok,
                "p22": p22, "over25Medio": o25, "bttsMedio": bt,
                "mercado": "%s (%.1f%%)" % (mk, p * 100),
                "mercadoSecundario": "Placar 2-2 exato: %.1f%% · Ambas marcam: %.1f%%" % (p22 * 100, A["M"]["btts"] * 100),
                "pSecundario": A["M"]["btts"]}))
        else:
            A["bloqueios"].append("Back 2x2: " + "; ".join(m))

    return ops


# ----------------------------------------------------------------------------
# pipeline
# ----------------------------------------------------------------------------
def fundir_cfg(base, extra):
    out = json.loads(json.dumps(base))
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and k in out:
            out[k].update(v)
        else:
            out[k] = v
    return out


def analisar(entrada):
    cfg = fundir_cfg(CFG_PADRAO, entrada.get("config"))
    G = cfg["geral"]
    entradas, descartes = [], []

    for j in entrada.get("jogos", []):
        A = preparar(j, cfg)
        if A.get("erro"):
            descartes.append({"jogo": rotulo(j), "hora": j.get("hora"), "liga": j.get("liga"),
                              "motivo": A["erro"], "confianca": None})
            continue
        ops = [o for o in avaliar(A, cfg) if o["temValor"] and o["stake"] > 0]
        if not ops:
            motivo = " · ".join(A["bloqueios"]) if A["bloqueios"] else "Nenhum método atingiu os critérios configurados."
            descartes.append({"jogo": rotulo(j), "hora": j.get("hora"), "liga": j.get("liga"),
                              "motivo": motivo, "confianca": round(A["conf"])})
            continue
        if A["conf"] < G["confMin"]:
            descartes.append({"jogo": rotulo(j), "hora": j.get("hora"), "liga": j.get("liga"),
                              "motivo": "Confiança de %.0f%% abaixo do mínimo de %g%% — dados incompletos no PDF."
                                        % (A["conf"], G["confMin"]),
                              "confianca": round(A["conf"])})
            continue
        A["cfgOver"] = cfg["OVER"]
        ops.sort(key=lambda o: (0 if o["status"] == "VALOR" else 1,
                                cfg[o["metodo"]]["prioridade"],
                                -(o["ev"] if o["ev"] is not None else -9)))
        entradas.append(montar_saida(A, ops))

    if G["maxEntradas"] > 0:
        entradas.sort(key=lambda e: -(e["principal"]["ev"] or 0))
        for e in entradas[G["maxEntradas"]:]:
            descartes.append({"jogo": e["jogo"], "hora": e["hora"], "liga": e["liga"],
                              "motivo": "Fora do limite diário de %d entradas (ranqueado por EV)." % G["maxEntradas"],
                              "confianca": e["confianca"]})
        entradas = entradas[:G["maxEntradas"]]

    entradas.sort(key=lambda e: str(e["hora"]))
    return {"config": cfg, "entradas": entradas, "descartes": descartes,
            "resumo": {"jogos": len(entrada.get("jogos", [])),
                       "entradas": len(entradas), "descartes": len(descartes),
                       "exposicaoTotalPct": round(sum(e["principal"]["stake"] for e in entradas), 2),
                       "exposicaoRiscoPct": round(sum((e["principal"]["liability"] or e["principal"]["stake"])
                                                      for e in entradas), 2)}}


def rotulo(j):
    return "%s x %s" % (j.get("casa"), j.get("fora"))


def montar_saida(A, ops):
    j, M = A["j"], A["M"]
    tot_mom = sum(A["momento"]) or 1
    gat = int(A["cfgOver"]["minutoGatilho"])
    return {
        "jogo": rotulo(j), "hora": j.get("hora"), "liga": j.get("liga"),
        "casa": j.get("casa"), "fora": j.get("fora"),
        "confianca": round(A["conf"]),
        "camposEstimados": A["estimados"],
        "fonteModelo": A["fonte"],
        "modelo": {
            "lambdaCasa": round(A["lc"], 3), "lambdaFora": round(A["lf"], 3),
            "lambdaTotal": round(M["lt"], 3),
            "prob1x2Modelo": [round(M["p1"], 4), round(M["px"], 4), round(M["p2"], 4)],
            "prob1x2Mercado": ([round(A["mercado"]["p1"], 4), round(A["mercado"]["px"], 4),
                                round(A["mercado"]["p2"], 4)] if A["mercado"] else None),
            "prob1x2Final": [round(A["p1"], 4), round(A["px"], 4), round(A["p2"], 4)],
            "overround": round(A["mercado"]["overround"], 4) if A["mercado"] else None,
            "divergenciaMandantePP": round(A["divergencia"] * 100, 2) if A["divergencia"] is not None else None,
            "btts": round(M["btts"], 4),
            "over": {str(k): round(v, 4) for k, v in M["over"].items()},
            "placares": [{"placar": "%d-%d" % (p["c"], p["f"]), "prob": round(p["p"], 4)} for p in M["placares"][:5]],
            "cleanSheetCasa": round(math.exp(-A["lf"]), 4),
            "cleanSheetFora": round(math.exp(-A["lc"]), 4),
        },
        "tempos": {
            "lambda1T": round(A["l1t"], 3), "lambda2T": round(A["l2t"], 3),
            "probGol1T": round(A["pGol1t"], 4), "probGol2T": round(A["pGol2t"], 4),
            "pctGols1T": round(A["r1"] * 100, 1), "pctGols2T": round((1 - A["r1"]) * 100, 1),
        },
        "momentoDosGols": {
            "fonte": A["momentoFonte"],
            "faixas": [{"faixa": FAIXAS_ROT[i], "pctGols": round(A["momento"][i] / tot_mom * 100, 1),
                        "golsEsperados": round(M["lt"] * A["momento"][i] / tot_mom, 3)}
                       for i in range(6)],
            "pctApos65": round(share_janela(A["momento"], gat, 90) * 100, 1),
        },
        "forma": {
            "casa": A["formaCasa"]["seq"] if A["formaCasa"] else None,
            "fora": A["formaFora"]["seq"] if A["formaFora"] else None,
            "aproveitamentoCasa": round(A["aprovCasa"]["v"], 1) if A["aprovCasa"]["v"] is not None else None,
            "aproveitamentoFora": round(A["aprovFora"]["v"], 1) if A["aprovFora"]["v"] is not None else None,
            "fonteAproveitamento": A["aprovCasa"]["src"],
        },
        "jogadoresCasa": j.get("jogadoresCasa"), "jogadoresFora": j.get("jogadoresFora"),
        "desfalques": j.get("desfalques"),
        "principal": limpar(ops[0]),
        "metodos": [limpar(o) for o in ops],
        "motivoCurto": motivo_curto(A, ops[0]),
        "motivoBase": motivo_base(A, ops[0]),
        "seguir": seguir_live(A, ops[0]),
        "descartar": descartar_live(A, ops[0]),
        "entrada": texto_entrada(A, ops[0]),
        "saida": texto_saida(A, ops[0]),
        "aoVivo": bool(ops[0].get("aoVivo")),
        "camposEstimados": A["estimados"],
        "derivado": bool(j.get("derivado")),
        "pesoMercado": round(A.get("pesoUsado", 0), 2),
        "faixasFavoritismo": ({k: v for k, v in A["faixasHist"].items() if v["n"]}
                              if A.get("faixasHist") else None),
        "faixaHoje": ({"time": A["fav"]["time"], "odd": A["fav"]["odd"],
                       "nome": A["fav"]["faixa"]["nome"], "v": A["fav"]["faixa"]["v"],
                       "e": A["fav"]["faixa"]["e"], "d": A["fav"]["faixa"]["d"],
                       "n": A["fav"]["faixa"]["n"]} if A["fav"].get("faixa") else None),
        "escudos": j.get("escudos"),
        "oddsPre": j.get("oddsPre"),
        "h2h": j.get("h2h"),
        "ultimosCasa": j.get("faixaCasa"),
        "ultimosFora": j.get("faixaFora"),
    }


def limpar(o):
    saida = {}
    for k, v in o.items():
        if k in ("temValor", "tipo"):
            continue
        saida[k] = round(v, 4) if isinstance(v, float) else v
    saida["tipo"] = o["tipo"]
    return saida


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            entrada = json.load(fh)
    else:
        entrada = json.load(sys.stdin)
    json.dump(analisar(entrada), sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()


# ----------------------------------------------------------------------------
# Textos operacionais — mesmos do aplicativo, para que os dois digam a mesma coisa
# ----------------------------------------------------------------------------
def texto_entrada(A, o):
    m = o["metodo"]
    if m == "BACK_FAV":
        return (f'Pré-live, até 15 min antes da bola rolar, com odd ≥ {o["oddRec"]:.2f}. '
                "Se o preço estiver abaixo disso, migre para o ao vivo: entre entre 10' e 20' "
                "com 0-0, quando a odd do favorito costuma inflar 12–20%.")
    if m == "LAY_ZEBRA":
        return ("Lay pré-live na abertura do mercado, quando a odd da zebra está mais alta e a "
                "liquidez ainda é boa. Alternativa ao vivo: entre aos 15'–25' com 0-0.")
    if m == "OVER":
        return (f'Só ao vivo. Deixe o jogo correr e monte a entrada entre {o["janela"][0]}\' e '
                f'{o["janela"][1]}\': olhe o placar, entre em Over (gols atuais + 0.5) com odd ≥ '
                f'{o["oddRec"]:.2f}. Confirme antes que o jogo esteja com pressão real.')
    if m == "BACK22":
        return (f'Pré-live com odd ≥ {o["oddRec"]:.2f}. Se preferir preço melhor, espere o ao vivo '
                "até os 25' com 0-0 — a odd sobe sem que o cenário do jogo tenha mudado.")
    return "—"


def texto_saida(A, o):
    m = o["metodo"]
    if m == "BACK_FAV":
        return ("Green: gol do favorito → cashout de 60–70% e deixe o resto correr até o 2º gol. "
                "Stop: gol da zebra a qualquer momento, ou 0-0 aos 65'.")
    if m == "LAY_ZEBRA":
        return ("Green: 1-0 para o favorito a partir dos 55' → cashout total. Stop obrigatório: "
                "gol da zebra, ou 0-0 aos 70'.")
    if m == "OVER":
        return ("Green no gol seguinte — encerre a posição inteira. Stop: 85' sem gol → saia com o "
                "que restar. Nunca leve essa entrada até o apito final.")
    if m == "BACK22":
        return ("Green quando o cenário se confirmar. Cashout parcial em 1-1 aos 60'. "
                "Stop: 0-0 aos 60'.")
    return "—"


def seguir_live(A, o):
    f, z = A["fav"]["time"], A["zeb"]["time"]
    m = o["metodo"]
    if m == "BACK_FAV":
        return (f"{f} com o jogo no campo do adversário nos primeiros 15' — duas finalizações ou "
                f"dois escanteios a favor. {z} recuado, sem sair em transição. Se o gol do favorito "
                "sair até os 30', deixe correr.")
    if m == "LAY_ZEBRA":
        return (f"{z} inteiro atrás da linha da bola, sem chegar ao ataque nos primeiros 20'. "
                f"{f} com posse alta e pressão constante. Odd da zebra subindo com 0-0 melhora a posição.")
    if m == "OVER":
        return (f'No minuto {o["janela"][0]}, o jogo precisa estar vivo: 8+ finalizações somadas, '
                "escanteios saindo, e pelo menos um dos times precisando do resultado. "
                "Substituições ofensivas já feitas são o melhor sinal.")
    if m == "BACK22":
        return ("Os dois times chegando: uma chance clara para cada lado até os 30', linhas altas e "
                "espaço entre defesa e meio. Gol cedo de qualquer um confirma o cenário.")
    return "—"


def descartar_live(A, o):
    f, z = A["fav"]["time"], A["zeb"]["time"]
    m = o["metodo"]
    if m == "BACK_FAV":
        return (f"Gol de {z} a qualquer momento. Expulsão no {f}. 0-0 aos 35' com o favorito sem "
                "finalização no alvo. Zebra criando duas chances claras em contra-ataque.")
    if m == "LAY_ZEBRA":
        return (f"Gol de {z} — a liability dispara e não se recupera. Expulsão ou lesão de peça-chave "
                f"no {f} antes dos 30'. Zebra com duas chances claras até os 25'.")
    if m == "OVER":
        return ("Jogo travado no gatilho: menos de 6 finalizações somadas, muito tempo perdido, faltas "
                "seguidas. Placar que serve aos dois lados. Expulsão que faz um time só administrar. "
                "Nesses casos, não monte — pule a partida.")
    if m == "BACK22":
        return ("0-0 aos 40' com poucas finalizações. Um time abre 2-0 e passa a administrar. "
                "Expulsão que fecha o jogo. Goleiro em noite inspirada segurando o placar.")
    return "—"


def motivo_curto(A, o, so_base=False):
    j = A["j"]
    alertas = []
    if A.get("divergencia") is not None and A["divergencia"] > 0.10:
        alertas.append(f'divergência de {A["divergencia"]*100:.0f} p.p. com o mercado')
    if j.get("derivado"):
        alertas.append("médias vindas dos últimos jogos")
    if A["estimados"]:
        alertas.append(f'{len(A["estimados"])} campo(s) estimado(s)')
    sufixo = f' ({"; ".join(alertas)})' if alertas else ""

    m = o["metodo"]
    if m == "BACK_FAV":
        cond = next((c for c in o["criterios"] if "casa" in c or "superior" in c), "")
        base = (f'{A["fav"]["time"]} vence em {A["fav"]["p"]*100:.0f}% dos cenários '
                f'(odd justa {1/A["fav"]["p"]:.2f}). '
                f'Adversário com {A["zeb"]["aprov"]["v"]:.0f}% de aproveitamento recente'
                + (f", {cond}." if cond else "."))
    elif m == "LAY_ZEBRA":
        frag = " e ".join(c for c in o["criterios"] if "derrota" in c or "sofre" in c) or "fragilidade confirmada"
        base = (f'{A["zeb"]["time"]} vence em apenas {A["zeb"]["p"]*100:.0f}% — {frag}. '
                f'Liability de {o["liability"]:.2f}% da banca.')
    elif m == "OVER":
        base = (f'Jogo de {A["M"]["lt"]:.2f} gols esperados, com {o["shareJanela"]*100:.0f}% deles '
                f'saindo depois do minuto {o["janela"][0]}. '
                f'Chance de mais um gol na janela: {o["p"]*100:.0f}%.')
    elif m == "BACK22":
        base = (f'Over 2.5 médio de {o["over25Medio"]:.0f}% e ambas marcam {o["bttsMedio"]:.0f}%, '
                f'com as duas defesas sofrendo {num(j.get("gsCasa")):.2f} e {num(j.get("gsFora")):.2f} '
                "gols por jogo.")
    else:
        base = "—"
    return (base + sufixo) if not so_base else base


def motivo_base(A, o):
    """A motivação sem os alertas entre parênteses — é o que vai na capa."""
    return motivo_curto(A, o, so_base=True)
