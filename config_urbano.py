"""
config_urbano.py - parametros do MODO URBANO (placas + leis de transito).

Nao substitui o config.py: acrescenta o que e especifico da pista urbana
e aplica overrides em runtime (aplicar_overrides no fim do arquivo).
O config.py continua com os valores da CORRIDA gravados.
"""

import config

# =====================================================================
# 1. MARCADORES (AprilTag)
# Confirmado no --scan: as placas da FIRA sao APRILTAG 36h11, nao ArUco.
# O signs.py le as duas familias pela mesma API.
# =====================================================================
ARUCO_DICT = "DICT_APRILTAG_36h11"

MARKER_TAMANHO_M = 0.08    # lado do marcador impresso, em metros

# Focal em PIXELS, na resolucao da camera de PLACAS.
# Calibre com: python3 test_signs.py --calib 0.50
FOCAL_PX = 640.0

# =====================================================================
# 2. MAPA ID -> PLACA
# Unico ponto do sistema onde um erro de digitacao vira infracao de
# transito. Confira cada ID com: python3 test_signs.py --scan
# =====================================================================
PLACAS = {
    0: "proibido_entrar",     # No Entry
    1: "sem_saida",           # Dead End
    2: "direita",             # Proceed Right  (Siga a direita)
    3: "esquerda",            # Proceed Left   (Siga a esquerda)
    4: "frente",              # Proceed Forward
    5: "parar",               # Stop - destino final
    6: "tunel",               # Tunnel
}

# =====================================================================
# 3. CONFIRMACAO E ACIONAMENTO
# =====================================================================
#
# Visto na pista: placa detectada so a 1.01m (v1, 1 voto) e a zebra
# disparou antes de completar os votos -- a intencao nunca armou e o
# carro seguiu reto por padrao. A causa raiz era o SALTO DE FRAMES
# aplicado em dobro (main + SignTracker), corrigido no main_urbano.py
# (SignTracker(pular_frames=1) com duas cameras). Estes dois valores
# (calibrados na pista) ficam como estao.
SIGN_CONFIRMA_FRAMES = 2     # frames concordantes pra aceitar um ID
SIGN_DIST_MIN_M = 0.15
# 2.00 -> 3.00: a distancia vem de um FOCAL_PX nao calibrado (640 chutado; o
# real de uma webcam 640x480 costuma ser ~450-550), o que SUPERESTIMA a
# distancia em ate ~40%. Com a placa a 1.5 m reais o carro "via" 2.1 m e o
# filtro jogava a placa fora em silencio ("placas: -" o tempo todo).
# Calibre com: python3 test_signs.py --calib 0.50
SIGN_DIST_MAX_M = 3.00

# Distancia em que a placa ARMA a intencao. A placa diz O QUE fazer;
# QUANDO fazer vem da faixa de pedestre (crosswalk.py).
SIGN_DIST_ACIONA_M = 1.20

# Com o carro PARADO na zebra (APROXIMANDO/PARANDO/PARADO) a placa arma ate
# esta distancia. Motivo: o carro agora freia no 1o instante em que ve a
# zebra, e pode parar com a placa a 1.3-1.6 m -- parado, ela nunca chegava
# a 1.20 m, nunca armava e o carro seguia RETO em vez de virar. Fica
# abaixo de SIGN_DIST_MAX_M pra evitar placa de outra rua.
SIGN_DIST_ACIONA_PARADO_M = 2.40

INTENCAO_VALIDA_S = 8.0      # intencao armada expira sem cruzamento
SIGN_SUMIU_ACIONA_FRAMES = 4 # arma tambem se o marcador sumir ja perto
SIGN_COOLDOWN_S = 6.0        # ignora o MESMO ID depois de obedecido
SIGN_SKIP_FRAMES = 2         # roda a deteccao 1 a cada N frames
SIGN_ROI_TOP_FRAC = 0.75     # procura placa so na parte de cima do frame

