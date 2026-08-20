#!/usr/bin/env python3
"""Verificações do motor. Roda sem dependências externas."""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "analise"))
import motor

falhas = []
def checar(nome, ok, detalhe=""):
    print(("  ok   " if ok else "  FALHA ") + nome + ("" if ok else f"  -> {detalhe}"))
    if not ok: falhas.append(nome)

M = motor.modelar(1.7, 1.1)
checar("probabilidades 1X2 somam 1", abs(M["p1"]+M["px"]+M["p2"]-1) < 1e-9)
checar("over decrescente", M["over"][0.5] > M["over"][1.5] > M["over"][2.5] > M["over"][3.5])
checar("Poisson soma 1", abs(sum(motor.poisson(k, 2.3) for k in range(40)) - 1) < 1e-9)

com = 0.065
rec = motor.odd_recomendada(0.62, 3, com)
checar("EV na odd mínima = margem exigida", abs(motor.ev_back(0.62, rec, com)*100 - 3) < 1e-6,
       f"deu {motor.ev_back(0.62, rec, com)*100:.4f}%")
recl = motor.odd_max_lay(0.18, 3, com)
checar("EV do lay na odd máxima = margem exigida", abs(motor.ev_lay(0.18, recl, com)*100 - 3) < 1e-6)

dm = motor.desmargem([1.55, 3.90, 6.20])
checar("desmargem soma 1", abs(sum(dm["probs"]) - 1) < 1e-9)
checar("overround positivo", dm["overround"] > 0)

lc, lf = motor.inferir_lambdas(dm["probs"])
MM = motor.modelar(lc, lf)
erro = max(abs(MM["p1"]-dm["probs"][0]), abs(MM["px"]-dm["probs"][1]), abs(MM["p2"]-dm["probs"][2]))
checar("inversão odds->lambda->odds fecha", erro < 0.01, f"erro {erro*100:.2f} p.p.")
checar("Kelly não aposta em EV negativo", motor.kelly(0.4, 1.5, 0.25, com) == 0)

sh = motor.share_janela(motor.MOMENTO_PADRAO, 0, 90)
checar("janela cheia = 100% dos gols", abs(sh - 1) < 1e-9)
checar("janela final é minoria", motor.share_janela(motor.MOMENTO_PADRAO, 65, 90) < 0.5)

jogo = {"hora":"16:00","liga":"Teste","casa":"A","fora":"B",
        "oddCasa":1.55,"oddEmpate":3.90,"oddFora":6.20,
        "gmCasa":1.95,"gsCasa":0.82,"gmFora":0.88,"gsFora":2.05,
        "ppjCasa":2.05,"ppjFora":0.85,"formaCasa":"VVEVV","formaFora":"DDEDD",
        "over25Casa":58,"over25Fora":52,"bttsCasa":46,"bttsFora":54}
r = motor.analisar({"jogos":[jogo]})
checar("jogo completo produz entrada", len(r["entradas"]) == 1, str(r["descartes"]))
if r["entradas"]:
    p = r["entradas"][0]["principal"]
    checar("stake dentro do teto", 0 < p["stake"] <= 3.0, f'stake {p["stake"]}')
    checar("odd recomendada plausível", 1.01 < p["oddRec"] < 100, f'odd {p["oddRec"]}')

vazio = motor.analisar({"jogos":[{"casa":"A","fora":"B"}]})
checar("jogo sem dados vai para descartes", len(vazio["descartes"]) == 1)

print()
if falhas:
    print(f"{len(falhas)} verificação(ões) falharam"); sys.exit(1)
print("todas as verificações passaram")
