"""
main_urbano.py - piloto autonomo em PISTA URBANA (obedece sinalizacao).

    python3 main_urbano.py            # sem janela (mais FPS)
    python3 main_urbano.py --debug    # com janelas de visao + placas

Diferenca pro main.py (corrida):
  - captura em resolucao maior, so pra conseguir ler o ArUco de longe;
  - a visao de faixa continua recebendo 480x240 (a calibracao dela e em
    pixels e nao pode mudar de resolucao sem reajustar tudo);
  - existe uma camada de decisao (navigator) que pode TOMAR o controle do
    PID durante cruzamentos e paradas;
  - perfil de velocidade urbano, aplicado sobre o config.py em runtime.

O main.py da corrida NAO foi alterado e continua funcionando como estava.
"""

import os
import sys
import time

import cv2

import config
import config_urbano as cfgu
from vision import LaneVision
from controller import SteeringPID, speed_for
from MotorModule import Motor
from signs import SignTracker
from crosswalk import CrosswalkDetector
from navigator import Navigator, APROXIMANDO, PARANDO, RECUANDO, PARADO

DEBUG = "--debug" in sys.argv

# sem display (SSH sem -X), cv2.imshow derruba o programa. O --debug
# continua valendo pra telemetria, so nao abre janela.
GUI = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
if DEBUG and not GUI:
    print("[--debug sem display] telemetria ligada, janelas desativadas.")


def abrir_camera(indice, res, nome):
    cap = cv2.VideoCapture(indice, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"AVISO: camera de {nome} (index {indice}) nao abriu.")
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera {nome} (index {indice}): {w}x{h} formato={fourcc_str}")
    if fourcc_str.strip() != "MJPG":
        print(f"  AVISO: {nome} nao aceitou MJPG -- o FPS vai sofrer.")
    if (w, h) != tuple(res):
        print(f"  AVISO: {nome} entregou {w}x{h} em vez de {tuple(res)}.")
        if nome == "placas":
            print("  Recalibre FOCAL_PX nessa resolucao, senao a distancia "
                  "das placas sai errada.")
    return cap


