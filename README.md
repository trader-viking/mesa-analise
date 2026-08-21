# Mesa de Análise

Análise de partidas para trading esportivo. Lê os relatórios em PDF, aplica os quatro métodos
operacionais e publica um site com os quadros do dia.

**Métodos:** Back Favorito · Lay Zebra · Over Limite (+1 gol, ao vivo) · Back 2x2

---

## Como funciona

```
site  →  baixar_pdfs.py  →  pdfs/  →  publicar.py  →  site/  →  GitHub Pages
```

A análise roda **na sua máquina**. Só a pasta `site/` (poucos KB por dia) vai para o GitHub —
os PDFs ficam de fora, porque cada um tem ~16 MB e o histórico do git é permanente.

## Instalação (uma vez)

```bash
git clone https://github.com/SEU-USUARIO/mesa-analise.git
cd mesa-analise
pip install -r requirements.txt
```

## Baixar os PDFs do site (opcional)

O `baixar_pdfs.py` abre cada partida no **Clube do Theo Borges** (`clube.theoborges.com`),
clica as abas, salva a página como PDF — exatamente o que você faz à mão — e já guarda o
arquivo na pasta certa com o nome certo.

```bash
pip install -r requirements-baixar.txt
python3 -m playwright install chromium
```

**Uma vez só — entrar na sua conta:**

```bash
python3 baixar_pdfs.py --login
```

Abre uma janela do navegador. Você entra na sua conta normalmente e volta ao terminal.
A sessão fica guardada em `.sessao.json` (que está no `.gitignore`, não vai para o GitHub).
**Sua senha nunca é digitada no script nem guardada em lugar nenhum.**

**No dia a dia:**

```bash
python3 baixar_pdfs.py --listar         # confere o que ele achou, sem baixar
python3 baixar_pdfs.py                  # partidas de hoje
python3 baixar_pdfs.py --quando amanha  # partidas de amanhã
```

Ele abre `clube.theoborges.com/matches?dia=hoje`, recolhe os links de partida e imprime um por um.

Comece pelo `--listar`: ele não baixa nada, só mostra os endereços encontrados. É a forma barata
de saber se a lista está certa antes de gastar ~15 segundos por partida. O `--limite 2` baixa só
as duas primeiras, para um teste de ponta a ponta.

Se algum link não for reconhecido, dá para listar à mão:

```bash
cp urls-exemplo.txt urls.txt          # cole os links das partidas
python3 baixar_pdfs.py --urls urls.txt
```

### Como ele acha as partidas

Em `analise/site.json`:

| Campo | Para que serve |
|---|---|
| `pagina_do_dia` | A lista de jogos. `{quando}` vira `hoje`/`amanha` conforme o `--quando`; `{data}` vira `AAAA-MM-DD` e `{dia}` vira `DD-MM-AAAA` quando você passa `--dia`. |
| `seletor_links_partida` | Seletor CSS dos links de partida. Preenchido, manda em tudo. |
| `padrao_link_partida` | Usado **só** quando o seletor está vazio: expressão que o endereço precisa conter. O padrão `/match` é largo de propósito — funciona sem você precisar inspecionar o HTML do site. |

Duas coisas são descartadas sozinhas, para o padrão largo não atrapalhar: links para fora do site
(patrocinador, rede social) e a própria página da lista, que quase sempre casa com o padrão por
causa do botão "amanhã". Se ainda vier link demais, aperte o padrão — `"/match/\\d+"`, por
exemplo, exige um número depois de `/match/`.

Depois de imprimir cada PDF, o script **lê o próprio arquivo** com o mesmo leitor da análise e
tira dali horário, times e liga. Ele não precisa saber onde o site mostra essas informações na
tela — basta o PDF sair no formato de sempre. Arquivo que já existe é pulado (`--forcar` refaz).

Se a sessão expirar, todas as partidas falham de uma vez: rode `--login` de novo.

## Uso diário

Coloque os PDFs na estrutura que você já usa:

```
pdfs/
  15-08-2026/
    Brasileirão/
      004_16h00_Grêmio_x_São_Paulo.pdf
    Premier League/
      001_11h00_Arsenal_x_Everton.pdf
```

O nome da pasta do meio vira a **data** e o da pasta interna vira a **liga** de cada jogo.

```bash
python3 publicar.py           # analisa e gera o site local
python3 publicar.py --push    # analisa, gera e publica no GitHub
```

Outras opções:

```bash
python3 publicar.py --dia 15-08-2026   # processa só um dia
python3 publicar.py --sem-cache        # reprocessa PDFs já lidos
```

Cada PDF leva uns 15 segundos na primeira leitura (são 71 páginas). Depois fica em cache e o
reprocessamento é instantâneo — um dia inteiro sai em menos de um segundo.

---

## Publicar no GitHub (uma vez)

1. Crie um repositório **público** chamado `mesa-analise` no GitHub, sem README.

2. No terminal, dentro desta pasta:

```bash
git init
git add .
git commit -m "Mesa de Análise"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/mesa-analise.git
git push -u origin main
```

3. No GitHub: **Settings → Pages → Source: GitHub Actions**.

4. Rode `python3 publicar.py --push`. Em um ou dois minutos o site estará em:

```
https://SEU-USUARIO.github.io/mesa-analise/
```

O índice lista todos os dias publicados. Cada dia tem a grade de quadros e o arquivo
`analise.json` com os números brutos, caso você queira levar para uma planilha.

---

## Instalar como aplicativo (PWA)