# =====================================================================
# 4. VELOCIDADES (override do config.py)
# =====================================================================
# "O MAIS LENTO POSSIVEL". Antes: cruzeiro 0.17, manobra 0.16, resto 0.14.
# Agora o cruzeiro e VELOCIDADE_URBANA e tudo o mais fica 0.01 abaixo, no
# piso. O piso REAL do seu motor/bateria so se descobre medindo:
#     python3 test_piso.py
# Ele diz o menor duty em que o carro ainda anda. Ponha VELOCIDADE_URBANA
# ~0.01 ACIMA dele (e os demais = o piso), pra sobrar folga quando a bateria
# cair. Se o carro zumbir parado, suba tudo; nao desca abaixo do piso.
#
# ATENCAO: baixar a velocidade da MANOBRA reescala os tempos da secao 6
# (x REF/velocidade), mas perto do piso duty->velocidade nao e linear: o
# carro anda MENOS do que a conta preve. Se a curva sair fechada de menos,
# suba MANOBRA_CURVA_* um pouco; se o avanco ficar curto, suba MANOBRA_AVANCO_*.
#
# MEDIDO no carro com test_piso.py: piso = 0.17 (cruzeiro 0.18 = piso + folga).
VELOCIDADE_URBANA = 0.18

VELOCIDADE_BASE_URBANO    = VELOCIDADE_URBANA
VELOCIDADE_MINIMA_URBANO  = 0.17
VELOCIDADE_PERDIDO_URBANO = 0.17
VELOCIDADE_MANOBRA        = 0.17   # dentro do cruzamento
VELOCIDADE_APROXIMACAO    = 0.17   # chegando na faixa pra parar
VELOCIDADE_TUNEL          = 0.17

# Abaixo deste duty o motor nao vence o atrito e zumbe parado em vez de
# andar devagar. Valor MEDIDO por test_piso.py.
VELOCIDADE_PISO_ESTIMADO = 0.17

# Freio por FPS baixo (main: speed *= fps/FPS_MINIMO_SEGURO). A 17% de duty
# qualquer reducao cai ABAIXO do piso do motor e o carro zumbe parado,
# entao no urbano fica desligado. A velocidade ja e a minima possivel.
FPS_FREIO_URBANO = False

# MARCHA LENTA POR PULSO -- permite velocidade media ABAIXO do piso do
# motor (liga no piso por uma fracao do tempo). DESLIGADO: troca
# "devagar" por "trepidante". Ligue so se precisar andar mais devagar
# do que o motor permite de forma continua.
PULSO_ATIVO     = False
PULSO_PISO      = 0.26
PULSO_PERIODO_S = 0.18
PULSO_MIN_FRAC  = 0.25

# ARRANQUE: atrito estatico > dinamico. Sem esse tranco curto, o carro
# zumbe ao retomar depois da parada obrigatoria.
ARRANQUE_ATIVO   = True
ARRANQUE_DUTY    = 0.55
ARRANQUE_TEMPO_S = 0.12

# VIES DO ALVO. Magnitude: 0.0 = meio da faixa | 1.0 = colado na linha.
# SINAL: positivo aproxima da PONTILHADA, negativo aproxima da CONTINUA.
#
# HISTORICO: positivo em 0.45 (colado na pontilhada) tirava o carro pra
# contramao depois de curva. A causa real nao era so o vies -- era o
# AVANCO/GIRO da manobra mal calibrado (secao 6), fazendo o carro pousar
# na faixa errada do cruzamento. Corrigido o giro, o vies pode ficar
# moderado e perto da pontilhada (o correto pela lei de transito).
# Se aparecer "!! CONTINUA NA ESQUERDA" no log, o problema voltou a ser
# o AVANCO/GIRO da curva, nao este numero. Teto real: config.LANE_BIAS_LIMITE.
#
# 0.55 -> 0.70: a placa fica quase colada na linha CONTINUA e o carro
# derrubava ela; mais um pouco pra pontilhada afasta. Alvo desloca ~10 px
# a mais (~2-3 cm). Proximo passo se precisar: 0.80. Teto: LANE_BIAS_LIMITE
# (0.90). Se aparecer "!! CONTINUA NA ESQUERDA" no log, volte pra 0.55.
#
# 0.70 -> 0.35, JUNTO com o KI novo (ver PID_KI_URBANO). Antes o carro nao
# chegava ao alvo (controle so proporcional): ficava colado na CONTINUA
# mesmo com 0.70. Agora ele CHEGA no alvo, e 0.70 seria colar na pontilhada
# (na simulacao, a ~4 cm da linha). 0.35 = alvo a 35% da meia-largura pro
# lado da pontilhada. Quer mais pra pontilhada? 0.45. Mais pro centro? 0.25.
# 0.35 -> 0.50 (pedido: andar mais perto da pontilhada). Mais ainda: 0.60.
LANE_BIAS_FRAC_URBANO = 0.50