def main():
    cfgu.aplicar_overrides()
    print("PILOTO URBANO -- seguindo faixa e obedecendo sinalizacao.\n")

    cap = abrir_camera(cfgu.CAMERA_FAIXA_INDEX, cfgu.CAMERA_RES_FAIXA, "faixa")
    if cap is None:
        print("Erro critico: camera de faixa nao abriu.")
        return

    # Camera DEDICADA as placas. Se nao existir/nao abrir, o sistema cai
    # sozinho pra camera unica (le placa no mesmo frame da faixa) -- pior,
    # mas funcional. Melhor degradar do que nao rodar na hora da prova.
    cap_placas = abrir_camera(cfgu.CAMERA_PLACAS_INDEX,
                              cfgu.CAMERA_RES_PLACAS, "placas")
    DUAS_CAMERAS = cap_placas is not None
    if not DUAS_CAMERAS:
        print("  -> rodando com UMA camera (placas lidas no frame da faixa).")

    vision = LaneVision()
    pid = SteeringPID()
    # Com duas cameras o main JA salteia a leitura (SIGN_SKIP_FRAMES). Se o
    # tracker salteasse de novo, a deteccao rodaria a cada 3x3=9 frames e as
    # 3 confirmacoes levariam ~27 frames de placa visivel. Com camera unica
    # o main chama update() todo frame, entao ai o tracker que salteia.
    placas = SignTracker(pular_frames=1 if DUAS_CAMERAS else None)
    zebra_det = CrosswalkDetector()
    nav = Navigator()
    motor = Motor(config.ENA_A, config.IN1_A, config.IN2_A,
                  config.ENA_B, config.IN3_B, config.IN4_B,
                  config.SERVO_PIN)

    frames, t_fps = 0, time.time()
    frame_n = 0
    ultimo_frame_placas = None
    turn = 0.0
    fps_medido = 30.0
    frame_anterior_confiavel = True
    t_cam = t_vis = t_sign = 0.0

    try:
        while True:
            t0 = time.time()
            ok, frame_full = cap.read()
            t1 = time.time()
            if not ok:
                motor.stop()
                continue

            # parado na zebra a placa arma de mais longe (ver config_urbano)
            placas.dist_aciona = (cfgu.SIGN_DIST_ACIONA_PARADO_M
                                  if nav.estado in (APROXIMANDO, PARANDO, RECUANDO, PARADO)
                                  else cfgu.SIGN_DIST_ACIONA_M)

            # ---------- 1. PLACAS (camera dedicada) -------------------
            # A leitura da camera de placas e SALTEADA (SIGN_SKIP_FRAMES):
            # cada cap.read() custa ~20ms e travaria o loop da faixa, que
            # e o que mantem o carro na pista. Placa nao precisa de 30 FPS
            # -- ela fica parada esperando o carro chegar.
            if DUAS_CAMERAS:
                if frame_n % cfgu.SIGN_SKIP_FRAMES == 0:
                    ok_p, frame_placas = cap_placas.read()
                    if ok_p:
                        evento = placas.update(frame_placas)
                        nav.on_evento(evento)
                        ultimo_frame_placas = frame_placas
            else:
                evento = placas.update(frame_full)
                nav.on_evento(evento)
            frame_n += 1
            t2 = time.time()

            # ---------- 2. FAIXA --------------------------------------
            frame = cv2.resize(frame_full, config.CAMERA_RES)
            res = vision.process(frame, debug=DEBUG)
            t3 = time.time()

            # ---------- 3. FAIXA DE PEDESTRE --------------------------
            # reaproveita a mascara que a visao ja calculou. Se o vision.py
            # nao expuser 'last_mask', recalcula (custa ~5ms a mais).
            mask = getattr(vision, "last_mask", None)
            if mask is None:
                y0 = int(vision.H * config.SCAN_TOP_PCT)
                mask = vision.threshold(frame[y0:, :])
            zebra = zebra_det.detect(mask)
            t4 = time.time()

            leitura_ok = bool(res.valid and res.motivo == "ok"
                              and (res.found_left or res.found_right))
            # Em cima da zebra a leitura de faixa NAO vale, mesmo que o
            # vision.py diga que esta ok: as barras brancas atravessadas
            # sao lidas como borda de faixa e o alvo pula.
            if zebra.presente:
                leitura_ok = False

            # ---------- 4. DECISAO ------------------------------------
            cmd = nav.update(leitura_ok, zebra)

            if cmd.resetar_pid:
                # depois de uma manobra em malha aberta, o estado interno do
                # PID (integral, erro anterior) descreve uma pista que nao
                # existe mais. Reaproveitar isso e garantir um esterco errado
                # no primeiro frame da rua nova.
                pid.reset()
                vision.ref_e = vision.ref_d = None   # forca reengate do rastreio
                zebra_det.reset()
                frame_anterior_confiavel = False

            if cmd.fim:
                motor.stop()
                print("\nDestino alcancado. Encerrando.")
                break

            # ---------- 5. COMANDO ------------------------------------
            if not cmd.usa_faixa:
                # manobra cronometrada: o navigator manda, a visao nao opina
                turn = cmd.turn
                speed = cmd.speed
                frame_anterior_confiavel = False
            elif leitura_ok:
                if not frame_anterior_confiavel:
                    pid.marcar_retomada()
                frame_anterior_confiavel = True
                turn = pid.update(res.error, res.heading)
                speed = speed_for(turn, res.curvature)
                if cfgu.FPS_FREIO_URBANO and fps_medido < config.FPS_MINIMO_SEGURO:
                    speed *= max(0.35, fps_medido / config.FPS_MINIMO_SEGURO)
            elif cmd.tolera_perdido or vision.lost_frames <= config.MAX_FRAMES_PERDIDO:
                frame_anterior_confiavel = False
                turn *= 0.85
                speed = config.VELOCIDADE_PERDIDO
            else:
                turn, speed = 0.0, 0.0
                pid.reset()

            # teto global (tunel, perfil urbano) -- vale pra TODO caminho
            speed = min(speed, nav.teto_velocidade())

            # imediato=True nas manobras: ali o esterco no talo e
            # intencional e nao pode ser rampado (comeria o tempo de curva)
            if cmd.frear:
                # parada obrigatoria: freio ATIVO (curto na ponte H), nao
                # so PWM=0 -- o navigator pedia (cmd.frear) mas o main nunca
                # chamava, e o carro seguia rolando por inercia.
                motor.turn_to(0.0, imediato=True)
                motor.brake()
            else:
                motor.move(speed, turn, imediato=not cmd.usa_faixa)

            t_cam += (t1 - t0); t_sign += (t2 - t1); t_vis += (t4 - t2)

            # ---------- 6. TELEMETRIA ---------------------------------
            frames += 1
            if time.time() - t_fps >= 2.0:
                fps_medido = frames / (time.time() - t_fps)
                if zebra.presente:
                    st = "ZEBRA"          # leitura suprimida DE PROPOSITO
                elif leitura_ok:
                    st = "OK"
                elif res.valid:
                    st = f"DEGRADADO({res.motivo})"
                else:
                    st = f"PERDIDO({res.motivo})"
                z = f" ZEBRA({zebra.linhas})" if zebra.presente else ""
                if (res.lado_continuo and
                        res.lado_continuo != cfgu.LADO_CONTINUO_ESPERADO):
                    z += "  !! CONTINUA NA " + res.lado_continuo.upper() + \
                         " -> possivel CONTRAMAO"
                print(f"FPS {fps_medido:.1f} | {nav.hud()}{z} | erro {res.error:+.2f} "
                      f"| turn {turn:+.2f} | v {speed:.2f} | {st}")
                print(f"  {placas.hud()}")
                print(f"  custo -> cam {1000*t_cam/frames:.0f}ms  "
                      f"placas {1000*t_sign/frames:.0f}ms  faixa {1000*t_vis/frames:.0f}ms")
                frames, t_fps = 0, time.time()
                t_cam = t_vis = t_sign = 0.0

            if DEBUG and GUI:
                # ---- janela da MASCARA (onde a zebra e detectada) ----
                # Sem ver a mascara nao da pra saber se um ZEBRA(n) e faixa
                # de pedestre de verdade ou lixo repetido no piso -- e essa
                # e a diferenca entre o carro parar no lugar certo ou parar
                # no meio da rua.
                vis_mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                if zebra.presente:
                    vis_mask[:, :, 0] = 0          # tinge de amarelo quando detecta
                    if zebra.y_mais_proximo is not None:
                        cv2.line(vis_mask, (0, zebra.y_mais_proximo),
                                 (vis_mask.shape[1], zebra.y_mais_proximo),
                                 (0, 0, 255), 2)
                # linha do gatilho de parada: quando a barra vermelha da
                # zebra cruzar ESTA linha, o carro freia
                y_gat = int(mask.shape[0] * cfgu.ZEBRA_PARADA_FRAC)
                cv2.line(vis_mask, (0, y_gat), (vis_mask.shape[1], y_gat),
                         (0, 255, 0), 1)
                cv2.putText(vis_mask,
                            f"zebra={zebra.linhas} frac={zebra.frac_proximidade:.2f}"
                            f" gatilho={cfgu.ZEBRA_PARADA_FRAC:.2f}",
                            (6, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                            (0, 255, 255), 1)
                cv2.imshow("Mascara (zebra)", vis_mask)

                base_placas = (ultimo_frame_placas if DUAS_CAMERAS
                               and ultimo_frame_placas is not None else frame_full)
                vis_placas = placas.detector.desenhar(base_placas.copy())
                cv2.putText(vis_placas, nav.hud() + (" ZEBRA" if zebra.presente else ""), (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.imshow("Placas", vis_placas)
                if res.debug_view is not None:
                    cv2.imshow("Faixa", res.debug_view)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    except KeyboardInterrupt:
        print("\nParada de emergencia.")
    finally:
        motor.cleanup()
        cap.release()
        if cap_placas is not None:
            cap_placas.release()
        cv2.destroyAllWindows()
        print("\n--- placas obedecidas nesta execucao ---")
        print(nav.resumo())
        print("\nDesligado com seguranca.")


if __name__ == '__main__':
    main()
