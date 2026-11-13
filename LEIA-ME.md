# Piloto urbano — FIRA

Pacote completo. Copie **todos** os arquivos desta pasta para `~/urbano`.
Não renomeie nada.

## Comando da prova

```bash
python3 main_urbano.py            # sem janela (mais FPS)
python3 main_urbano.py --debug    # com janelas, pra bancada
```

## Os arquivos

**Base do robô** (não são "da corrida" — são do robô; o urbano depende deles):

| arquivo | papel |
|---|---|
| `config.py` | pinos, servo, câmera, visão, PID |
| `vision.py` | visão de faixa (já com `last_mask` exposta) |
| `controller.py` | PID de direção |
| `MotorModule.py` | tração + servo (GPIO) |

**Camada urbana:**

| arquivo | papel |
|---|---|
| `config_urbano.py` | placas, zebra, manobras, velocidades |
| `signs.py` | leitura dos marcadores ArUco |
| `crosswalk.py` | detecção da faixa de pedestre |
| `navigator.py` | máquina de estados de decisão |
| `main_urbano.py` | loop principal |
| `test_signs.py` | ferramenta de calibração |
| `test_piso.py` | acha o menor duty em que o carro anda (velocidade mínima) |

## Duas câmeras

O modo urbano usa **duas câmeras USB**, cada uma com um trabalho só:

| câmera | index (`config_urbano.py`) | resolução | função |
|---|---|---|---|
| faixa  | `CAMERA_FAIXA_INDEX`  | `config.CAMERA_RES` (480x240) | seguir a pista (`vision.py`) e ver a zebra |
| placas | `CAMERA_PLACAS_INDEX` | `CAMERA_RES_CAPTURA` (640x480) | ler só os marcadores ArUco das placas (`signs.py`) |

Antes de rodar, descubra o index de cada uma (a ordem de plugagem USB
decide qual é 0 e qual é 1 -- confira sempre, principalmente se trocar
de porta USB ou reiniciar o Pi):

```bash
ls /dev/video*
v4l2-ctl --list-devices
```

Ajuste `CAMERA_FAIXA_INDEX` / `CAMERA_PLACAS_INDEX` em `config_urbano.py`
de acordo. Se `main_urbano.py` imprimir "AVISO: a camera ... entregou
WxH em vez de ..." no início, é sinal de que os indexes estão trocados
ou a câmera não suporta a resolução pedida.

## Modelo de decisão

    PLACA (ArUco)     -> O QUE fazer no cruzamento
    FAIXA DE PEDESTRE -> QUANDO fazer

A placa arma uma intenção a ~1,2m. A intenção fica guardada até a zebra
aparecer; aí a manobra dispara em malha aberta (PID desligado, porque
dentro do cruzamento não existe faixa pra seguir). Zebra sem placa
armada = atravessa reto.

## As 7 placas suportadas

O mapa `PLACAS` em `config_urbano.py` já cobre a tabela oficial da
prova -- nome da placa, o que o carro deve fazer:

| placa | decisão do carro |
|---|---|
| No Entry (proibido_entrar) | não entra nessa rua -- desvia no cruzamento |
| Dead End (sem_saida) | não entra nessa rua -- desvia no cruzamento |
| Proceed Right (direita) | vira à direita no cruzamento |
| Proceed Left (esquerda) | vira à esquerda no cruzamento |
| Proceed Forward (frente) | segue em frente |
| Stop (parar) | destino final -- encerra a missão |
| Tunnel (tunel) | reduz velocidade e afrouxa a visão (seção 9 do `config_urbano.py`) |

Os **marcadores** dessa tabela são ArUco, não QR Code (ver comentário na
seção 1 de `config_urbano.py`) -- só carregam um ID de 0 a 6, o que é o
que permite ler de longe com câmera barata. Os IDs abaixo são **chute**
e têm que ser confirmados com `test_signs.py --scan` antes de qualquer
coisa (próxima seção).

## Ordem de calibração

**Nunca pule etapas — cada uma depende da anterior estar certa.**

### 1. IDs das placas (pode ser no notebook)

```bash
python3 test_signs.py --scan
```

Por padrão usa a câmera de `CAMERA_PLACAS_INDEX`; para testar com outra,
passe `--cam N` (ex: `python3 test_signs.py --scan --cam 0`).
Mostre uma placa por vez. Anote o dicionário e o ID de cada uma.
Corrija `ARUCO_DICT` e o mapa `PLACAS` no `config_urbano.py`.

