import numpy as np

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def detect_pitch(samples, sample_rate):
    samples = np.array(samples, dtype=float)
    samples -= np.mean(samples)             # quita offset DC
    samples *= np.hanning(len(samples))     # ventana, reduce leakage

    fft_vals = np.fft.rfft(samples)
    mags = np.abs(fft_vals)
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)

    min_idx = np.searchsorted(freqs, 20)    # ignora ruido < 20 Hz
    if min_idx >= len(mags) - 1:
        return 0.0
    peak_idx = min_idx + np.argmax(mags[min_idx:])

    # Interpolación parabólica para precisión sub-bin
    if 0 < peak_idx < len(mags) - 1:
        a, b, g = mags[peak_idx - 1], mags[peak_idx], mags[peak_idx + 1]
        denom = (a - 2 * b + g)
        p = 0.5 * (a - g) / denom if denom != 0 else 0
        return freqs[peak_idx] + p * (freqs[1] - freqs[0])
    return freqs[peak_idx]


def freq_to_note(freq, a4=440.0):
    if freq <= 20:
        return None, 0
    semitones = 12 * np.log2(freq / a4)
    n = round(semitones)
    note = NOTE_NAMES[(n + 9) % 12]
    octave = 4 + (n + 9) // 12
    cents_off = (semitones - n) * 100      # desviación de afinación
    return f"{note}{octave}", cents_off
