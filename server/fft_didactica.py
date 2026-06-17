"""
Versión DIDÁCTICA de la Transformada de Fourier, implementada A MANO con ciclos.

Objetivo: mostrar paso a paso CÓMO funciona la FFT, sin usar `numpy.fft`, para
poder explicar el algoritmo (no tratarlo como caja negra).

Contiene:
  - dft_directa()        : la DEFINICIÓN de la DFT con dos ciclos anidados. O(N^2).
                           Lenta, pero es la fórmula tal cual.
  - fft_iterativa()      : la Transformada RÁPIDA de Fourier (Cooley-Tukey radix-2),
                           iterativa e in-place, escrita con ciclos. O(N log N).
  - detect_pitch_manual(): detecta la nota usando fft_iterativa en vez de numpy.fft.

La versión original (fourier.py) usa numpy.fft y queda intacta. Ejecuta este
archivo directamente para ver la demostración:  python fft_didactica.py
"""

import math
import cmath

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


# ── 1) DFT por definición (lenta, solo para explicar la fórmula) ─────────────────

def dft_directa(x):
    """DFT por definición:  X[k] = Σ_n  x[n] · e^(-2πi·k·n/N).

    Dos ciclos anidados  ->  O(N^2). Para N=2048 son ~4 millones de operaciones:
    es la versión "lenta" que justifica por qué existe la FFT.
    """
    N = len(x)
    X = [0j] * N
    for k in range(N):                       # ciclo sobre las frecuencias
        suma = 0j
        for n in range(N):                   # ciclo sobre las muestras
            suma += x[n] * cmath.exp(-2j * math.pi * k * n / N)
        X[k] = suma
    return X


# ── 2) FFT rápida (Cooley-Tukey radix-2, iterativa, con ciclos) ──────────────────

def _bit_reversal(x):
    """Reordena el arreglo por inversión de bits (paso previo de la FFT iterativa).

    Ej. con N=8: el índice 1 (001) va a la posición 4 (100), el 3 (011) al 6 (110)...
    """
    N = len(x)
    a = list(x)
    j = 0
    for i in range(1, N):
        bit = N >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    return a


def fft_iterativa(x):
    """Transformada Rápida de Fourier (Cooley-Tukey radix-2, iterativa, in-place).

    Requiere len(x) potencia de 2 (aquí BUFFER_SIZE = 2048 lo es).

    Idea: en lugar de O(N^2), combina "mariposas" (butterflies) en log2(N) etapas,
    reutilizando resultados. Esto baja el costo a O(N log N) -> por eso es "rápida".

    Estructura de los ciclos:
        - ciclo de ETAPAS      : longitud = 2, 4, 8, ..., N   (log2 N pasadas)
        - ciclo de BLOQUES     : recorre el arreglo en trozos de 'longitud'
        - ciclo de MARIPOSAS   : combina pares dentro de cada bloque
    """
    N = len(x)
    if N == 0 or (N & (N - 1)) != 0:
        raise ValueError("La FFT radix-2 requiere longitud potencia de 2 (>0)")

    a = [complex(v) for v in _bit_reversal(x)]

    longitud = 2
    while longitud <= N:                              # --- ciclo de etapas ---
        w_long = cmath.exp(-2j * math.pi / longitud)  # factor twiddle de la etapa
        mitad = longitud // 2
        for inicio in range(0, N, longitud):          # --- ciclo de bloques ---
            w = 1 + 0j
            for k in range(mitad):                    # --- ciclo de mariposas ---
                par   = a[inicio + k]
                impar = a[inicio + k + mitad] * w
                a[inicio + k]         = par + impar
                a[inicio + k + mitad] = par - impar
                w *= w_long
        longitud <<= 1                                # siguiente etapa: el doble
    return a


# ── 3) Detección de nota usando la FFT manual ───────────────────────────────────

def _hanning(N):
    """Ventana de Hanning calculada a mano (sin numpy)."""
    if N <= 1:
        return [1.0] * N
    return [0.5 - 0.5 * math.cos(2 * math.pi * n / (N - 1)) for n in range(N)]


