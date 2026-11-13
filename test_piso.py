"""
test_piso.py - descobre o MENOR duty em que o carro AINDA ANDA.

Serve pra deixar o robo o mais lento possivel sem ele zumbir parado.
Liga a tracao (NAO usa camera). Use com o carro NO CHAO, em reta, com
~2 m livres na frente, bateria no nivel que vai usar na prova.

    python3 test_piso.py                # sobe de 0.08 ate 0.30, passo 0.01
    python3 test_piso.py 0.10 0.25      # inicio e fim

Como funciona: a cada degrau o carro PARA (freio), depois parte do zero com
o mesmo tranco de arranque do main_urbano.py e segue no duty do degrau por
alguns segundos. Fique olhando:

    - zumbiu ou parou logo depois do tranco  -> abaixo do piso, deixa subir
    - saiu e CONTINUA andando de forma firme -> ESSE e o piso. Aperte Ctrl+C.

Ao apertar Ctrl+C ele imprime os valores sugeridos pro config_urbano.py.
Ctrl+C a qualquer momento tambem corta o motor.
"""

import sys
import time

import config
from MotorModule import Motor

PASSO = 0.01
SEGUNDOS_POR_DEGRAU = 4.0
PAUSA_FREIO_S = 1.2


def main():
    ini = float(sys.argv[1]) if len(sys.argv) > 1 else 0.08
    fim = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30

    motor = Motor(config.ENA_A, config.IN1_A, config.IN2_A,
                  config.ENA_B, config.IN3_B, config.IN4_B,
                  config.SERVO_PIN)
    print(__doc__.split("Como funciona")[0])
    print("Comecando em 3 s... (Ctrl+C corta tudo)")
    ultimo = None
    interrompido = False
    try:
        time.sleep(3)
        duty = ini
        while duty <= fim + 1e-9:
            ultimo = round(duty, 2)
            motor.brake()                 # para de verdade e rearma o tranco
            time.sleep(PAUSA_FREIO_S)
            print(f"duty {ultimo:.2f}: anda de forma firme?  (Ctrl+C se SIM)")
            t0 = time.time()
            while time.time() - t0 < SEGUNDOS_POR_DEGRAU:
                motor.move(ultimo, 0.0, imediato=True)
                time.sleep(0.03)          # mesma cadencia do loop do main
            duty += PASSO
        print("\nChegou no fim da faixa sem voce interromper.")
    except KeyboardInterrupt:
        interrompido = True
        print("\nInterrompido.")
    finally:
        motor.cleanup()

    if not interrompido:
        print("Nenhum duty dessa faixa fez o carro andar firme: rode de novo "
              "com um fim maior (ex: python3 test_piso.py 0.10 0.40).")
    elif ultimo is not None:
        print(f"\nO carro andava firme em duty {ultimo:.2f}  -> esse e o PISO.")
        print("Cole no config_urbano.py (folga de 0.01 pro cruzeiro, pois a")
        print("bateria cai durante a prova):")
        print(f"  VELOCIDADE_URBANA        = {ultimo + 0.01:.2f}")
        print(f"  VELOCIDADE_MINIMA_URBANO = {ultimo:.2f}")
        print(f"  VELOCIDADE_PERDIDO_URBANO = {ultimo:.2f}")
        print(f"  VELOCIDADE_MANOBRA       = {ultimo:.2f}")
        print(f"  VELOCIDADE_APROXIMACAO   = {ultimo:.2f}")
        print(f"  VELOCIDADE_TUNEL         = {ultimo:.2f}")
        print(f"  VELOCIDADE_PISO_ESTIMADO = {ultimo:.2f}")


if __name__ == '__main__':
    main()