# Em mao direita, a linha CONTINUA (borda da rua) fica a DIREITA do carro
# e a pontilhada a esquerda. Se a visao reportar continua na ESQUERDA, o
# carro esta na via contraria -- o main avisa no log.
LADO_CONTINUO_ESPERADO = "direita"

# FORCA qual lado e a continua em vez de deixar a visao "adivinhar" (contando
# buracos na pontilhada). Adivinhar falha justamente onde mais importa: logo
# depois de uma curva, ou onde a pontilhada esta apagada/suja. Como a regra
# e "mao direita", a resposta e conhecida de antemao. O vies acima continua
# valendo: o lado forcado so diz PRA ONDE e "perto da pontilhada" (esquerda). A deteccao automatica continua rodando so pra gerar o aviso de
# CONTRAMAO no log. Use None pra voltar ao modo automatico.
LADO_CONTINUO_FORCADO = LADO_CONTINUO_ESPERADO

# LIMITADOR DE TAXA DO ESTERCO (unidades de turn por segundo).
# 3.0 = varre de -1 a +1 em ~0.66s. Menor = mais suave e mais lento pra
# reagir; maior = mais nervoso. E o remedio direto pro servo tremendo.
TURN_SLEW_POR_S = 3.0

# Zona morta do servo em GRAUS: so reescreve o pulso se o angulo mudou
# mais que isso. Mata o micro-tremor de PWM parado.
SERVO_DEADBAND_URBANO = 2.0

# =====================================================================
# 4b. FAIXA DE PEDESTRE (zebra) -- ver crosswalk.py
# Valores em PIXELS na resolucao da visao (480x240).
# =====================================================================
ZEBRA_MIN_BARRAS = 4
ZEBRA_BARRA_MIN_PX = 3
ZEBRA_BARRA_MAX_PX = 30
ZEBRA_SPAN_MIN_FRAC = 0.35
ZEBRA_IRREGULARIDADE_MAX = 0.45
# Varredura da zebra: mais linhas e comecando mais acima na imagem (0.25 ->
# 0.15). Antes a 1a deteccao so acontecia com a faixa ja perto (frac ~0.41,
# quase igual ao gatilho de parada), entao o gatilho nao tinha folga pra
# parar mais cedo. Com 14 linhas a barra mais proxima so cai em degraus de
# ~10 px (frac 0.21 | 0.28 | 0.34 | 0.40 | 0.47 | 0.53). Veja ZEBRA_PARADA_FRAC.
ZEBRA_SCAN_ROWS = 14
ZEBRA_TOP_FRAC = 0.15
ZEBRA_MIN_LINHAS = 3
ZEBRA_HIT_FRAMES = 1          # entra rapido (cada frame de espera = cm andados)
ZEBRA_MISS_FRAMES = 6         # sai devagar (nao pisca no meio da travessia)
ZEBRA_COOLDOWN_S = 3.0        # (so cobre a fase de parada)

# BUG CORRIGIDO: o cooldown acima comeca quando a zebra e AVISTADA, e a
# parada obrigatoria sozinha (aproximacao + freio + 3s parado) ja passa de
# 3s -- quando a manobra terminava, o cooldown tinha vencido e a zebra da
# SAIDA do cruzamento disparava uma 2a parada de 3s. Agora o bloqueio
# comeca quando a MANOBRA ACABA. Valor em s a velocidade de referencia;
# e reescalado junto com as manobras (mais lento = mais tempo).
ZEBRA_COOLDOWN_POS_MANOBRA_S = 3.0

