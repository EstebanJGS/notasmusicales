"""
fourier.py — Procesamiento matemático de la señal de audio
============================================================

Aquí vive la conexión directa con la teoría de Series/Transformada de Fourier
que se trabajó antes de escribir código:

  1. Centrado de la señal       → elimina el componente DC (ADC va de 0 a 4095,
                                   no de -2048 a 2047, así que hay que restar la
                                   media antes de transformar)
  2. Ventana de Hanning         → mitiga el "spectral leakage" que aparece al
                                   truncar la señal a N muestras (Ejemplo 3.25:
                                   un pulso rectangular en el tiempo equivale a
                                   convolucionar con un sinc en frecuencia)
  3. FFT (Cooley-Tukey)         → calcula la DFT en O(N log N) en vez de O(N²)
  4. Magnitud y fase            → |X[k]| y arg(X[k]) para cada frecuencia
  5. Detección de picos         → identifica las frecuencias dominantes
  6. Mapeo a nota musical       → convierte Hz a la nota más cercana (A4=440Hz)
"""

import numpy as np

# ──────────────────────────────────────────────────────────────────────────
# Constantes musicales
# ──────────────────────────────────────────────────────────────────────────
NOTAS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
A4_FREQ = 440.0   # frecuencia de referencia: La4
A4_MIDI = 69      # número MIDI de La4


def frecuencia_a_nota(freq: float) -> dict:
    """
    Convierte una frecuencia en Hz a la nota musical más cercana,
    usando la escala temperada de 12 semitonos.

    La relación matemática es:
        n = 12 * log2(f / 440)
    donde n es el número de semitonos de distancia respecto a A4 (440 Hz).
    Cada semitono multiplica la frecuencia por 2^(1/12).
    """
    if freq <= 0:
        return {"nota": None, "octava": None, "cents_desviacion": None}

    semitonos_desde_a4 = 12 * np.log2(freq / A4_FREQ)
    semitono_redondeado = round(semitonos_desde_a4)

    # Desviación en "cents" (centésimas de semitono) — útil para saber
    # qué tan afinada está la nota detectada.
    cents = (semitonos_desde_a4 - semitono_redondeado) * 100

    midi_num = A4_MIDI + semitono_redondeado
    indice_nota = midi_num % 12
    octava = midi_num // 12 - 1

    return {
        "nota": NOTAS[indice_nota],
        "octava": int(octava),
        "cents_desviacion": round(float(cents), 1),
    }


# ──────────────────────────────────────────────────────────────────────────
# Procesamiento principal
# ──────────────────────────────────────────────────────────────────────────
def procesar_ventana(samples: list[int], fs: int, timestamp: int) -> dict:
    """
    Aplica la cadena completa: centrado -> ventaneo -> FFT -> espectro -> picos.

    Parameters
    ----------
    samples : valores crudos del ADC (0-4095), en el dominio del tiempo
    fs      : frecuencia de muestreo en Hz
    timestamp : marca de tiempo recibida del ESP32 (se reenvía sin cambios)

    Returns
    -------
    dict listo para enviar al frontend por WebSocket
    """
    x = np.asarray(samples, dtype=np.float64)
    n = len(x)

    # ── 1. Centrado: quitar el componente DC ──────────────────────────────
    # El ADC entrega [0, 4095], con silencio cerca de ~2048. Sin este paso
    # aparecería un pico gigante en 0 Hz que no representa nada del sonido.
    x_centrada = x - np.mean(x)

    # Amplitud pico-a-pico cruda, útil para que el frontend muestre un
    # medidor de "qué tan fuerte está sonando" sin necesidad de la FFT.
    amplitud_pp = float(np.max(x) - np.min(x))

    # ── 2. Ventana de Hanning ──────────────────────────────────────────────
    # Suaviza los bordes de la ventana truncada para reducir spectral leakage
    # (ver Ejemplo 3.25 — pulso rectangular y la función sinc).
    ventana = np.hanning(n)
    x_ventaneada = x_centrada * ventana

    # ── 3. FFT ──────────────────────────────────────────────────────────────
    X = np.fft.fft(x_ventaneada)
    frecuencias = np.fft.fftfreq(n, d=1 / fs)

    # ── 4. Magnitud y fase — solo la mitad positiva (Nyquist) ───────────────
    # Para una señal real, el espectro es simétrico: X[k] y X[N-k] son
    # complejos conjugados. La información completa está en la primera mitad.
    mitad = n // 2
    freqs_pos = frecuencias[:mitad]
    magnitudes = np.abs(X[:mitad]) / (n / 2)   # normalizado → amplitudes reales
    fases = np.angle(X[:mitad])

    # magnitudes[0] (componente DC) debería ser ~0 tras el centrado; lo forzamos
    # a 0 explícitamente para que no compita como "pico" por ruido numérico.
    magnitudes[0] = 0.0

    # ── 5. Detección de picos ────────────────────────────────────────────────
    picos = _detectar_picos(freqs_pos, magnitudes, fases)

    return {
        "timestamp": timestamp,
        "fs": fs,
        "n": n,
        "amplitud_pp": amplitud_pp,
        # Muestras centradas (sin la ventana de Hanning) para que el frontend
        # pueda dibujar la forma de onda real en el dominio del tiempo.
        "muestras": x_centrada.round(1).tolist(),
        "espectro": {
            # Se truncan a un número razonable de puntos para no saturar
            # el WebSocket — el frontend solo necesita ver la forma del
            # espectro, no cada bin individual.
            "frecuencias": freqs_pos[: mitad].round(1).tolist(),
            "magnitudes": magnitudes[: mitad].round(2).tolist(),
        },
        "picos": picos,
        "nota_dominante": picos[0]["nota"] if picos else None,
    }


def _detectar_picos(
    freqs: np.ndarray,
    magnitudes: np.ndarray,
    fases: np.ndarray,
    umbral_relativo: float = 0.15,
    max_picos: int = 5,
) -> list[dict]:
    """
    Encuentra los picos locales del espectro de magnitud.

    Un punto k es "pico" si es mayor que sus dos vecinos inmediatos y supera
    un umbral relativo al pico más grande del espectro (para ignorar ruido
    numérico de bajo nivel).
    """
    if len(magnitudes) < 3 or np.max(magnitudes) == 0:
        return []

    umbral = np.max(magnitudes) * umbral_relativo

    candidatos = []
    for k in range(1, len(magnitudes) - 1):
        if (
            magnitudes[k] > umbral
            and magnitudes[k] > magnitudes[k - 1]
            and magnitudes[k] > magnitudes[k + 1]
        ):
            candidatos.append(k)

    # Ordena los candidatos por magnitud descendente y toma los más fuertes
    candidatos.sort(key=lambda k: magnitudes[k], reverse=True)
    candidatos = candidatos[:max_picos]
    # Reordena por frecuencia ascendente para que el frontend los muestre
    # de forma natural (de grave a agudo)
    candidatos.sort()

    picos = []
    for k in candidatos:
        freq = float(freqs[k])
        info_nota = frecuencia_a_nota(freq)
        picos.append(
            {
                "frecuencia_hz": round(freq, 1),
                "magnitud": round(float(magnitudes[k]), 2),
                "fase_rad": round(float(fases[k]), 3),
                **info_nota,
            }
        )

    # El primer elemento de la lista que regresamos debe ser el pico más
    # fuerte (la "fundamental" percibida), no necesariamente el de menor
    # frecuencia — se reordena una vez más solo para el campo de retorno.
    picos.sort(key=lambda p: p["magnitud"], reverse=True)
    return picos