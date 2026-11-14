"""
signs.py - leitura das placas de sinalizacao (marcadores ArUco).

Responsabilidade unica: olhar o frame e dizer QUAL PLACA esta na frente e
A QUE DISTANCIA. Nao decide nada, nao toca em GPIO, nao conhece o PID.
Quem decide o que fazer com a placa e o navigator.py.

Duas camadas aqui, de proposito:

  SignDetector -> leitura CRUA, frame a frame. Sem memoria.
  SignTracker  -> leitura ESTAVEL, com memoria. Confirma por repeticao,
                  mede aproximacao, aplica cooldown e emite EVENTO.

A separacao importa porque o ArUco erra de um jeito especifico: ele quase
nunca inventa um marcador que nao existe, mas ele TROCA O ID quando a
imagem esta borrada ou muito inclinada. Um unico frame nunca deve virar
uma manobra. Por isso o tracker so emite evento depois de N leituras
concordantes -- e um filtro de voto, nao de deteccao.
"""

import time

import cv2
import numpy as np

import config_urbano as cfgu


class Leitura:
    """Uma placa vista em UM frame."""
    __slots__ = ("id", "tipo", "dist", "cx", "cy", "lado_px")

    def __init__(self, id_, tipo, dist, cx, cy, lado_px):
        self.id = id_
        self.tipo = tipo          # 'direita', 'parar', ... ou None se ID desconhecido
        self.dist = dist          # metros (estimado)
        self.cx = cx              # centro do marcador no frame de captura
        self.cy = cy
        self.lado_px = lado_px    # lado medio do marcador em pixels

    def __repr__(self):
        return f"<Leitura id={self.id} {self.tipo} {self.dist:.2f}m>"


class SignDetector:
    """Deteccao crua de ArUco. Compativel com OpenCV antigo e novo."""

    def __init__(self, dict_name=None):
        nome = dict_name or cfgu.ARUCO_DICT
        self.dict_name = nome
        dic_id = getattr(cv2.aruco, nome)

        # OpenCV >= 4.7 mudou a API do aruco. Suporta as duas porque o Pi
        # costuma vir com a versao do repositorio, que e mais velha.
        # Dois conjuntos de parametros:
        #   RAPIDO     : o padrao do OpenCV (~7 ms), pra quando a imagem e boa.
        #   TOLERANTE  : aceita marcador borrado (movimento/vibracao) e com
        #                borda deformada. Na bancada de teste (marcador sintetico
        #                com borrao de 9 px) o padrao achava 8 de 40; o
        #                tolerante 40 de 40, sem nenhum ID trocado. Custa ~3x,
        #                entao so roda quando o rapido nao achou nada.
        def _tolerante(p):
            p.polygonalApproxAccuracyRate = 0.05
            p.maxErroneousBitsInBorderRate = 0.5
            return p

        if hasattr(cv2.aruco, "ArucoDetector"):
            dicionario = cv2.aruco.getPredefinedDictionary(dic_id)
            self._detector = cv2.aruco.ArucoDetector(
                dicionario, cv2.aruco.DetectorParameters())
            self._detector_tol = cv2.aruco.ArucoDetector(
                dicionario, _tolerante(cv2.aruco.DetectorParameters()))
            self._api_nova = True
        else:
            self._dicionario = cv2.aruco.Dictionary_get(dic_id)
            self._params = cv2.aruco.DetectorParameters_create()
            self._params_tol = _tolerante(cv2.aruco.DetectorParameters_create())
            self._api_nova = False

        self.ultimo_corners = []
        self.ultimo_ids = []

    # ------------------------------------------------------------------
    def _detect_raw(self, gray, tolerante=False):
        if self._api_nova:
            det = self._detector_tol if tolerante else self._detector
            corners, ids, _ = det.detectMarkers(gray)
        else:
            params = self._params_tol if tolerante else self._params
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self._dicionario, parameters=params)
        return corners, ids

    def detect(self, frame, insistir=False):
        """insistir=True: se a deteccao rapida nao achar nada, tenta de novo
        com os parametros tolerantes (mais lento, acha marcador borrado)."""
        """Devolve lista de Leitura, da MAIS PROXIMA pra mais distante."""
        h = frame.shape[0]
        y_lim = int(h * cfgu.SIGN_ROI_TOP_FRAC)
        roi = frame[:y_lim, :]

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        corners, ids = self._detect_raw(gray)
        if insistir and (ids is None or len(ids) == 0):
            corners, ids = self._detect_raw(gray, tolerante=True)

        self.ultimo_corners = corners
        self.ultimo_ids = [] if ids is None else ids.flatten().tolist()

        if ids is None or len(ids) == 0:
            return []

        leituras = []
        for c, i in zip(corners, ids.flatten()):
            pts = c.reshape(4, 2)
            # lado medio: media dos 4 lados do quadrilatero. Mais robusto
            # que largura/altura sozinhas quando o marcador esta inclinado.
            lados = [np.linalg.norm(pts[k] - pts[(k + 1) % 4]) for k in range(4)]
            lado_px = float(np.mean(lados))
            if lado_px <= 1.0:
                continue

            # pinhole: dist = (tamanho_real * focal) / tamanho_em_pixels
            dist = (cfgu.MARKER_TAMANHO_M * cfgu.FOCAL_PX) / lado_px

            cx = float(pts[:, 0].mean())
            cy = float(pts[:, 1].mean())
            leituras.append(Leitura(int(i), cfgu.PLACAS.get(int(i)),
                                    dist, cx, cy, lado_px))

        leituras.sort(key=lambda l: l.dist)
        return leituras

    def desenhar(self, frame):
        """Marca as deteccoes no frame (so pra debug/HUD)."""
        if len(self.ultimo_corners) == 0:
            return frame
        ids = np.array(self.ultimo_ids).reshape(-1, 1)
        cv2.aruco.drawDetectedMarkers(frame, self.ultimo_corners, ids)
        return frame