# PARADA OBRIGATORIA: o gatilho e a posicao da zebra na IMAGEM.
# Parou em cima da faixa -> BAIXE. Parou longe demais -> suba.
# Lembre da ZONA CEGA: frac=1.0 nao e "encostando", e "ja passou".
#
# PARAR MAIS CEDO: originalmente 0.42 (barra da zebra na linha 77 da
# mascara); depois 0.39 (linha 63), que ainda parava em cima. Agora 0.27 ->
# linha 43, o MAIS CEDO que a deteccao atual permite: o carro freia na
# primeira varredura em que enxerga a zebra. A barra so cai em degraus de
# ~10 px (ver ZEBRA_SCAN_ROWS):
#   0.47 (linha 73) | 0.39 (63) | 0.33 (53) | 0.27 (43) <- agora
# Mais cedo que isso NAO adianta mexer aqui: so enxergando a zebra de mais
# longe (ZEBRA_TOP_FRAC menor), o que arrisca confundir fundo com zebra.
# Quer voltar um pouco? 0.33.
#
# 0.27 -> 0.20: agora que existe RE (secao 7), o objetivo e frear NA PRIMEIRA
# vez em que a zebra aparece, qualquer que seja o degrau. Valor abaixo do
# primeiro degrau (0.21) = "assim que enxergar".
ZEBRA_PARADA_FRAC = 0.20

APROXIMACAO_MAX_S = 2.5       # teto de tempo da aproximacao

# =====================================================================
# 4c. PID PARA BAIXA VELOCIDADE (override do config.py)
#
# Num carro Ackermann o amortecimento do laco sai como
#       zeta ~ v * KD / raiz(KP)
# ou seja, e PROPORCIONAL A VELOCIDADE. O PID do config.py foi calibrado
# a VELOCIDADE_BASE = 1.00; aqui o carro anda a ~0.16, o que derruba o
# amortecimento na mesma proporcao. O mesmo par (KP, KD) que era estavel
# na corrida oscila no urbano. Correcao: baixar KP e SUBIR KD.
#
# CUIDADO com o quanto: o KD_URBANO estava em 0.42 (quase o dobro do
# KP_URBANO) com D_SUAVIZACAO_URBANO em 0.30 -- um filtro de derivada
# BEM mais fraco que o do config.py (0.55), que la foi subido de 0.3
# pra 0.55 justamente pra "segurar o balanco" do servo (ver comentario
# na secao 7 do config.py). O par antigo daqui desfazia esse ajuste E
# ainda multiplicava o ganho da derivada -- e a derivada e o termo que
# mais amplifica ruido de pixel frame a frame, exatamente a receita pra
# o servo tremer mais que o normal. Baixado KD e subido o filtro pra
# nao repetir o mesmo problema que o config.py ja tinha corrigido.
# Se ainda tremer na pista, primeiro suba D_SUAVIZACAO_URBANO (mais
# filtro); so desça KD_URBANO se isso nao bastar.
# =====================================================================
PID_KP_URBANO = 0.24
PID_KD_URBANO = 0.20
PID_D_SUAVIZACAO_URBANO = 0.55

# Zona morta: mata o "hunting" do servo em cima de ruido de pixel.
# INTEGRAL (KI). Sem ele o controle e so proporcional (KP 0.24) e a posicao
# do carro na pista FICA REFEN do "puxao" do servo reto: o log mostrava
# `erro -0.35 | turn -0.08` por varios segundos (esterço minusculo segurando
# um erro enorme) e o carro ficava colado na continua, nao importando o
# viés. O integral soma esse erro ao longo do tempo e leva o carro ate o alvo
# de verdade (o vies passa a significar o que diz). PID_I_LIMIT_URBANO limita
# o quanto ele pode empurrar (0.5 x KI 0.20 = 0.10 de esterço ~ 4-5 graus).
# Se o carro serpentear devagar (ondas longas), baixe KI pra 0.12.
PID_KI_URBANO = 0.20
PID_I_LIMIT_URBANO = 0.5

