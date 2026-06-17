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
