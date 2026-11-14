"""
navigator.py - a "cabeca" do motorista urbano.

MODELO DE DECISAO (mudou depois de ver a arena da FIRA)
-------------------------------------------------------
    PLACA (ArUco)        -> O QUE fazer no proximo cruzamento
    FAIXA DE PEDESTRE    -> QUANDO fazer

A placa nao executa mais nada sozinha: ela ARMA uma intencao. A intencao
fica guardada ate a zebra do cruzamento aparecer -- ai a manobra dispara.

Por que isso e melhor que a versao anterior (disparar por distancia da
placa): a placa fica na LATERAL da rua e a camera e baixa, entao o
marcador some do quadro bem antes de o carro chegar ao cruzamento.
Estimar "quanto falta" pela area do marcador funciona, mas com erro de
varios centimetros, e esse erro vira curva iniciada cedo/tarde demais. A
zebra, por outro lado, esta bem na frente do carro e diz com precisao de
frame que o cruzamento e AGORA. Numa arena onde todo cruzamento tem
zebra, essa e a referencia mais confiavel disponivel.

Fallback continua existindo: se a intencao estiver armada e nenhuma zebra
for detectada dentro de INTENCAO_VALIDA_S, ela e descartada (nao vira
manobra as cegas no meio da rua -- isso seria pior que nao manobrar).

Estados
-------
SEGUINDO     : PID no comando. Estado normal.
AVANCANDO    : entrando no cruzamento em linha reta, sem PID.
ABRINDO      : so curva a DIREITA: servo um pouco pra esquerda, pra abrir o
               caminho e nao raspar na placa do canto. Sem PID.
CURVANDO     : servo no talo por tempo fixo, sem PID.
TRAVESSANDO  : cruzando em frente, em reta, sem PID.
REENGATANDO  : PID de volta, tolerando ausencia de faixa por N frames.
PARANDO      : frenagem (na faixa de pedestre, como manda a lei).
RECUANDO     : RE em linha reta quando o carro passou da faixa (ou a deixou
               quase debaixo do capo): volta ate a zebra reaparecer a uma
               distancia segura. So depois disso comeca a espera.
PARADO       : parado (minimo PARADA_TEMPO_S; apos re, minimo RE_ESPERA_MIN_S).
FIM          : missao encerrada.
"""

import time
from collections import deque

import config
import config_urbano as cfgu


SEGUINDO = "SEGUINDO"
APROXIMANDO = "APROXIMANDO"
AVANCANDO = "AVANCANDO"
ABRINDO = "ABRINDO"
CURVANDO = "CURVANDO"
TRAVESSANDO = "TRAVESSANDO"
REENGATANDO = "REENGATANDO"
PARANDO = "PARANDO"
RECUANDO = "RECUANDO"
PARADO = "PARADO"
FIM = "FIM"

# Estados em que uma placa nova AINDA pode ser aceita.
# Inclui a parada obrigatoria de proposito: a placa fica NO cruzamento,
# entao ela normalmente e lida exatamente enquanto o carro esta chegando
# ou ja parado na faixa. Recusar placa nessa janela e recusar a placa
# justamente na hora em que ela aparece -- foi esse o bug que fazia o
# carro parar certo e depois seguir reto ignorando a ordem.
_ACEITA_PLACA = (SEGUINDO, REENGATANDO, APROXIMANDO, PARANDO, RECUANDO, PARADO)

# Estados em que a decisao JA foi tomada e o carro esta executando. Aqui
# sim a placa e recusada: no meio do cruzamento o que a camera ve e quase
# sempre a placa da rua transversal, nao uma ordem nova.
_EXECUTANDO = (AVANCANDO, ABRINDO, CURVANDO, TRAVESSANDO, FIM)


class Comando:
    """O que o main deve fazer NESTE frame."""
    __slots__ = ("usa_faixa", "turn", "speed", "resetar_pid",
                 "tolera_perdido", "estado", "fim", "frear")

    def __init__(self):
        self.usa_faixa = True
        self.turn = 0.0
        self.speed = 0.0
        self.resetar_pid = False
        self.tolera_perdido = False
        self.estado = SEGUINDO
        self.fim = False
        self.frear = False    # main deve chamar motor.brake() neste frame


