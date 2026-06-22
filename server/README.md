# Backend — Analizador de Espectro de Audio

Recibe ventanas de audio del ESP32 (HTTP POST), les aplica la cadena
**centrado → ventana de Hanning → FFT → detección de picos → nota musical**,
y retransmite el resultado en tiempo real a cualquier frontend conectado por
WebSocket.

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecutar el servidor

```bash
python main.py
```

o equivalentemente:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

El servidor queda escuchando en `http://0.0.0.0:8000`. Anota la IP de tu
laptop en la red WiFi (`ipconfig` en Windows, `ifconfig`/`ip a` en Linux/Mac)
y pásasela a tu compañero para que la ponga en `BACKEND_URL` del firmware.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/audio` | Recibe el JSON del ESP32, procesa y retransmite |
| `WS` | `/ws` | El frontend se conecta aquí para recibir el espectro en vivo |
| `GET` | `/health` | Verifica que el servidor está vivo y cuántos clientes WS hay conectados |

## Probar sin el hardware (con el simulador)

Mientras tu compañero termina el circuito, puedes probar todo el pipeline
matemático con datos sintéticos:

```bash
# Terminal 1 — levanta el servidor
python main.py

# Terminal 2 — simula al ESP32 enviando un La (440Hz) + su octava (880Hz)
python simulador_esp32.py --freq 440 880 --url http://localhost:8000/audio
```

Verás en la Terminal 1 los logs de cada POST recibido, y puedes conectar
cualquier cliente WebSocket (o tu frontend) a `ws://localhost:8000/ws` para
ver el JSON de resultado en tiempo real.

### Otros ejemplos del simulador

```bash
# Una sola nota pura — Do central
python simulador_esp32.py --freq 261.63

# Un acorde — Do mayor (Do, Mi, Sol)
python simulador_esp32.py --freq 261.63 329.63 392.00

# Más ciclos, más rápido
python simulador_esp32.py --freq 440 --ciclos 50 --intervalo 0.05
```

## Formato de salida (lo que recibe el frontend por WebSocket)

```json
{
  "timestamp": 1718042400123,
  "fs": 8000,
  "n": 1024,
  "amplitud_pp": 2415.0,
  "espectro": {
    "frecuencias": [0.0, 7.8, 15.6, ...],
    "magnitudes": [0.0, 1.2, 0.8, ...]
  },
  "picos": [
    {
      "frecuencia_hz": 437.5,
      "magnitud": 420.69,
      "fase_rad": -1.234,
      "nota": "La",
      "octava": 4,
      "cents_desviacion": -9.9
    }
  ],
  "nota_dominante": "La"
}
```

## Estructura de archivos

```
audio_backend/
├── main.py              # FastAPI: endpoints HTTP y WebSocket
├── fourier.py            # Toda la matemática: FFT, ventaneo, picos, notas
├── simulador_esp32.py    # Genera datos sintéticos para probar sin hardware
├── requirements.txt
└── README.md
```

## Por qué cada paso matemático está ahí (resumen rápido)

| Paso | Por qué es necesario |
|---|---|
| Centrado (`x - mean(x)`) | El ADC entrega [0,4095], no [-2048,2047]. Sin centrar, aparece un pico falso enorme en 0 Hz |
| Ventana de Hanning | Reduce el *spectral leakage* causado por truncar la señal a N muestras (la ventana rectangular implícita produce un sinc en frecuencia — Ejemplo 3.25) |
| FFT (`np.fft.fft`) | Calcula la DFT en O(N log N) en vez de O(N²) — necesario para tiempo real |
| Solo mitad positiva | El espectro de una señal real es simétrico; la segunda mitad es información redundante |
| Normalizar por N/2 | Recupera las amplitudes reales de las senoidales originales |
| Detección de picos | Identifica las frecuencias dominantes — eso es lo que se interpreta como "notas" |
