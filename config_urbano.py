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
    2: "esquerda",            # Proceed Left
    3: "direita",             # Proceed Right
    4: "frente",              # Proceed Forward
    5: "parar",               # Stop - destino final
    6: "tunel",               # Tunnel
}

# =====================================================================
# 3. CONFIRMACAO E ACIONAMENTO
# =====================================================================
SIGN_CONFIRMA_FRAMES = 3     # frames concordantes pra aceitar um ID
SIGN_DIST_MIN_M = 0.15
SIGN_DIST_MAX_M = 2.00

# Distancia em que a placa ARMA a intencao. A placa diz O QUE fazer;
# QUANDO fazer vem da faixa de pedestre (crosswalk.py).
SIGN_DIST_ACIONA_M = 1.20

INTENCAO_VALIDA_S = 8.0      # intencao armada expira sem cruzamento
SIGN_SUMIU_ACIONA_FRAMES = 4 # arma tambem se o marcador sumir ja perto
SIGN_COOLDOWN_S = 6.0        # ignora o MESMO ID depois de obedecido
SIGN_SKIP_FRAMES = 3         # roda a deteccao 1 a cada N frames
SIGN_ROI_TOP_FRAC = 0.75     # procura placa so na parte de cima do frame

# =====================================================================
# 4. VELOCIDADES (override do config.py)
# =====================================================================
# UMA velocidade so pra tudo: 17% de duty, constante. Mexa AQUI e so aqui.
# Constante de proposito: sem variacao de velocidade o tempo das manobras
# cronometradas fica repetivel e o carro nao "acorda" nem "dorme" em curva.
VELOCIDADE_URBANA = 0.17

VELOCIDADE_BASE_URBANO    = VELOCIDADE_URBANA
VELOCIDADE_MINIMA_URBANO  = VELOCIDADE_URBANA   # min == base -> speed_for() nao varia
VELOCIDADE_PERDIDO_URBANO = VELOCIDADE_URBANA
VELOCIDADE_MANOBRA        = VELOCIDADE_URBANA   # dentro do cruzamento
VELOCIDADE_APROXIMACAO    = VELOCIDADE_URBANA   # chegando na faixa pra parar
VELOCIDADE_TUNEL          = VELOCIDADE_URBANA

# Abaixo deste duty o motor nao vence o atrito e zumbe parado em vez de
# andar devagar. Se o carro travar, suba VELOCIDADE_URBANA.
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
# O carro tem que andar SEMPRE PELO LADO DIREITO da pista, ou seja, mais
# perto da CONTINUA (borda direita) do que da pontilhada (divisoria
# central). Por isso o sinal e NEGATIVO. Alem de seguir a regra, isso
# afasta o carro da contramao: mesmo errando um pouco, ele erra pra longe
# da divisoria, nao pra cima dela. (O vies POSITIVO usado antes colava o
# carro na divisoria e a visao chegava a "reengatar" no par de linhas da
# pista oposta depois de uma curva.)
#
# Magnitude 0.40 = alvo deslocado 40% da meia-largura da pista pra direita
# do centro. Nao baixe muito: o controle tem zona morta (DEAD_ZONE_URBANO
# 0.07 e SERVO_DEADBAND_URBANO 2 graus, que com PID_KP_URBANO=0.24 ignora
# erro menor que ~0.17) e um vies pequeno some dentro dela -- o carro
# continua andando no meio. Se a roda direita encostar/pisar na continua,
# baixe pra -0.30; se ainda andar no meio, suba pra -0.50.
# Teto: config.LANE_BIAS_LIMITE.
LANE_BIAS_FRAC_URBANO = -0.40

# Em mao direita, a linha CONTINUA (borda da rua) fica a DIREITA do carro
# e a pontilhada a esquerda. Se a visao reportar continua na ESQUERDA, o
# carro esta na via contraria -- o main avisa no log.
LADO_CONTINUO_ESPERADO = "direita"

# FORCA o lado do vies em vez de deixar a visao "adivinhar" qual lado e a
# continua (contando buracos na pontilhada). Adivinhar falha justamente nos
# trechos onde mais importa: logo depois de uma curva, ou onde a pontilhada
# esta apagada/suja. Como a regra e "mao direita", a resposta e conhecida de
# antemao. A deteccao automatica continua rodando so pra gerar o aviso de
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
ZEBRA_SCAN_ROWS = 10
ZEBRA_TOP_FRAC = 0.25
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
ZEBRA_PARADA_FRAC = 0.42

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
DEAD_ZONE_URBANO = 0.07
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

MANOBRA_AVANCO_DIR_S = 0.55
MANOBRA_AVANCO_ESQ_S = 1.25
MANOBRA_CURVA_DIR_S  = 0.80
MANOBRA_CURVA_ESQ_S  = 1.55
MANOBRA_TRAVESSIA_S  = 1.50
MANOBRA_TURN_MAG_DIR = 0.95
MANOBRA_TURN_MAG_ESQ = 0.80   # menos esterco = raio maior = arco aberto

MANOBRA_AUTOESCALA = True     # False so depois de congelar a velocidade

if MANOBRA_AUTOESCALA and VELOCIDADE_MANOBRA > 0:
    _k = VELOCIDADE_MANOBRA_REF / VELOCIDADE_MANOBRA
    MANOBRA_AVANCO_DIR_S *= _k
    MANOBRA_AVANCO_ESQ_S *= _k
    MANOBRA_CURVA_DIR_S  *= _k
    MANOBRA_CURVA_ESQ_S  *= _k
    MANOBRA_TRAVESSIA_S  *= _k
    ZEBRA_COOLDOWN_POS_MANOBRA_S *= _k

MANOBRA_REENGATE_FRAMES = 25  # frames sem faixa tolerados no reengate

# =====================================================================
# 7. PARADA / DESTINO
# =====================================================================
PARADA_FREIO_S    = 0.25
PARADA_TEMPO_S    = 3.0    # parado na faixa, em TODO cruzamento
PARADA_DEFINITIVA = True   # placa STOP = destino, encerra a missao

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