class Evento:
    """Uma placa CONFIRMADA e pronta pra ser obedecida."""
    __slots__ = ("tipo", "id", "dist")

    def __init__(self, tipo, id_, dist):
        self.tipo = tipo
        self.id = id_
        self.dist = dist

    def __repr__(self):
        return f"<Evento {self.tipo} id={self.id} {self.dist:.2f}m>"


class SignTracker:
    """Transforma leituras cruas em EVENTOS confiaveis.

    Regra de acionamento (as duas valem, o que vier primeiro):
      a) a placa confirmada chegou a menos de SIGN_DIST_ACIONA_M; ou
      b) a placa confirmada ja estava proxima e SUMIU do quadro.

    O caso (b) nao e detalhe: com a camera baixa e a placa na lateral da
    pista, o marcador sai do campo de visao ANTES de o carro chegar ao
    cruzamento. Um sistema que so usa (a) simplesmente nunca aciona em
    algumas aproximacoes -- e o robo passa reto pela placa.
    """

    def __init__(self, pular_frames=None):
        """pular_frames: roda a deteccao 1 a cada N chamadas de update().
        None = usa cfgu.SIGN_SKIP_FRAMES (camera unica, update todo frame).
        1 = nao salteia aqui (quem chama ja salteia -- duas cameras)."""
        self.detector = SignDetector()
        self._skip = (cfgu.SIGN_SKIP_FRAMES if pular_frames is None
                      else max(1, int(pular_frames)))
        # Distancia em que a placa confirmada ARMA a intencao. O main troca
        # esse valor em tempo de execucao: com o carro PARADO na zebra ele
        # sobe pra SIGN_DIST_ACIONA_PARADO_M (a placa nao vai chegar mais
        # perto, e antes ficava sem armar e o carro seguia reto).
        self.dist_aciona = cfgu.SIGN_DIST_ACIONA_M
        self._votos = {}          # id -> frames seguidos confirmando
        self._ultima_dist = {}    # id -> ultima distancia vista
        self._sumido = {}         # id -> frames desde que sumiu (se ja confirmado e perto)
        self._cooldown = {}       # id -> timestamp ate quando ignorar
        self._frame_n = 0
        self.visivel = []         # ultimas leituras validas (pra HUD)
        self.desconhecidos = {}   # id -> frames, pra IDs fora do mapa PLACAS
        self._avisados = set()
        # main liga isso com o carro parado/chegando na zebra: ai a leitura
        # insiste (tolerante) em TODO frame, e ninguem esta andando pra
        # reclamar do custo. Andando, so insiste a cada 3 leituras.
        self.modo_parado = False
        self._diag_t = {}         # id -> ultimo aviso de diagnostico (throttle)
        self.cruas = []           # leituras cruas do ultimo frame (antes dos filtros)

    def _diagnostica(self, l):
        """Placa lida pelo ArUco mas DESCARTADA pelos filtros: explica o motivo.
        Sem isso o HUD mostrava 'placas: -' e parecia que a camera nao viu nada."""
        if l.tipo is None:
            return                      # ja avisado em 'desconhecidos'
        if self._em_cooldown(l.id):
            motivo = "em cooldown (acabou de ser obedecida)"
        elif l.dist < cfgu.SIGN_DIST_MIN_M:
            motivo = f"PERTO demais (min {cfgu.SIGN_DIST_MIN_M:.2f} m)"
        elif l.dist > cfgu.SIGN_DIST_MAX_M:
            motivo = f"LONGE demais (max {cfgu.SIGN_DIST_MAX_M:.2f} m)"
        else:
            return
        agora = time.time()
        if agora - self._diag_t.get(l.id, 0.0) < 1.0:
            return
        self._diag_t[l.id] = agora
        print(f"  [placa] id {l.id} ({l.tipo}) lido a {l.dist:.2f} m "
              f"(lado {l.lado_px:.0f}px) -- DESCARTADO: {motivo}")

    def _em_cooldown(self, id_):
        return time.time() < self._cooldown.get(id_, 0.0)

    def registrar_execucao(self, id_):
        """Chame quando a placa foi obedecida -> nao reage a ela de novo."""
        self._cooldown[id_] = time.time() + cfgu.SIGN_COOLDOWN_S
        self._votos.pop(id_, None)
        self._sumido.pop(id_, None)
        self._ultima_dist.pop(id_, None)

    def update(self, frame):
        """Processa um frame. Devolve Evento ou None."""
        self._frame_n += 1

        # amostragem: nao precisa rodar ArUco em todo frame se a velocidade
        # e baixa. Nos frames pulados, o estado (votos/sumido) fica parado,
        # o que e correto -- nao conta ausencia que nao foi verificada.
        if self._skip > 1 and (self._frame_n % self._skip):
            return None

        cruas = self.detector.detect(
            frame, insistir=self.modo_parado or (self._frame_n % 3 == 0))
        self.cruas = cruas
        for l in cruas:
            self._diagnostica(l)

        # IDs lidos mas AUSENTES do mapa PLACAS. Antes isso era descartado
        # em silencio -- o HUD mostrava "placas: -" e dava a impressao de
        # que a camera nao tinha visto nada, quando na verdade tinha lido
        # perfeitamente e o mapa e que estava incompleto/errado. Silencio
        # e o pior comportamento possivel aqui: esconde exatamente o erro
        # de configuracao mais provavel do sistema.
        for l in cruas:
            if l.tipo is None:
                self.desconhecidos[l.id] = self.desconhecidos.get(l.id, 0) + 1
                if l.id not in self._avisados and self.desconhecidos[l.id] >= 3:
                    self._avisados.add(l.id)
                    print(f"  !! ID {l.id} detectado ({self.detector.dict_name}) "
                          f"mas NAO esta no mapa PLACAS do config_urbano.py "
                          f"-- essa placa esta sendo IGNORADA")

        leituras = [l for l in cruas
                    if l.tipo is not None
                    and cfgu.SIGN_DIST_MIN_M <= l.dist <= cfgu.SIGN_DIST_MAX_M
                    and not self._em_cooldown(l.id)]
        self.visivel = leituras

        vistos = {l.id for l in leituras}

        # ---- placas que sumiram neste frame
        for id_ in list(self._votos.keys()):
            if id_ in vistos:
                continue
            confirmada = self._votos[id_] >= cfgu.SIGN_CONFIRMA_FRAMES
            perto = self._ultima_dist.get(id_, 99.0) <= cfgu.SIGN_DIST_ACIONA_M * 2.2
            if confirmada and perto:
                self._sumido[id_] = self._sumido.get(id_, 0) + 1
                if self._sumido[id_] >= cfgu.SIGN_SUMIU_ACIONA_FRAMES:
                    ev = Evento(cfgu.PLACAS[id_], id_, self._ultima_dist.get(id_, 0.0))
                    self.registrar_execucao(id_)
                    return ev
            elif not confirmada:
                # ainda juntando votos e o marcador falhou neste frame. A
                # leitura de longe PISCA (marcador de poucos pixels, borrao,
                # reflexo) -- zerar tudo no primeiro frame perdido exigia N
                # leituras PERFEITAMENTE seguidas e a placa quase nunca
                # confirmava. Perde 1 voto e segue; sem leitura por varios
                # frames, os votos chegam a zero e ela e esquecida.
                self._votos[id_] -= 1
                if self._votos[id_] <= 0:
                    self._votos.pop(id_, None)
                    self._ultima_dist.pop(id_, None)
            else:
                # confirmada mas LONGE: era so uma placa passando ao fundo
                self._votos.pop(id_, None)
                self._ultima_dist.pop(id_, None)

        # ---- placas visiveis: acumula voto e testa distancia
        for l in leituras:
            self._votos[l.id] = self._votos.get(l.id, 0) + 1
            self._ultima_dist[l.id] = l.dist
            self._sumido.pop(l.id, None)

            if (self._votos[l.id] >= cfgu.SIGN_CONFIRMA_FRAMES
                    and l.dist <= self.dist_aciona):
                ev = Evento(l.tipo, l.id, l.dist)
                self.registrar_execucao(l.id)
                return ev

        return None

    def hud(self):
        extra = ""
        if self.desconhecidos:
            ids = ",".join(str(i) for i in sorted(self.desconhecidos))
            extra = f"  [IDs fora do mapa: {ids}]"
        if not self.visivel:
            return "placas: -" + extra
        return "placas: " + " ".join(
            f"{l.tipo}({l.dist:.2f}m,v{self._votos.get(l.id,0)})"
            for l in self.visivel) + extra
