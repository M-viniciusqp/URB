"""
test_re.py - testa a RE EM LINHA RETA, sem camera. Carro NO CHAO, com ~1 m
livre ATRAS.

    python3 test_re.py                  # usa RE_TURN / RE_BALANCO_B do config
    python3 test_re.py -0.10            # RE_TURN = -0.10
    python3 test_re.py -0.10 1.05 1.5   # RE_TURN, RE_BALANCO_B, segundos

Olhe pra onde a TRASEIRA vai (na re ela vai pro lado do volante):
  traseira desviou pra DIREITA  -> RE_TURN mais NEGATIVO
  traseira desviou pra ESQUERDA -> RE_TURN mais POSITIVO
Se mesmo assim torcer, teste o BALANCO_B (1.05, 0.95...): uma roda mais forte
que a outra gira o carro.
Quando voltar reto, cole os valores no config_urbano.py.
"""
import sys
import time

import config
import config_urbano as cfgu
from MotorModule import Motor


def main():
    a = sys.argv[1:]
    turn = float(a[0]) if len(a) > 0 else cfgu.RE_TURN
    bal = float(a[1]) if len(a) > 1 else cfgu.RE_BALANCO_B
    seg = float(a[2]) if len(a) > 2 else 1.5
    cfgu.RE_BALANCO_B = bal
    m = Motor(config.ENA_A, config.IN1_A, config.IN2_A,
              config.ENA_B, config.IN3_B, config.IN4_B, config.SERVO_PIN)
    print(f"RE: turn={turn:+.2f} balanco_B={bal:.2f} por {seg:.1f}s -- comecando em 3 s (Ctrl+C corta)")
    try:
        time.sleep(3)
        t0 = time.time()
        while time.time() - t0 < seg:
            m.move(-cfgu.VELOCIDADE_RE, turn, imediato=True)
            time.sleep(0.03)
        m.brake()
        time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        m.cleanup()
    print("Pronto. Pra onde a traseira foi? Ajuste e rode de novo.")


if __name__ == "__main__":
    main()