# Zona morta 0.07 -> 0.04: com 0.07 (~4 cm) o integral nao fechava o ultimo
# trecho ate o alvo (ele e zerado dentro da zona morta).
DEAD_ZONE_URBANO = 0.04
ERRO_SUAVIZACAO_URBANO = 0.45

# =====================================================================
# 5. CAMERAS
#   faixa  -> chao logo a frente: faixa + zebra
#   placas -> mais pra cima/longe: so AprilTag
# Indices: ls /dev/video*   |  FOCAL_PX vale na resolucao de PLACAS.
# Se a de placas nao abrir, o main cai sozinho pra uma camera so.
# =====================================================================
CAMERA_FAIXA_INDEX  = 0
CAMERA_PLACAS_INDEX = 2
CAMERA_RES_FAIXA   = (640, 480)
CAMERA_RES_PLACAS  = (640, 480)
CAMERA_RES_CAPTURA = CAMERA_RES_PLACAS   # compat. camera unica

# =====================================================================
# 6. MANOBRAS EM MALHA ABERTA (cronometradas)
#
# Dentro do cruzamento NAO existe faixa pra seguir: o PID e desligado e
# o movimento e cronometrado ate haver faixa de novo.
#
# AS CURVAS SAO ASSIMETRICAS por causa da mao direita:
#   DIREITA  -> a faixa de destino e a mais proxima. Gira cedo, arco curto.
#   ESQUERDA -> a faixa de destino fica do OUTRO lado do cruzamento. Tem
#               que avancar alem do centro antes de girar, com arco maior,
#               senao termina na contramao.
# Calibre os quatro numeros INDEPENDENTEMENTE -- espelhar da errado.
#
# Os tempos valem para VELOCIDADE_MANOBRA_REF e sao reescalados sozinhos
# quando a velocidade muda (o que importa e a DISTANCIA, nao o tempo).
# =====================================================================
VELOCIDADE_MANOBRA_REF = 0.24

# AVANCO da direita baixado: andar reto demais antes de virar faz o carro
# passar do canto e curvar tarde, pousando na faixa de LONGE (errada).
# 0.25 -> 0.0: curva a DIREITA sem avanco reto. Com o avanco o carro entrava
# demais no cruzamento e terminava na faixa CONTRARIA (continua a esquerda).
# Agora, depois da re, ele ja sai com o servo pra esquerda (ABRINDO) e
# faz o balao pra direita. Quer um pouco de reta de volta? 0.15.
MANOBRA_AVANCO_DIR_S = 0.0
MANOBRA_AVANCO_ESQ_S = 0.45

# GIRO: quanto tempo o servo FICA no angulo de MANOBRA_TURN_MAG antes de
# soltar. Confirmado na pista.
MANOBRA_CURVA_DIR_S  = 1.35
MANOBRA_CURVA_ESQ_S  = 1.38
MANOBRA_TRAVESSIA_S  = 1.50
MANOBRA_TURN_MAG_DIR = 0.95
MANOBRA_TURN_MAG_ESQ = 0.80   # menos esterco = raio maior = arco aberto

# ABERTURA DA CURVA A DIREITA (so a direita; a esquerda nao muda).
# Antes de virar pra direita o servo vai um pouco pra ESQUERDA por
# MANOBRA_ABERTURA_DIR_S, e so depois gira a direita. O carro "abre" o
# caminho e passa mais longe do canto onde fica a placa, em vez de
# raspar nela (a placa caia). Tempo no velocidade de REFERENCIA (reescala
# sozinho, como os outros). 0 desliga a abertura.
#   MANOBRA_ABERTURA_DIR_S    quanto tempo fica virado pra esquerda
#   MANOBRA_ABERTURA_TURN_DIR quanto do curso esquerdo do servo (0..1)
# Mais tempo/mais esterco = abre mais. Se encostar na pontilhada ou invadir
# a contramao, diminua; se ainda raspar na placa, aumente.
MANOBRA_ABERTURA_DIR_S    = 0.35
MANOBRA_ABERTURA_TURN_DIR = 0.60
# O desvio pra esquerda "gasta" parte do giro: sem compensar, o carro sai da
# curva virado menos de 90 graus. Com True, o giro a direita ganha o tempo
# extra proporcional (esterco x tempo da abertura / esterco do giro).
MANOBRA_ABERTURA_COMPENSA = True