class Navigator:
    def __init__(self):
        self.estado = SEGUINDO
        self.t_estado = time.time()
        self.sentido = 0.0
        self.pos_curva = None
        self.pos_parada = None     # o que executar DEPOIS da parada obrigatoria
        self.frames_reengate = 0
        self.log = []

        # intencao armada pela placa, aguardando o cruzamento
        self.intencao = None        # 'direita' | 'esquerda' | 'frente' | 'parar'
        self.intencao_t = 0.0
        self.intencao_origem = ""

        self._zebra_anterior = False
        self._zebra_frac = 0.0
        self._zebra_bloqueio_ate = 0.0
        self._t_fim_manobra = 0.0   # quando a ultima manobra terminou
        self._zebra_livre = 0       # frames SEGUIDOS sem zebra desde o fim da manobra
        self._zebra_max = 0.0       # maior frac visto desde que a zebra foi avistada
        self._zebra_sem = 0         # frames SEGUIDOS sem enxergar barra nenhuma
        self._re_n = 0              # re's ja feitas neste cruzamento
        self._re_t_seguro = None    # instante (na re) em que chegou no ponto seguro
        self._re_arco_s = 0.0       # tempo recuando com o volante esterçado (p/ compensar a curva)
        self._re_viu = False        # a zebra foi vista durante a re atual
        self._frac_hist = deque(maxlen=10)  # ultimos frac (carro parou de deslizar?)

        self._bloqueio_ate = 0.0
        self._bloqueio_tentativas = 0

        self.em_tunel = False
        self._tunel_ate = 0.0
        self._backup_tunel = None

        # True quando pos_parada veio de placa CONFIRMADA (nao do default
        # "frente" por falta de leitura). Ver PARADO em _passo().
        self._pos_parada_confirmada = False

    # ------------------------------------------------------------------
    def _muda(self, novo):
        self.estado = novo
        self.t_estado = time.time()

    def _dt_estado(self):
        return time.time() - self.t_estado

    def _registrar(self, texto):
        self.log.append(f"[{time.strftime('%H:%M:%S')}] {texto}")
        print(f"  >> {texto}")

    # ------------------------------------------------------------------
    # TUNEL: nao e estado, e um MODIFICADOR. O carro continua seguindo a
    # faixa; o que muda e a tolerancia da visao e o teto de velocidade.
    # Feito mexendo no config em runtime e restaurando na saida, pra nao
    # espalhar 'if tunel' dentro do vision.py.
    # ------------------------------------------------------------------
    def _entrar_tunel(self):
        if self.em_tunel:
            self._tunel_ate = time.time() + cfgu.TUNEL_DURACAO_S
            return
        self._backup_tunel = (config.TOPHAT_FATOR, config.V_MIN_ABS,
                              config.MAX_FRAMES_PERDIDO)
        config.TOPHAT_FATOR = cfgu.TUNEL_TOPHAT_FATOR
        config.V_MIN_ABS = cfgu.TUNEL_V_MIN_ABS
        config.MAX_FRAMES_PERDIDO = cfgu.TUNEL_MAX_FRAMES_PERDIDO
        self.em_tunel = True
        self._tunel_ate = time.time() + cfgu.TUNEL_DURACAO_S
        self._registrar("TUNEL: entrando (visao permissiva, velocidade reduzida)")

    def _sair_tunel(self):
        if not self.em_tunel:
            return
        config.TOPHAT_FATOR, config.V_MIN_ABS, config.MAX_FRAMES_PERDIDO = self._backup_tunel
        self.em_tunel = False
        self._registrar("TUNEL: saindo (visao normal)")

    # ------------------------------------------------------------------
    def _armar(self, tipo, origem):
        # Se o carro JA esta chegando na faixa ou parado nela, a decisao do
        # que fazer depois da parada ainda nao foi executada -- entao a
        # placa que acabou de ser lida corrige essa decisao em vez de
        # ficar esperando o proximo cruzamento (que nunca viria).
        if self.estado in (APROXIMANDO, PARANDO, RECUANDO, PARADO):
            anterior = self.pos_parada
            self.pos_parada = tipo
            self._pos_parada_confirmada = True
            self._registrar(f"placa '{origem}' lida NA parada -> decisao "
                            f"atualizada: {anterior} -> {tipo}")
            return

        self.intencao = tipo
        self.intencao_t = time.time()
        self.intencao_origem = origem
        self._registrar(f"intencao ARMADA: {tipo} (placa: {origem}) "
                        f"-- aguardando a faixa de pedestre")

    def on_evento(self, ev):
        """Recebe uma placa confirmada pelo signs.py."""
        if ev is None:
            return
        if self.estado in _EXECUTANDO:
            self._registrar(f"placa '{ev.tipo}' ignorada (executando: {self.estado})")
            return

        tipo = ev.tipo

        if tipo == "tunel":
            self._sair_tunel() if self.em_tunel else self._entrar_tunel()
            return

        if tipo in ("direita", "esquerda", "frente", "parar"):
            self._armar(tipo, tipo)
            return

        if tipo in ("proibido_entrar", "sem_saida"):
            # As duas placas ficam no INICIO da rua: ve-las de frente
            # significa "a rua reta esta vedada" -> desvia no cruzamento.
            agora = time.time()
            if agora < self._bloqueio_ate:
                self._bloqueio_tentativas += 1   # a 1a preferencia ja falhou
            else:
                self._bloqueio_tentativas = 0
            self._bloqueio_ate = agora + cfgu.BLOQUEIO_MEMORIA_S

            idx = self._bloqueio_tentativas % len(cfgu.BLOQUEIO_PREFERENCIA)
            escolha = cfgu.BLOQUEIO_PREFERENCIA[idx]
            self._armar(escolha, f"{tipo} -> desvio pela {escolha}")
            return

        self._registrar(f"placa desconhecida ignorada: {tipo}")

    # ------------------------------------------------------------------
    def _disparar(self, tipo):
        """Zebra avistada: SEMPRE para antes dela. A manobra so acontece
        depois dos 3 segundos parado -- e a regra de transito, nao uma
        opcao: faixa de pedestre e parada obrigatoria, tenha placa ou nao.
        """
        self._zebra_bloqueio_ate = time.time() + cfgu.ZEBRA_COOLDOWN_S
        self.pos_parada = tipo
        self._pos_parada_confirmada = self.intencao is not None
        self._zebra_max = 0.0
        self._re_n = 0
        self._re_arco_s = 0.0
        self.intencao = None
        self._registrar(f"faixa de pedestre a frente -> parando "
                        f"(depois: {tipo})")
        self._muda(APROXIMANDO)

    def _bloquear_zebra_saida(self):
        """A manobra acabou: a zebra da rua de DESTINO ja esta logo ali.
        Ignora bordas de zebra por um tempo, senao o carro para uma 2a vez
        de 3s na saida do cruzamento (o cooldown de _disparar vencia durante
        a propria parada obrigatoria, antes da manobra comecar)."""
        self._zebra_bloqueio_ate = time.time() + cfgu.ZEBRA_COOLDOWN_POS_MANOBRA_S
        self._t_fim_manobra = time.time()
        self._zebra_livre = 0

    def _executar_pos_parada(self):
        """Chamado quando a parada obrigatoria termina."""
        tipo = self.pos_parada or "frente"
        self.pos_parada = None
        self._pos_parada_confirmada = False

        if tipo == "parar" and cfgu.PARADA_DEFINITIVA:
            self._registrar("MISSAO ENCERRADA no destino.")
            self._muda(FIM)
            return

        if tipo in ("direita", "esquerda"):
            self.sentido = 1.0 if tipo == "direita" else -1.0
            self.pos_curva = CURVANDO
            self._registrar(f"retomando: manobra para a {tipo}")
        else:
            self.pos_curva = TRAVESSANDO
            self._registrar("retomando: seguindo em frente")
        self._muda(AVANCANDO)

    # ------------------------------------------------------------------
    def update(self, leitura_ok, zebra=None):
        """leitura_ok = visao entregou faixa fresca e confiavel.
        zebra        = CrosswalkResult (ou bool, por compatibilidade)."""
        if zebra is None or zebra is False:
            zebra_presente, zebra_frac = False, 0.0
        elif zebra is True:
            zebra_presente, zebra_frac = True, 1.0
        else:
            zebra_presente = zebra.presente
            zebra_frac = zebra.frac_proximidade
        self._zebra_frac = zebra_frac
        # "visivel" = alguma barra de zebra na varredura NESTE frame
        self._zebra_sem = 0 if zebra_frac > 0.0 else self._zebra_sem + 1
        self._frac_hist.append(zebra_frac)
        if self.estado in (APROXIMANDO, PARANDO):
            self._zebra_max = max(self._zebra_max, zebra_frac)
        cmd = Comando()
        agora = time.time()

        if self.em_tunel and agora > self._tunel_ate:
            self._sair_tunel()

        # intencao vence por tempo (placa de outra rua / carro errou o caminho)
        if self.intencao and (agora - self.intencao_t) > cfgu.INTENCAO_VALIDA_S:
            self._registrar(f"intencao '{self.intencao}' expirou sem cruzamento -- descartada")
            self.intencao = None

        # ---- borda de subida da zebra, so fora de manobra ----
        borda = (zebra_presente and not self._zebra_anterior
                 and self.estado in (SEGUINDO, REENGATANDO))
        zebra_nova = borda and agora >= self._zebra_bloqueio_ate

        # ZEBRA DO PROXIMO CRUZAMENTO DENTRO DA JANELA DE BLOQUEIO. O bloqueio
        # existe pra ignorar a zebra de SAIDA do cruzamento que acabou de ser
        # feito, mas em ruas curtas a zebra do cruzamento SEGUINTE aparece
        # ainda dentro dele -- e o carro passava por cima sem parar. Vale como
        # zebra NOVA se: ja passou ZEBRA_NOVA_MIN_S do fim da manobra, houve
        # pelo menos ZEBRA_NOVA_LIVRE_FRAMES frames SEM zebra (a de saida ja
        # ficou pra tras) e ela apareceu LONGE (frac pequeno = vindo de frente).
        if (borda and not zebra_nova
                and (agora - self._t_fim_manobra) >= cfgu.ZEBRA_NOVA_MIN_S
                and self._zebra_livre >= cfgu.ZEBRA_NOVA_LIVRE_FRAMES
                and 0.0 < zebra_frac <= cfgu.ZEBRA_NOVA_FRAC_MAX):
            self._registrar("zebra de um NOVO cruzamento (dentro do bloqueio "
                            "pos-manobra) -- vou parar")
            zebra_nova = True

        if zebra_presente or zebra_frac > 0.0:
            self._zebra_livre = 0
        else:
            self._zebra_livre += 1
        self._zebra_anterior = zebra_presente

        if zebra_nova:
            # Sem placa armada o correto e atravessar reto: o cruzamento nao
            # tem faixa pra seguir e a zebra ja estragou a leitura da visao.
            # Melhor uma travessia reta controlada do que deixar o PID
            # esterçar em cima das barras da zebra.
            self._disparar(self.intencao or "frente")

        # roda o passo de estado; se a transicao acontecer NESTE frame,
        # roda de novo pra ja emitir o comando do estado novo (senao o
        # primeiro frame de cada manobra sai com turn=0)
        for _ in range(2):
            antes = self.estado
            self._passo(cmd)
            if self.estado == antes:
                break

        if self.estado == REENGATANDO:
            cmd.usa_faixa = True
            cmd.tolera_perdido = True
            self.frames_reengate += 1
            if leitura_ok:
                self._registrar("faixa reengatada")
                self._muda(SEGUINDO)
            elif self.frames_reengate > cfgu.MANOBRA_REENGATE_FRAMES:
                self._registrar("reengate falhou -- devolvendo pro modo perdido")
                self._muda(SEGUINDO)

        cmd.estado = self.estado
        return cmd

    # ------------------------------------------------------------------
    def _passo(self, cmd):
        e = self.estado
        dt = self._dt_estado()

        if e == APROXIMANDO:
            # rola devagar ate a zebra chegar perto do para-choque.
            # O gatilho e a POSICAO da zebra na imagem, nao um tempo fixo:
            # tempo fixo erraria a distancia toda vez que a velocidade de
            # chegada fosse diferente (bateria, curva antes, inclinacao).
            cmd.usa_faixa = False
            cmd.speed = cfgu.VELOCIDADE_APROXIMACAO
            chegou = self._zebra_frac >= cfgu.ZEBRA_PARADA_FRAC
            if chegou or dt >= cfgu.APROXIMACAO_MAX_S:
                if not chegou:
                    self._registrar("perdi a zebra na chegada -- parando assim mesmo")
                self._muda(PARANDO)

        elif e == AVANCANDO:
            cmd.usa_faixa = False
            cmd.speed = cfgu.VELOCIDADE_MANOBRA
            if self.pos_curva == CURVANDO:
                limite = (cfgu.MANOBRA_AVANCO_DIR_S if self.sentido > 0
                          else cfgu.MANOBRA_AVANCO_ESQ_S)
            else:
                limite = cfgu.MANOBRA_AVANCO_DIR_S
            if dt >= limite:
                proximo = self.pos_curva or TRAVESSANDO
                # curva a DIREITA: antes de girar, abre o caminho (servo
                # pra esquerda) -- a esquerda e a travessia nao mudam
                if (proximo == CURVANDO and self.sentido > 0
                        and cfgu.MANOBRA_ABERTURA_DIR_S > 0):
                    proximo = ABRINDO
                self._muda(proximo)

        elif e == ABRINDO:
            cmd.usa_faixa = False
            cmd.turn = -cfgu.MANOBRA_ABERTURA_TURN_DIR     # negativo = esquerda
            cmd.speed = cfgu.VELOCIDADE_MANOBRA
            if dt >= cfgu.MANOBRA_ABERTURA_DIR_S:
                self._muda(CURVANDO)

        elif e == CURVANDO:
            cmd.usa_faixa = False
            if self.sentido > 0:
                cmd.turn = cfgu.MANOBRA_TURN_MAG_DIR
                limite = cfgu.MANOBRA_CURVA_DIR_EFETIVA_S
                limite = min(1.5 * limite, max(0.5 * limite, limite - self._comp_arco(cfgu.MANOBRA_TURN_MAG_DIR)))
            else:
                cmd.turn = -cfgu.MANOBRA_TURN_MAG_ESQ
                limite = cfgu.MANOBRA_CURVA_ESQ_S
                limite = min(1.5 * limite, max(0.5 * limite, limite - self._comp_arco(cfgu.MANOBRA_TURN_MAG_ESQ)))
            cmd.speed = cfgu.VELOCIDADE_MANOBRA
            if dt >= limite:
                self.frames_reengate = 0
                cmd.resetar_pid = True
                self._bloquear_zebra_saida()
                self._muda(REENGATANDO)

        elif e == TRAVESSANDO:
            cmd.usa_faixa = False
            cmd.speed = cfgu.VELOCIDADE_MANOBRA
            if dt >= cfgu.MANOBRA_TRAVESSIA_S:
                self.frames_reengate = 0
                cmd.resetar_pid = True
                self._bloquear_zebra_saida()
                self._muda(REENGATANDO)

        elif e == PARANDO:
            cmd.usa_faixa = False
            # rampa: travar seco joga o carro pra frente e desalinha
            # FREIO ATIVO em vez de rampa: a rampa era elegante no papel,
            # mas ela CONTINUA ANDANDO durante a desaceleracao -- e a
            # distancia percorrida ali depende da bateria e do piso, que e
            # exatamente o que nao se pode ter numa parada obrigatoria.
            cmd.speed = 0.0
            cmd.frear = True
            if dt >= cfgu.PARADA_FREIO_S:
                decisao = self._avalia_re(dt - cfgu.PARADA_FREIO_S)
                if decisao is True:
                    self._re_n += 1
                    self._registrar(f"passou da faixa (frac {self._zebra_frac:.2f}, "
                                    f"max {self._zebra_max:.2f}) -> RE "
                                    f"({self._re_n}/{cfgu.RE_TENTATIVAS_MAX})")
                    self._re_viu = False
                    self._re_t_seguro = None
                    self._muda(RECUANDO)
                elif decisao is False:
                    self._registrar(f"PARADO antes da faixa ({self._espera_parado():.0f}s)")
                    self._muda(PARADO)
                # None = a zebra piscou agora; espera mais um frame pra decidir

        elif e == RECUANDO:
            cmd.usa_faixa = False
            arco = self._turn_arco_re()
            cmd.turn = max(-1.0, min(1.0, arco + cfgu.RE_TURN))
            cmd.speed = -cfgu.VELOCIDADE_RE
            if self._zebra_frac > 0.0:
                self._re_viu = True
            visivel_ok = (self._zebra_frac > 0.0
                          and self._zebra_frac <= cfgu.RE_ALVO_FRAC)
            # a zebra ja foi vista nesta re e SUMIU de novo: foi pro fundo
            # da imagem (longe), ou seja, ja recuou o bastante
            longe = self._re_viu and self._zebra_sem >= 3
            seguro = visivel_ok or longe
            if seguro and self._re_t_seguro is None:
                self._re_t_seguro = dt
            # chegou no ponto seguro: continua mais RE_FOLGA_S (re um pouco maior)
            chegou = (self._re_t_seguro is not None
                      and dt >= max(cfgu.RE_MIN_S, self._re_t_seguro) + cfgu.RE_FOLGA_S)
            if chegou or dt >= cfgu.RE_MAX_S + cfgu.RE_FOLGA_S:
                self._re_arco_s += dt if arco != 0.0 else 0.0
                if not seguro:
                    self._registrar("re: tempo maximo -- parando assim mesmo")
                else:
                    self._registrar("re concluida (zebra a frac "
                                    f"{self._zebra_frac:.2f})" if visivel_ok
                                    else "re concluida (zebra ficou longe)")
                self._zebra_max = 0.0
                self._muda(PARANDO)

        elif e == PARADO:
            cmd.usa_faixa = False
            cmd.speed = 0.0
            cmd.frear = True      # segura parado (evita rolar em desnivel)
            # Os PARADA_TEMPO_S sao minimo obrigatorio (lei de transito, vale
            # sempre). Se a placa AINDA nao foi confirmada nesse momento,
            # continua parado tentando confirmar (parado a leitura fica mais
            # facil: sem vibracao, sem blur de movimento) ate
            # PARADA_TEMPO_EXTRA_MAX_S a mais -- so ai desiste e segue reto.
            espera = self._espera_parado()
            tempo_esgotado = dt >= (espera + cfgu.PARADA_TEMPO_EXTRA_MAX_S)
            if dt >= espera and (self._pos_parada_confirmada or tempo_esgotado):
                if not self._pos_parada_confirmada:
                    self._registrar("placa nao confirmada a tempo -- seguindo reto por padrao")
                cmd.resetar_pid = True
                self.frames_reengate = 0
                self._executar_pos_parada()
                if self.estado == FIM:
                    cmd.fim = True

        elif e == FIM:
            cmd.usa_faixa = False
            cmd.speed = 0.0
            cmd.fim = True

        elif e == REENGATANDO:
            pass      # tratado no update() (precisa de leitura_ok)

        else:
            cmd.usa_faixa = True

    # ------------------------------------------------------------------
    def _turn_arco_re(self):
        """Esterco da re: oposto ao lado da curva que vem depois (arco maior)."""
        if cfgu.RE_ARCO_TURN <= 0:
            return 0.0
        if self.pos_parada == "direita":
            t = -cfgu.RE_ARCO_TURN
        elif self.pos_parada == "esquerda":
            t = +cfgu.RE_ARCO_TURN
        else:
            return 0.0
        return -t if cfgu.RE_ARCO_INVERTE else t

    def _comp_arco(self, mag_curva):
        """Tempo a tirar da curva: o arco da re ja girou o carro um pouco."""
        if not cfgu.RE_ARCO_COMPENSA or self._re_arco_s <= 0 or mag_curva <= 0:
            return 0.0
        comp = (cfgu.RE_ARCO_TURN / mag_curva) * self._re_arco_s
        return -comp if cfgu.RE_ARCO_INVERTE else comp   # invertido: gira pro lado errado

    def _espera_parado(self):
        """Tempo minimo parado. Depois de uma RE, nunca menos que
        RE_ESPERA_MIN_S (contado a partir de o carro parar de vez)."""
        if self._re_n > 0:
            return max(cfgu.PARADA_TEMPO_S, cfgu.RE_ESPERA_MIN_S)
        return cfgu.PARADA_TEMPO_S

    def _avalia_re(self, extra):
        """Parado (freio feito): precisa dar re? True / False / None (ainda
        nao da pra dizer -- a zebra piscou; no maximo 0.5 s de espera)."""
        if not cfgu.RE_ATIVA or self._re_n >= cfgu.RE_TENTATIVAS_MAX:
            return False
        # so decide com o carro PARADO de verdade: o frac da zebra para de
        # mudar. Frear nao e instantaneo -- decidir no meio do deslize usa
        # uma posicao que ainda vai mudar.
        h = self._frac_hist
        parou = len(h) == h.maxlen and (max(h) - min(h)) <= 0.01
        if not parou and extra < 0.8:
            return None
        if self._zebra_frac > 0.0:                     # zebra visivel
            return self._zebra_frac >= cfgu.RE_GATILHO_FRAC
        if self._zebra_sem >= 3 or extra >= 0.5:       # sumiu de vez
            return self._zebra_max >= cfgu.RE_PERDEU_FRAC
        return None

    def teto_velocidade(self):
        if self.em_tunel:
            return cfgu.VELOCIDADE_TUNEL
        return cfgu.VELOCIDADE_BASE_URBANO

    def hud(self):
        alvo = self.intencao or "-"
        return f"{self.estado} | intencao={alvo}" + (" | TUNEL" if self.em_tunel else "")

    def resumo(self):
        return "\n".join(self.log) if self.log else "(nenhuma placa obedecida)"
