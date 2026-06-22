"""
Backend — Analizador de Espectro de Audio con Series de Fourier
================================================================

Flujo:
  ESP32  --HTTP POST JSON-->  /audio   (este servidor)
                                  |
                                  | 1. centra la señal (resta media)
                                  | 2. aplica ventana de Hanning
                                  | 3. calcula la FFT (np.fft.fft)
                                  | 4. obtiene magnitud y fase
                                  | 5. detecta picos (frecuencias dominantes)
                                  | 6. identifica la nota musical más cercana
                                  v
  Frontend  <--WebSocket JSON--  /ws   (este servidor)

JSON que el ESP32 debe enviar a POST /audio:
{
  "fs": 8000,
  "n": 1024,
  "timestamp": 1718042400123,
  "samples": [2048, 2061, 2075, 2089, ...]   # n enteros, 0-4095
}
"""

import asyncio
import json
import time

import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from fourier import procesar_ventana

app = FastAPI(title="Analizador de Espectro de Audio — Fourier")

# CORS abierto para que el frontend (servido en otro puerto/origen) pueda
# conectarse sin problemas durante desarrollo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────
# Modelo de entrada — valida exactamente el JSON que manda el ESP32
# ──────────────────────────────────────────────────────────────────────────
class VentanaAudio(BaseModel):
    fs: int
    n: int
    timestamp: int
    samples: list[int]

    @field_validator("samples")
    @classmethod
    def validar_longitud(cls, v, info):
        n = info.data.get("n")
        if n is not None and len(v) != n:
            raise ValueError(
                f"El arreglo 'samples' tiene {len(v)} elementos, "
                f"pero 'n' indica {n}. Deben coincidir."
            )
        return v

    @field_validator("samples")
    @classmethod
    def validar_rango_adc(cls, v):
        # El ADC del ESP32 es de 12 bits → valores válidos 0-4095
        fuera_de_rango = [x for x in v if x < 0 or x > 4095]
        if fuera_de_rango:
            raise ValueError(
                "Hay valores fuera del rango del ADC (0-4095). "
                "Verifica analogReadResolution(12) en el firmware."
            )
        return v


# ──────────────────────────────────────────────────────────────────────────
# Gestor de conexiones WebSocket — para reenviar resultados al frontend
# ──────────────────────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        muertos = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                muertos.append(ws)
        for ws in muertos:
            self.disconnect(ws)


manager = ConnectionManager()

# Última ventana procesada y último timestamp aceptado (para descartar
# paquetes duplicados o desordenados si el ESP32 los manda fuera de orden).
ultimo_timestamp = -1


# ──────────────────────────────────────────────────────────────────────────
# Endpoint que recibe los datos del ESP32
# ──────────────────────────────────────────────────────────────────────────
@app.post("/audio")
async def recibir_audio(ventana: VentanaAudio):
    global ultimo_timestamp

    # Descarta paquetes desordenados o duplicados (ver README del firmware:
    # el timestamp sirve exactamente para esto).
    if ventana.timestamp <= ultimo_timestamp:
        return {"status": "ignorado", "razon": "timestamp desordenado o duplicado"}
    ultimo_timestamp = ventana.timestamp

    # ── DIAGNÓSTICO TEMPORAL ────────────────────────────────────────────
    # Imprime estadísticas básicas de la ventana cruda ANTES de procesar,
    # para confirmar si realmente hay señal de audio variando o si es
    # ruido plano / silencio constante.
    arr = np.array(ventana.samples)
    print(
        f"[DEBUG] min={arr.min()} max={arr.max()} "
        f"media={arr.mean():.1f} desviación={arr.std():.1f} "
        f"clientes_ws={len(manager.active)}"
    )
    # ──────────────────────────────────────────────────────────────────────

    resultado = procesar_ventana(
        samples=ventana.samples,
        fs=ventana.fs,
        timestamp=ventana.timestamp,
    )

    # Reenvía el resultado a todos los clientes web conectados en tiempo real
    await manager.broadcast(resultado)

    return {"status": "ok", "picos_detectados": len(resultado["picos"])}


# ──────────────────────────────────────────────────────────────────────────
# WebSocket que consume el frontend para recibir el espectro en vivo
# ──────────────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # No esperamos mensajes del cliente, solo mantenemos la conexión viva.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ──────────────────────────────────────────────────────────────────────────
# Endpoint de salud — útil para que tu compañero pruebe la conexión
# ──────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "clientes_ws_conectados": len(manager.active),
        "ultimo_timestamp_recibido": ultimo_timestamp,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)