MANOBRA_AUTOESCALA = True     # False so depois de congelar a velocidade

if MANOBRA_AUTOESCALA and VELOCIDADE_MANOBRA > 0:
    _k = VELOCIDADE_MANOBRA_REF / VELOCIDADE_MANOBRA
    MANOBRA_AVANCO_DIR_S *= _k
    MANOBRA_AVANCO_ESQ_S *= _k
    MANOBRA_CURVA_DIR_S  *= _k
    MANOBRA_CURVA_ESQ_S  *= _k
    MANOBRA_TRAVESSIA_S  *= _k
    MANOBRA_ABERTURA_DIR_S *= _k
    ZEBRA_COOLDOWN_POS_MANOBRA_S *= _k

# Giro a direita EFETIVO = giro calibrado + compensacao da abertura.
# (angulo girado ~ esterco x tempo; esterco em fracao do curso do servo,
# que e diferente pra esquerda e pra direita)
_curso_esq = config.SERVO_CENTRO - config.SERVO_MAX_ESQ
_curso_dir = config.SERVO_MAX_DIR - config.SERVO_CENTRO
if MANOBRA_ABERTURA_COMPENSA and MANOBRA_ABERTURA_DIR_S > 0:
    MANOBRA_CURVA_DIR_EFETIVA_S = MANOBRA_CURVA_DIR_S + MANOBRA_ABERTURA_DIR_S * (
        (MANOBRA_ABERTURA_TURN_DIR * _curso_esq) /
        (MANOBRA_TURN_MAG_DIR * _curso_dir))
else:
    MANOBRA_CURVA_DIR_EFETIVA_S = MANOBRA_CURVA_DIR_S

MANOBRA_REENGATE_FRAMES = 25  # frames sem faixa tolerados no reengate

# =====================================================================
# 7. PARADA / DESTINO
# =====================================================================
PARADA_FREIO_S    = 0.25
PARADA_TEMPO_S    = 5.0    # parado na faixa, em TODO cruzamento
PARADA_TEMPO_EXTRA_MAX_S = 3.0
PARADA_DEFINITIVA = True   # placa STOP = destino, encerra a missao

# RE (marcha a re) NA PARADA: a zebra NAO pode ser pisada. Se mesmo freando
# na 1a vista o carro passou da linha (ou esta com ela quase debaixo do
# capo), ele da re ate a zebra voltar a aparecer a uma distancia segura, e
# SO ENTAO comeca a contar a parada obrigatoria.
# A re e feita em linha reta (servo centrado), na velocidade de piso.
RE_ATIVA            = True
VELOCIDADE_RE       = 0.17    # duty da re (piso do motor; nao use menos)
# Quando recuar (frac_proximidade da zebra: 0 = longe, 1 = colada no capo):
#   - zebra SUMIU depois de ter chegado a RE_PERDEU_FRAC (passou por baixo), ou
#   - zebra visivel com frac >= RE_GATILHO_FRAC (quase debaixo do capo).
RE_GATILHO_FRAC     = 0.60
RE_PERDEU_FRAC      = 0.40
# Onde parar de recuar: zebra visivel com frac <= RE_ALVO_FRAC.
RE_ALVO_FRAC        = 0.45
RE_MIN_S            = 0.30    # recua pelo menos isso (a deteccao pisca)
RE_MAX_S            = 1.60    # teto de tempo por tentativa
RE_TENTATIVAS_MAX   = 2
# Depois da re o carro fica PARADO no minimo isso antes de andar de novo
# (vale junto com PARADA_TEMPO_S: usa-se o MAIOR dos dois, contado a partir
# do fim da re).
RE_ESPERA_MIN_S     = 3.0
# RE EXTRA so pra curva a DIREITA: depois da espera obrigatoria, recua mais
# isso (em s, na VELOCIDADE_RE) pra largar de mais atras, e espera
# RE_ESPERA_MIN_S de novo antes de sair. Motivo: sem avanco reto o carro faz
# o balao a partir do ponto onde parou; quanto mais atras ele parte, mais
# cedo termina a curva e mais perto da faixa DIREITA da rua nova ele cai.
# Terminou na faixa contraria (muito longe)? suba (1.2). Terminou colado na
# borda/placa da direita (curto demais)? baixe (0.6). 0 desliga.
RE_EXTRA_DIR_S      = 0.9

