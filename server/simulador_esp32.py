"""
simulador_esp32.py — Simula al ESP32 enviando ventanas de audio
==================================================================

Útil para probar el backend completo (FFT, detección de picos, WebSocket)
SIN necesitar el hardware físico conectado todavía.

Genera una señal sintética (suma de senoidales conocidas + ruido) con
exactamente el mismo formato JSON que el firmware real del ESP32:

    {
      "fs": 8000,
      "n": 1024,
      "timestamp": <ms>,
      "samples": [2048, 2061, ...]   # enteros 0-4095, como un ADC real
    }

Uso:
    python simulador_esp32.py
    python simulador_esp32.py --freq 440 880      # simula un La + su octava
    python simulador_esp32.py --url http://localhost:8000/audio
"""

import argparse
import time

import numpy as np
import requests

FS_DEFAULT = 8000
N_DEFAULT = 1024


def generar_ventana_simulada(
    frecuencias: list[float],
    amplitudes: list[float],
    fs: int,
    n: int,
    ruido_db: float = 30.0,
) -> list[int]:
    """
    Genera N muestras simulando lo que el ADC del ESP32 entregaría si el
    micrófono captara exactamente esas frecuencias con esas amplitudes.

    El resultado se escala y desplaza para imitar un ADC de 12 bits real:
    silencio ~2048, rango válido [0, 4095].
    """
    t = np.arange(n) / fs

    señal = np.zeros(n)
    for f, a in zip(frecuencias, amplitudes):
        señal += a * np.sin(2 * np.pi * f * t)

    # Ruido blanco de fondo, como lo tendría un micrófono real
    amplitud_ruido = max(amplitudes) * (10 ** (-ruido_db / 20))
    señal += np.random.normal(0, amplitud_ruido, n)

    # Centra en 2048 (punto medio del ADC de 12 bits) y limita al rango válido
    señal_adc = señal + 2048
    señal_adc = np.clip(señal_adc, 0, 4095)

    return señal_adc.astype(int).tolist()


def enviar_ventana(url: str, samples: list[int], fs: int):
    payload = {
        "fs": fs,
        "n": len(samples),
        "timestamp": int(time.time() * 1000),
        "samples": samples,
    }
    try:
        resp = requests.post(url, json=payload, timeout=2)
        print(f"  → POST {resp.status_code} | {resp.json()}")
    except requests.exceptions.RequestException as e:
        print(f"  → Error de conexión: {e}")


def main():
    parser = argparse.ArgumentParser(description="Simulador de ESP32 para pruebas")
    parser.add_argument(
        "--url", default="http://localhost:8000/audio", help="URL del endpoint /audio"
    )
    parser.add_argument(
        "--freq",
        nargs="+",
        type=float,
        default=[440.0, 880.0, 1320.0],
        help="Frecuencias a simular en Hz (ej: --freq 440 880)",
    )
    parser.add_argument(
        "--amp",
        nargs="+",
        type=float,
        default=None,
        help="Amplitudes correspondientes (por defecto: decrecientes 1.0, 0.5, 0.33...)",
    )
    parser.add_argument(
        "--ciclos", type=int, default=20, help="Número de ventanas a enviar"
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=0.128,
        help="Segundos entre envíos (por defecto 128ms, igual que N/fs)",
    )
    args = parser.parse_args()

    amplitudes = args.amp or [1.0 / (i + 1) for i in range(len(args.freq))]

    print(f"Simulando ESP32 → {args.url}")
    print(f"Frecuencias: {args.freq} Hz | Amplitudes: {amplitudes}")
    print(f"fs={FS_DEFAULT} Hz, n={N_DEFAULT} muestras, cada {args.intervalo*1000:.0f} ms\n")

    for i in range(args.ciclos):
        samples = generar_ventana_simulada(
            args.freq, amplitudes, FS_DEFAULT, N_DEFAULT
        )
        print(f"[{i+1}/{args.ciclos}] Enviando ventana...")
        enviar_ventana(args.url, samples, FS_DEFAULT)
        time.sleep(args.intervalo)


if __name__ == "__main__":
    main()
