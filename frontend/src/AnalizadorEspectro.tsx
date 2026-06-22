import React, { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = "ws://localhost:8000/ws";

export default function AnalizadorEspectro() {
  const [conectado, setConectado] = useState(false);
  const [resultado, setResultado] = useState(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ── Conexión WebSocket al backend ──────────────────────────────────────
  useEffect(() => {
    function conectar() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConectado(true);
      ws.onclose = () => {
        setConectado(false);
        // Reintenta cada 2s si se cae la conexión
        setTimeout(conectar, 2000);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setResultado(data);
        } catch (e) {
          console.error("JSON inválido recibido del backend", e);
        }
      };
    }

    conectar();
    return () => wsRef.current?.close();
  }, []);

  // ── Dibujar la onda en el canvas cada vez que llega un resultado nuevo ──
  const dibujarOnda = useCallback((muestras: number[]) => {
    const canvas = canvasRef.current;
    if (!canvas || !muestras || muestras.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    
    const W = canvas.width;
    const H = canvas.height;
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

    ctx.clearRect(0, 0, W, H);

    // línea central de referencia (silencio / cero)
    ctx.strokeStyle = isDark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.12)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, H / 2);
    ctx.lineTo(W, H / 2);
    ctx.stroke();

    // la onda capturada
    const min = Math.min(...muestras);
    const max = Math.max(...muestras);
    const rango = Math.max(max - min, 1);

    ctx.strokeStyle = "#7F77DD";
    ctx.lineWidth = 2;
    ctx.beginPath();
    muestras.forEach((v, i) => {
      const x = (i / (muestras.length - 1)) * W;
      const yNorm = (v - min) / rango;
      const y = H - yNorm * H * 0.8 - H * 0.1;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  }, []);

  useEffect(() => {
    if (resultado?.muestras) dibujarOnda(resultado.muestras);
  }, [resultado, dibujarOnda]);

  // ── Datos derivados para mostrar ────────────────────────────────────────
  const nota = resultado?.nota_dominante ?? null;
  const picoFundamental = resultado?.picos?.[0] ?? null;
  const picos = resultado?.picos ?? [];

  return (
    <div style={{ padding: "1rem 0" }}>
      <EstadoConexion conectado={conectado} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
          marginTop: 16,
        }}
      >
        <TarjetaNota nota={nota} pico={picoFundamental} />
        <TarjetaFrecuencias picos={picos} />
      </div>

      <div style={{ marginTop: 12 }}>
        <TarjetaOnda canvasRef={canvasRef} tieneDatos={!!resultado} fs={resultado?.fs} />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
function EstadoConexion({ conectado }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: conectado ? "var(--color-text-success)" : "var(--color-text-danger)",
          display: "inline-block",
        }}
      />
      <span style={{ color: "var(--color-text-secondary)" }}>
        {conectado ? "Conectado al backend" : "Esperando conexión..."}
      </span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
function TarjetaNota({ nota, pico }) {
  return (
    <div
      style={{
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "1.25rem",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 180,
        textAlign: "center",
      }}
    >
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 12px" }}>
        Nota detectada
      </p>
      {nota ? (
        <>
          <p style={{ fontSize: 48, fontWeight: 500, margin: 0, color: "var(--color-text-primary)" }}>
            {nota}
            {pico?.octava ?? ""}
          </p>
          <p style={{ fontSize: 13, color: "var(--color-text-tertiary)", margin: "8px 0 0" }}>
            {pico ? `${pico.frecuencia_hz.toFixed(1)} Hz` : ""}
            {pico?.cents_desviacion != null && (
              <span> &middot; {pico.cents_desviacion > 0 ? "+" : ""}{pico.cents_desviacion.toFixed(0)} cents</span>
            )}
          </p>
        </>
      ) : (
        <p style={{ fontSize: 24, color: "var(--color-text-tertiary)", margin: 0 }}>—</p>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
function TarjetaFrecuencias({ picos }) {
  const maxMag = Math.max(...picos.map((p) => p.magnitud), 1);

  return (
    <div
      style={{
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "1.25rem",
        minHeight: 180,
      }}
    >
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 16px" }}>
        Compuesta por
      </p>

      {picos.length === 0 ? (
        <p style={{ fontSize: 14, color: "var(--color-text-tertiary)", margin: 0 }}>
          Sin señal detectada
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {picos.map((p, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  fontSize: 13,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-text-secondary)",
                  minWidth: 64,
                }}
              >
                {p.frecuencia_hz.toFixed(0)} Hz
              </span>
              <div
                style={{
                  flex: 1,
                  height: 8,
                  borderRadius: "var(--border-radius-md)",
                  background: "var(--color-background-secondary)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${(p.magnitud / maxMag) * 100}%`,
                    background: "#7F77DD",
                    borderRadius: "var(--border-radius-md)",
                  }}
                />
              </div>
              <span
                style={{
                  fontSize: 12,
                  color: "var(--color-text-tertiary)",
                  minWidth: 36,
                  textAlign: "right",
                }}
              >
                {p.nota}
                {p.octava}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
function TarjetaOnda({ canvasRef, tieneDatos, fs }) {
  return (
    <div
      style={{
        background: "var(--color-background-primary)",
        border: "0.5px solid var(--color-border-tertiary)",
        borderRadius: "var(--border-radius-lg)",
        padding: "1.25rem",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: 0 }}>
          Onda capturada
        </p>
        {fs && (
          <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", margin: 0 }}>
            fs = {fs} Hz
          </p>
        )}
      </div>
      <canvas
        ref={canvasRef}
        width={640}
        height={160}
        style={{ width: "100%", height: 160, display: "block" }}
      />
      {!tieneDatos && (
        <p style={{ fontSize: 13, color: "var(--color-text-tertiary)", margin: "12px 0 0", textAlign: "center" }}>
          Presiona el botón en el ESP32 para capturar audio
        </p>
      )}
    </div>
  );
}