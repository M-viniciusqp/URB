import time
import RPi.GPIO as GPIO
from time import sleep

import config

try:
    import config_urbano as cfgu
except ImportError:      # rodando o main.py da corrida, sem o urbano
    cfgu = None

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


class Motor:
    """Tracao traseira (ponte H dupla) + direcao por servo."""

    def __init__(self, EnaA, In1A, In2A, EnaB, In1B, In2B, servoPin):
        self.EnaA, self.In1A, self.In2A = EnaA, In1A, In2A
        self.EnaB, self.In1B, self.In2B = EnaB, In1B, In2B

        for pin in (EnaA, In1A, In2A, EnaB, In1B, In2B, servoPin):
            GPIO.setup(pin, GPIO.OUT)

        self.pwmA = GPIO.PWM(self.EnaA, 100)
        self.pwmB = GPIO.PWM(self.EnaB, 100)
        self.pwmA.start(0)
        self.pwmB.start(0)

        self.servoPin = servoPin
        self.pwmServo = GPIO.PWM(self.servoPin, 50)
        self.pwmServo.start(0)

        self._last_angle = None
        self._turn_atual = 0.0             # esterco efetivamente aplicado
        self._t_turn = time.time()
        self._parado_desde = time.time()   # pro tranco de arranque
        self._andando = False
        self.set_servo_angle(config.SERVO_CENTRO)

    # ---------------- SERVO ----------------
    def set_servo_angle(self, angle):
        angle = max(config.SERVO_MAX_ESQ, min(config.SERVO_MAX_DIR, angle))
        # so reescreve o duty se mudou de verdade -> mata o tremor do servo
        if self._last_angle is not None and \
           abs(angle - self._last_angle) < config.SERVO_DEADBAND_DEG:
            return
        self._last_angle = angle
        duty = (angle / 18.0) + 2.5
        self.pwmServo.ChangeDutyCycle(duty)

    def turn_to(self, turn, imediato=False):
        """turn em -1 (esquerda total) .. +1 (direita total).

        LIMITADOR DE TAXA (slew rate): o comando nao salta, ele caminha
        ate o alvo a no maximo TURN_SLEW_POR_S por segundo.

        Por que isso mata a oscilacao do servo: o PID pode pedir -0.24 num
        frame e +0.25 no seguinte por causa de ruido de leitura. Sem
        limite, o servo persegue esse zigue-zague em cheio e o carro
        serpenteia -- e pior, a propria trepidacao muda o que a camera ve,
        realimentando o ciclo. Com o limite, ruido de alta frequencia e
        fisicamente filtrado antes de virar movimento, sem adicionar
        atraso ao comando LENTO (a curva de verdade passa inteira).

        imediato=True pula o limitador -- usado nas manobras em malha
        aberta, onde o esterco no talo e intencional e nao pode ser
        rampado (comeria o tempo de curva calibrado).
        """
        turn = max(-1.0, min(1.0, turn))

        agora = time.time()
        dt = agora - self._t_turn
        self._t_turn = agora
        if imediato or cfgu is None or cfgu.TURN_SLEW_POR_S <= 0:
            self._turn_atual = turn
        else:
            if dt <= 0 or dt > 0.5:
                dt = 1 / 30.0
            passo = cfgu.TURN_SLEW_POR_S * dt
            delta = turn - self._turn_atual
            self._turn_atual += max(-passo, min(passo, delta))
        turn = self._turn_atual
        if turn < 0:
            amplitude = config.SERVO_CENTRO - config.SERVO_MAX_ESQ
        else:
            amplitude = config.SERVO_MAX_DIR - config.SERVO_CENTRO
        self.set_servo_angle(config.SERVO_CENTRO + turn * amplitude)

    # ---------------- TRACAO ----------------
    def _duty_marcha_lenta(self, speed):
        """Converte uma velocidade ABAIXO do piso do motor num duty pulsado.

        Devolve o duty a aplicar NESTE instante (piso ou zero). A media no
        tempo equivale a 'speed', mas cada pulso individual tem torque de
        sobra pra vencer o atrito -- que e o ponto todo.
        """
        if cfgu is None or not cfgu.PULSO_ATIVO:
            return speed
        alvo = abs(speed)
        if alvo <= 0.0 or alvo >= cfgu.PULSO_PISO:
            return speed          # acima do piso: PWM normal, sem pulso

        frac = max(cfgu.PULSO_MIN_FRAC, alvo / cfgu.PULSO_PISO)
        fase = (time.time() % cfgu.PULSO_PERIODO_S) / cfgu.PULSO_PERIODO_S
        ligado = fase < frac
        duty = cfgu.PULSO_PISO if ligado else 0.0
        return duty if speed >= 0 else -duty

    def _tranco_arranque(self, speed):
        """Atrito ESTATICO e maior que o dinamico: sair do zero custa mais
        torque do que seguir andando. Sem um tranco curto, o carro fica
        zumbindo parado ao retomar depois da parada obrigatoria."""
        if cfgu is None or not cfgu.ARRANQUE_ATIVO:
            return speed
        agora = time.time()
        if abs(speed) < 0.01:
            self._andando = False
            self._parado_desde = agora
            return speed
        if not self._andando:
            self._andando = True
            self._parado_desde = agora
        if agora - self._parado_desde < cfgu.ARRANQUE_TEMPO_S:
            alvo = max(abs(speed), cfgu.ARRANQUE_DUTY)
            return alvo if speed >= 0 else -alvo
        return speed

    def drive(self, speed):
        """speed em -1 .. +1."""
        speed = self._tranco_arranque(speed)
        speed = self._duty_marcha_lenta(speed)
        speed = max(-1.0, min(1.0, speed)) * 100
        forward = speed >= 0
        GPIO.output(self.In1A, GPIO.HIGH if forward else GPIO.LOW)
        GPIO.output(self.In2A, GPIO.LOW if forward else GPIO.HIGH)
        GPIO.output(self.In1B, GPIO.HIGH if forward else GPIO.LOW)
        GPIO.output(self.In2B, GPIO.LOW if forward else GPIO.HIGH)
        self.pwmA.ChangeDutyCycle(abs(speed))
        self.pwmB.ChangeDutyCycle(abs(speed))

    def _marcar_parado(self):
        self._andando = False
        self._parado_desde = time.time()

    def brake(self):
        """FREIO ATIVO (curto-circuito do motor pela ponte H).

        Diferente de stop(): stop() corta o PWM e o carro segue rolando
        por inercia ate parar sozinho -- num piso liso isso e facilmente
        10-15cm. Com IN1=IN2=LOW e ENA em 100%, a L298 curto-circuita os
        terminais do motor, e ele vira um gerador freando a si mesmo.
        A parada e MUITO mais curta e, principalmente, REPETIVEL.

        Nao mexe no servo -- a direcao fica onde estava.
        """
        GPIO.output(self.In1A, GPIO.LOW)
        GPIO.output(self.In2A, GPIO.LOW)
        GPIO.output(self.In1B, GPIO.LOW)
        GPIO.output(self.In2B, GPIO.LOW)
        self.pwmA.ChangeDutyCycle(100)
        self.pwmB.ChangeDutyCycle(100)
        self._marcar_parado()

    def move(self, speed=0.5, turn=0.0, t=0, imediato=False):
        self.turn_to(turn, imediato=imediato)
        self.drive(speed)
        if t:
            sleep(t)

    def stop(self, t=0):
        self.pwmA.ChangeDutyCycle(0)
        self.pwmB.ChangeDutyCycle(0)
        self.set_servo_angle(config.SERVO_CENTRO)
        if t:
            sleep(t)

    def cleanup(self):
        self.stop()
        sleep(0.2)
        self.pwmA.stop(); self.pwmB.stop(); self.pwmServo.stop()
        GPIO.cleanup()