> IDs 0–5 conferidos com a imagem oficial das placas (0 Proibido entrar, 1 Rua
> sem saída, 2 Direita, 3 Esquerda, 4 Frente, 5 Pare); o 6 (Tunnel) não estava
> nela e continua **chute**. Direita e esquerda estavam trocadas antes. Se estiverem errados, o robô
> obedece a placa errada com total confiança. É o passo mais crítico.

### 2. Distância das placas

Meça o lado do marcador impresso com régua → `MARKER_TAMANHO_M`.
Depois, marcador a exatamente 50 cm da lente da câmera de placas:

```bash
python3 test_signs.py --calib 0.50    # aperte 'c'
```

Cole o `FOCAL_PX` que ele imprimir.

### 3. Verificação ao vivo

```bash
python3 test_signs.py
```

Aproxime a placa e veja se o evento dispara. Ajuste `SIGN_DIST_ACIONA_M`
se disparar cedo/tarde demais.

### 4. Zebra

Robô parado a ~30 cm da faixa de pedestre:

```bash
python3 test_vision.py     # olhe a janela "Mascara"
```

As barras têm que aparecer separadas e limpas. Ajuste
`ZEBRA_BARRA_MIN_PX` / `ZEBRA_BARRA_MAX_PX` conforme a largura real
delas em pixels.

### 5. Bancada — carro na mão, rodas no ar

```bash
python3 main_urbano.py --debug
```

Passe placa e zebra na frente da câmera. Confira a sequência de estados:

    SEGUINDO -> AVANCANDO -> CURVANDO -> REENGATANDO -> SEGUINDO

### 6. Pista — só agora

Ajuste os únicos números que sobram:

- curva fechou cedo/tarde → `MANOBRA_AVANCO_S`
- virou menos/mais que 90° → `MANOBRA_CURVA_S`

Um cruzamento por vez, repetindo até ficar consistente.
**Calibre com a bateria no nível que vai usar na prova** — bateria fraca
muda esses tempos.

## Pendências de regulamento

- **Tunnel**: a linha veio vazia na tabela. Implementado o padrão
  defensivo (reduz velocidade, afrouxa o limiar de branco, tolera mais
  frames sem leitura). Confira a regra real — seção 9 do
  `config_urbano.py`.
- **Stop**: tratado como destino final (`PARADA_DEFINITIVA = True`).
  Se for um PARE comum (para 3 s e segue), troque para `False`.

## Perfil atual: lento, mao direita

- **Velocidade minima**: cruzeiro `VELOCIDADE_URBANA = 0.18` e o resto em
  0.17 (manobra, aproximacao, perdido, tunel; piso medido = 0.17). Descubra o piso REAL do seu
  motor com o carro no chao: `python3 test_piso.py` (Ctrl+C no primeiro duty
  em que ele anda firme; ele imprime os valores pra colar no config). O
  freio por FPS baixo (`FPS_FREIO_URBANO`) fica desligado. Baixar a
  velocidade da manobra reescala os tempos da secao 6, mas perto do piso o
  carro anda menos do que a conta preve: reconfira as curvas.
- **Mao direita**: `LADO_CONTINUO_FORCADO = "direita"` (a continua e sempre
  a da direita; a visao nao adivinha mais o lado) e
  `LANE_BIAS_FRAC_URBANO = 0.55` (calibrado no Pi: perto da pontilhada,
  que e o correto pela lei de transito). Se aparecer "!! CONTINUA NA
  ESQUERDA" no log, o problema e o AVANCO/GIRO da curva, nao este numero.
- **Zebra da saida**: depois da manobra a zebra e ignorada por
  `ZEBRA_COOLDOWN_POS_MANOBRA_S` (escala com a velocidade). Antes o carro
  parava uma 2a vez de 3 s na saida do cruzamento.
- **Parada**: o `main_urbano.py` agora usa o freio ativo (`motor.brake()`) na
  parada obrigatoria; antes so cortava o PWM e o carro rolava.
- **Placas**: removido o salto de frames duplicado (a deteccao rodava a cada
  9 frames em vez de 3) e os votos de confirmacao agora decaem 1 por frame
  perdido em vez de zerar.
- **Parada**: `PARADA_TEMPO_S` (5 s) e o minimo; se a placa ainda nao foi
  confirmada, espera ate `PARADA_TEMPO_EXTRA_MAX_S` (+3 s) antes de seguir
  reto por padrao.
- **Manobras**: tempos calibrados na pista (`MANOBRA_AVANCO_*`,
  `MANOBRA_CURVA_*`). Recalibre se mudar velocidade ou bateria.