def detect_pitch_manual(samples, sample_rate):
    """Equivalente a fourier.detect_pitch pero usando fft_iterativa (sin numpy)."""
    N = len(samples)
    if N < 2:
        return 0.0

    media = sum(samples) / N
    win = _hanning(N)
    x = [(s - media) * win[n] for n, s in enumerate(samples)]   # quita DC + ventana

    espectro = fft_iterativa(x)                  # <-- AQUÍ nuestra FFT con ciclos

    mitad = N // 2                               # señal real -> espectro simétrico
    mags = [abs(espectro[k]) for k in range(mitad)]
    resolucion = sample_rate / N                 # Hz por bin

    min_idx = max(1, int(20 / resolucion))       # ignora ruido < 20 Hz
    if min_idx >= mitad - 1:
        return 0.0

    pico = min_idx
    for k in range(min_idx, mitad):              # ciclo para hallar el máximo
        if mags[k] > mags[pico]:
            pico = k

    # Interpolación parabólica para precisión sub-bin (igual que la versión numpy)
    if 0 < pico < mitad - 1:
        a_, b_, g_ = mags[pico - 1], mags[pico], mags[pico + 1]
        denom = a_ - 2 * b_ + g_
        p = 0.5 * (a_ - g_) / denom if denom != 0 else 0.0
        return (pico + p) * resolucion
    return pico * resolucion


def freq_to_note(freq, a4=440.0):
    """Frecuencia -> nota (misma fórmula que fourier.py, aquí sin numpy)."""
    if freq <= 20:
        return None, 0.0
    semitonos = 12 * math.log2(freq / a4)
    n = round(semitonos)
    nota = NOTE_NAMES[(n + 9) % 12]
    octava = 4 + (n + 9) // 12
    cents = (semitonos - n) * 100
    return f"{nota}{octava}", cents


# ── 4) Demostración para exponer ────────────────────────────────────────────────

if __name__ == '__main__':
    import time

    SAMPLE_RATE = 8000
    N = 2048
    F_REAL = 440.0          # La4 (A4)

    # Señal sintética: senoide a 440 Hz + un armónico + un poco de zumbido a 50 Hz
    señal = [
        1000 * math.sin(2 * math.pi * F_REAL * (n / SAMPLE_RATE))
        + 300 * math.sin(2 * math.pi * 2 * F_REAL * (n / SAMPLE_RATE))
        + 50 * math.sin(2 * math.pi * 50 * (n / SAMPLE_RATE))
        for n in range(N)
    ]

    print("=== 1) ¿La FFT rápida da lo mismo que la DFT por definición? (N=8) ===")
    chico = [0.0, 1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0]
    rapida = fft_iterativa(chico)
    lenta = dft_directa(chico)
    error = max(abs(rapida[k] - lenta[k]) for k in range(8))
    print(f"  error máximo entre fft_iterativa y dft_directa = {error:.2e}"
          f"  ->  {'IGUALES [OK]' if error < 1e-9 else 'DIFIEREN [X]'}\n")

    print("=== 2) Detección de la nota (señal de prueba a 440 Hz) ===")
    f = detect_pitch_manual(señal, SAMPLE_RATE)
    nota, cents = freq_to_note(f)
    print(f"  FFT manual -> {f:7.2f} Hz  ->  {nota} ({cents:+.1f} cents)")
    try:
        from fourier import detect_pitch as detect_pitch_numpy
        f2 = detect_pitch_numpy(señal, SAMPLE_RATE)
        print(f"  numpy.fft  -> {f2:7.2f} Hz   (para comparar)")
    except ImportError:
        print("  (numpy no instalado: se omite la comparación con fourier.py)")

    print("\n=== 3) Por qué se llama 'rápida' (tiempos sobre N=2048) ===")
    t0 = time.perf_counter(); dft_directa(señal);   t_dft = time.perf_counter() - t0
    t0 = time.perf_counter(); fft_iterativa(señal); t_fft = time.perf_counter() - t0
    print(f"  DFT directa   O(N^2)    : {t_dft * 1000:9.1f} ms")
    print(f"  FFT iterativa O(N logN) : {t_fft * 1000:9.1f} ms"
          f"   ->  ~{t_dft / t_fft:.0f}x más rápida")
