# Notas Musicales 🎵

Detección de notas musicales en tiempo real con un **ESP32** y un servidor **Python (Flask + NumPy)**.

El ESP32 captura audio por su ADC, detecta el inicio de una nota (onset) y envía el buffer crudo por HTTP. El servidor aplica una FFT (transformada de Fourier) para estimar la frecuencia fundamental y la traduce a nota musical y desviación en cents.

## Estructura

```
esp32/      Firmware PlatformIO (recomendado)
arduino/    Sketch equivalente para el IDE de Arduino
server/     Servidor Python que recibe el audio y calcula la nota
```

## Servidor

```bash
cd server
pip install -r requirements.txt
python app.py            # escucha en 0.0.0.0:5000
```

Endpoints:
- `POST /audio` — recibe el buffer binario (uint16 little-endian) y devuelve `{ note, freq, cents }`.
- `GET  /health` — comprobación de estado.

## ESP32 (PlatformIO)

1. Copia `esp32/include/config.example.h` a `esp32/include/config.h`.
2. Rellena tu `WIFI_SSID`, `WIFI_PASSWORD` y la IP del servidor (`SERVER_HOST`).
3. Compila y sube:

```bash
cd esp32
pio run -t upload
pio device monitor
```

> `config.h` está en `.gitignore`: ahí van tus credenciales y **no se suben** al repositorio.

## Arduino IDE (alternativa)

Abre `arduino/notasmusicales/notasmusicales.ino` y edita `ssid`, `password` y `serverUrl`.
Pon `SEND_ENABLED` en `false` para probar la lectura del micrófono sin servidor.

## Cómo funciona

| Etapa | Descripción |
|-------|-------------|
| Onset detection | RMS de energía sobre una ventana corta; dispara cuando supera el umbral. |
| Captura | 2048 muestras a 8 kHz (~256 ms) desde el ADC de 12 bits. |
| FFT | `numpy.fft.rfft` con ventana de Hanning e interpolación parabólica para precisión sub-bin. |
| Nota | `12 · log₂(f / 440)` → nombre de nota, octava y cents de desviación. |

## Versión didáctica de la FFT (para exponer el algoritmo)

`server/fourier.py` usa `numpy.fft` (rápido, caja negra). Para **explicar cómo funciona la
Transformada Rápida de Fourier por dentro**, `server/fft_didactica.py` la implementa a mano
con ciclos, sin numpy:

- `dft_directa()` — la DFT por definición, dos ciclos anidados, O(N²) (la versión lenta).
- `fft_iterativa()` — la **FFT** (Cooley-Tukey radix-2, iterativa con ciclos), O(N log N).
- `detect_pitch_manual()` — detecta la nota usando esa FFT manual.

Ejecuta la demostración (compara ambas, detecta la nota y mide tiempos):

```bash
cd server
python fft_didactica.py
```

Salida típica: `fft_iterativa` da el mismo resultado que `dft_directa`, detecta `A4`, y la
FFT resulta **~600× más rápida** que la DFT directa sobre 2048 muestras.

Para que el **servidor** use este motor manual en lugar de numpy:

```powershell
$env:FFT_ENGINE="manual"; python app.py    # PowerShell
```