O site é instalável. Abra o endereço do GitHub Pages e clique em **⤓ Instalar app** — o botão só
aparece quando o navegador confirma que dá para instalar.

- **Android / Chrome / Edge:** o botão abre a instalação. Sem ele, use o menu ⋮ → *Instalar
  aplicativo*.
- **iPhone / iPad:** o Safari não tem esse prompt. Toque em *Compartilhar* → *Adicionar à Tela de
  Início*. O botão explica isso se for tocado no iOS.

Depois de instalado, abre em janela própria, com ícone na tela inicial e sem barra de endereço.

**Funciona offline** para o que você já abriu: um *service worker* busca na rede primeiro e cai no
cache quando não há conexão. A ordem importa — cache primeiro mostraria o relatório de ontem como
se fosse o de hoje, e isso é pior do que não abrir.

Os arquivos (`manifest.webmanifest`, `sw.js`, `icone-*.png`) são gerados pelo `publicar.py` a cada
publicação. Os ícones precisam do Pillow, que já vem com o `pdfplumber`.

Só funciona em **https** — ou seja, no GitHub Pages. Abrindo o `site/index.html` direto do disco a
instalação não é oferecida.

---

## Critérios

Ficam em `analise/criterios.json`. Tudo que não estiver no arquivo usa o padrão de `motor.py`.

```json
{
  "geral": { "banca": 1000, "comissao": 6.5, "kelly": 0.25, "stakeMax": 3.0 },
  "ligas": { "lista": "Brasileirão, Premier League" },
  "BACK_FAV":  { "probMin": 60, "aprovAdvMax": 40 },
  "LAY_ZEBRA": { "probMax": 20, "derrotas5Min": 3, "gsZebraMin": 2.0 },
  "OVER":      { "minutoGatilho": 65, "minutoFim": 70, "probMin": 55 },
  "BACK22":    { "over25Min": 60, "bttsMin": 60, "gsAmbosMin": 1.2 }
}
```

`ligas.lista` vazia aceita todas as competições. Com nomes preenchidos, jogos de outras ligas
vão para o Quadro 2 com esse motivo.

### Os critérios em vigor

| Método | Exige |
|---|---|
| **Back Favorito** | prob. de vitória ≥ 60% · favorito em casa **ou** claramente superior · adversário com aproveitamento recente < 40% |
| **Lay Zebra** | prob. da zebra ≤ 20% · 3+ derrotas nos últimos 5 **ou** defesa sofrendo ≥ 2.0 |
| **Over Limite** | só ao vivo, gatilho aos 65'–70' · linha = gols atuais + 0.5 · probabilidade tirada da tabela MOMENTO DOS GOLS |
| **Back 2x2** | over 2.5 médio ≥ 60% · ambas marcam ≥ 60% · **as duas** defesas sofrendo ≥ 1.2 |

Três parâmetros são acréscimos de engenharia, não critérios seus, e podem ser zerados: as odds
de guarda, o `lambdaTotalMin` do Over Limite e a margem exigida sobre a odd justa (`evMin`).

---

## O que o relatório entrega

Cada jogo aprovado vira um quadro com **partida · mercado sugerido · odd · stake em % e em reais**
e a etiqueta AO VIVO ou PRÉ-LIVE. Clicando, abre o detalhe: motivo, o que faz seguir ou descartar
a entrada ao vivo, momento de entrada e saída, números do modelo, tabela de momento dos gols,
histórico com aproveitamento por faixa de favoritismo e todas as odds do mercado pré.

A **odd recomendada** é o entregável principal: o preço a partir do qual a entrada tem a margem
exigida — mínima em back, **máxima** em lay.

---

## Estrutura

```
analise/
  motor.py        cálculo: Poisson, remoção de margem, EV, Kelly, os quatro métodos
  leitor_pdf.py   extração posicional e leitura do relatório de partida
  relatorio.py    geração do HTML
  criterios.json  seus limiares
  site.json       endereços e ajustes do baixador
baixar_pdfs.py    pega os PDFs do site (login uma vez, sessão reaproveitada)
publicar.py       comando único: analisa, gera o site e publica
testes/           verificações do motor (rodam no CI a cada push)
site/             saída publicada — é o que o GitHub Pages serve
pdfs/             seus PDFs (fora do repositório)
```

## Notas sobre a leitura dos PDFs

Três detalhes do formato que já estão tratados e vale conhecer:

- Cada linha de tabela começa com um caractere invisível de ícone (área privada do Unicode).
  Sem limpar, nenhuma expressão regular ancorada em início de linha funciona.
- No começo de temporada a tabela **Aproveitamento** vem zerada. Nesse caso as médias são
  derivadas da faixa dos últimos 8 jogos, e o relatório avisa. Como essa derivação não corrige
  a força do adversário, o peso do mercado no modelo sobe de 0.50 para 0.75.
- Na aba H2H, o marcador `AP` de prorrogação é desenhado abaixo do placar e aparece no jogo
  seguinte na ordem do texto. Além disso, jogo que foi para a prorrogação terminou empatado no
  tempo normal — é assim que o 1X2 liquida, e é assim que o histórico por faixa conta.

## Testes

```bash
python3 testes/test_motor.py
```

Conferem que as probabilidades somam 1, que o EV na odd recomendada é exatamente a margem
configurada (back e lay), que a inversão odds → gols esperados → odds fecha, e que o Kelly
nunca sugere stake em aposta de valor negativo. Rodam no CI a cada push.