# =====================================================================
# 8. RUA BLOQUEADA (No Entry / Dead End)
# As duas placas significam o mesmo: nao entra nessa rua -> desvia.
# =====================================================================
BLOQUEIO_PREFERENCIA = ("direita", "esquerda")
BLOQUEIO_MEMORIA_S = 5.0

# =====================================================================
# 9. TUNEL
# A linha do tunel veio VAZIA na tabela da prova. Padrao defensivo:
# reduz, afrouxa o limiar de branco e tolera mais frames sem leitura.
# CONFIRA O REGULAMENTO.
# =====================================================================
TUNEL_DURACAO_S          = 6.0
TUNEL_TOPHAT_FATOR       = 0.30
TUNEL_V_MIN_ABS          = 40
TUNEL_MAX_FRAMES_PERDIDO = 30


# =====================================================================
# APLICACAO DOS OVERRIDES
# =====================================================================
def aplicar_overrides():
    """Aplica o perfil urbano sobre o config.py, em runtime.
    Nao edita arquivo: rodar main.py depois nao herda nada daqui."""
    config.VELOCIDADE_BASE    = VELOCIDADE_BASE_URBANO
    config.VELOCIDADE_MINIMA  = VELOCIDADE_MINIMA_URBANO
    config.VELOCIDADE_PERDIDO = VELOCIDADE_PERDIDO_URBANO
    config.LANE_BIAS_FRAC     = LANE_BIAS_FRAC_URBANO
    config.LADO_CONTINUO_FORCADO = LADO_CONTINUO_FORCADO
    # o config.py da corrida tem piso de curva fechada em 0.38: sem isso,
    # speed_for() SOBE a velocidade em curva fechada (so o teto do main
    # segurava). Alinha com a velocidade urbana.
    config.VELOCIDADE_MINIMA_FECHADA = VELOCIDADE_MINIMA_URBANO

    _kp_antes, _kd_antes = config.PID_KP, config.PID_KD
    config.PID_KP = PID_KP_URBANO
    config.PID_KD = PID_KD_URBANO
    config.PID_D_SUAVIZACAO = PID_D_SUAVIZACAO_URBANO
    config.PID_KI = PID_KI_URBANO
    config.PID_I_LIMIT = PID_I_LIMIT_URBANO
    config.DEAD_ZONE = DEAD_ZONE_URBANO
    config.ERRO_SUAVIZACAO = ERRO_SUAVIZACAO_URBANO
    config.SERVO_DEADBAND_DEG = SERVO_DEADBAND_URBANO

    print(f"[urbano] PID baixa velocidade: KP {_kp_antes:.2f}->{config.PID_KP:.2f}  "
          f"KD {_kd_antes:.2f}->{config.PID_KD:.2f}")
    print(f"[urbano] perfil: base={config.VELOCIDADE_BASE:.2f} "
          f"min={config.VELOCIDADE_MINIMA:.2f} bias={config.LANE_BIAS_FRAC:.2f}")
    if MANOBRA_AUTOESCALA:
        print(f"[urbano] manobras x{_k:.2f} -> avanco dir {MANOBRA_AVANCO_DIR_S:.2f}s "
              f"esq {MANOBRA_AVANCO_ESQ_S:.2f}s")
    if VELOCIDADE_APROXIMACAO < VELOCIDADE_PISO_ESTIMADO:
        print(f"[urbano] AVISO: VELOCIDADE_APROXIMACAO ({VELOCIDADE_APROXIMACAO:.2f}) "
              f"abaixo do piso ({VELOCIDADE_PISO_ESTIMADO:.2f}) -- pode travar zumbindo.")
