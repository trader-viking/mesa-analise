"""Identidade visual da Mesa de Análise.

A geometria do símbolo mora aqui e em nenhum outro lugar. Três renderizadores
leem a mesma lista de retângulos: SVG (site), PNG (ícones do aplicativo) e
canvas (as imagens dos quadros). Se o desenho mudar, muda em todos de uma vez.

O símbolo: quatro barras — os quatro métodos, nas cores que eles já têm no
aplicativo — apoiadas num tampo com duas pernas. É a mesa onde os métodos
ficam. Sem as pernas o tampo lê como sublinhado; por isso a versão reduzida,
para 16 e 32 px, larga as pernas de propósito, e não por descuido.
"""

from __future__ import annotations

# ---------------------------------------------------------------- paleta
PALETA = {
    "preto":  "#0E1116",   # fundo
    "painel": "#151A21",   # cartão
    "painel2": "#1B222B",
    "linha":  "#28313D",
    "claro":  "#E7ECF3",   # texto principal
    "cinza":  "#94A1B2",   # texto secundário
    "cinza2": "#66707E",   # texto terciário
    "verde":  "#34C48A",   # positivo / no ar
    "vermelho": "#EF5F5F",
    "ambar":  "#E0A02F",
}
METODOS = {
    "BACK_FAV":  ("#4C7EF3", "Back Favorito"),
    "LAY_ZEBRA": ("#A97BF0", "Lay Zebra"),
    "OVER":      ("#25B49B", "Over Limite"),
    "BACK22":    ("#E0A02F", "Back 2x2"),
}
CORES_METODO = [c for c, _ in METODOS.values()]

ALTURAS = [40, 58, 72, 50]      # a silhueta que dá o ritmo da marca


def formas(lado=100.0, pernas=True, mono=None):
    """Retângulos do símbolo em (x, y, largura, altura, raio, cor).

    Tudo derivado de uma grade 100×100 e multiplicado por `lado`, para o
    desenho ser idêntico em qualquer tamanho e em qualquer renderizador.
    """
    u = lado / 100.0
    larg, vao, esp = 13 * u, 8 * u, 8 * u
    base = 72 * u
    cores = [mono] * 4 if mono else CORES_METODO
    cor_mesa = mono or PALETA["claro"]

    esq = (lado - (4 * larg + 3 * vao)) / 2
    itens = []
    for i, (h, cor) in enumerate(zip(ALTURAS, cores)):
        itens.append((esq + i * (larg + vao), base - h * u, larg, h * u, larg * 0.34, cor))

    itens.append((2 * u, base, 96 * u, esp, esp / 2, cor_mesa))
    if pernas:
        pl, ph = 8 * u, 18 * u
        itens.append((11 * u, base + esp, pl, ph, pl * 0.42, cor_mesa))
        itens.append((81 * u, base + esp, pl, ph, pl * 0.42, cor_mesa))
    return itens


def altura_total(lado=100.0, pernas=True):
    return (98 if pernas else 80) * lado / 100.0


# ---------------------------------------------------------------- SVG
def svg_simbolo(lado=100, pernas=True, mono=None, atributos=""):
    alt = altura_total(lado, pernas)
    corpo = "".join(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="{r:.2f}" fill="{c}"/>'
        for x, y, w, h, r, c in formas(lado, pernas, mono))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lado:.0f} {alt:.0f}" '
            f'width="{lado:.0f}" height="{alt:.0f}" aria-hidden="true" {atributos}>'
            f'{corpo}</svg>')


def svg_icone(lado=512, recuo=0.17, raio=0.22):
    """Ícone de aplicativo: moldura arredondada e o símbolo dentro da zona segura."""
    interno = lado * (1 - 2 * recuo)
    m = lado * recuo
    topo = (lado - altura_total(interno)) / 2
    corpo = "".join(
        f'<rect x="{m + x:.2f}" y="{topo + y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="{r:.2f}" fill="{c}"/>'
        for x, y, w, h, r, c in formas(interno))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lado} {lado}" '
            f'width="{lado}" height="{lado}">'
            f'<rect width="{lado}" height="{lado}" rx="{lado*raio:.0f}" fill="{PALETA["preto"]}"/>'
            f'{corpo}</svg>')


# ---------------------------------------------------------------- PNG
def png_icone(caminho, lado=512, recuo=0.17, raio=0.22, fundo=None):
    """Mesmo desenho do SVG, em bitmap. Exige Pillow (vem com o pdfplumber)."""
    from PIL import Image, ImageDraw

    escala = 4                                  # desenha grande e reduz: bordas limpas
    L = lado * escala
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if fundo != "transparente":
        d.rounded_rectangle([0, 0, L - 1, L - 1], radius=int(L * raio),
                            fill=fundo or PALETA["preto"])

    interno = L * (1 - 2 * recuo)
    m = L * recuo
    topo = (L - altura_total(interno)) / 2
    for x, y, w, h, r, c in formas(interno):
        d.rounded_rectangle([m + x, topo + y, m + x + w, topo + y + h], radius=r, fill=c)

    img.resize((lado, lado), Image.LANCZOS).save(caminho)


# ---------------------------------------------------------------- canvas
def js_simbolo():
    """Função JS que desenha o símbolo num canvas, a partir da mesma grade."""
    import json
    return (
        "const MARCA_FORMAS = " + json.dumps(
            [[round(v, 3) if isinstance(v, float) else v for v in f] for f in formas(100.0)]) + ";\n"
        "function desenharMarca(c, x, y, lado){\n"
        "  const k = lado / 100;\n"
        "  for (const [fx, fy, fw, fh, fr, cor] of MARCA_FORMAS){\n"
        "    c.fillStyle = cor;\n"
        "    c.beginPath();\n"
        "    c.roundRect(x + fx*k, y + fy*k, fw*k, fh*k, fr*k);\n"
        "    c.fill();\n"
        "  }\n"
        "}\n")
