# Firmware ESP32 — Analizador de Espectro de Audio
### Proyecto: Series de Fourier aplicadas al procesamiento de señales de audio
**Materia:** Matemáticas Avanzadas para la Ingeniería  

---

## Resumen de tu tarea

Tu trabajo es conectar el micrófono MAX4466 al ESP32, capturar bloques de audio
como valores numéricos del ADC, y enviarlos por WiFi al backend de tu compañero
mediante una petición HTTP POST cada 128 ms.

El backend hace todo el procesamiento matemático (FFT, espectro de frecuencias).
Tú solo capturas y envías los datos crudos.

---

## Hardware necesario

| Componente | Cantidad |
|---|---|
| ESP32 (cualquier variante) | 1 |
| Micrófono MAX4466 | 1 |
| Botón pulsador (push button) | 1 |
| Resistencia 10kΩ | 1 |
| Cables jumper | 5 |
| Protoboard | 1 |

### Conexión MAX4466 → ESP32

| Pin MAX4466 | Pin ESP32 | Descripción |
|---|---|---|
| VCC | 3.3V | Alimentación |
| GND | GND | Tierra |
| OUT | GPIO34 | Señal analógica de audio |

> **Importante:** usa GPIO34 específicamente porque es un pin de entrada ADC
> dedicado en el ESP32. No uses GPIO34 como salida — solo lectura.

### Conexión del botón → ESP32

Usa el pin GPIO18 con una resistencia pull-down de 10kΩ a GND:

```
3.3V ──── [ Botón ] ──── GPIO18
                    │
               [ 10kΩ ]
                    │
                   GND
```

| Elemento | Conexión |
|---|---|
| Un extremo del botón | 3.3V |
| Otro extremo del botón | GPIO18 + resistencia 10kΩ a GND |

> Con este circuito: botón **no presionado** = GPIO18 lee 0 (LOW).
> Botón **presionado** = GPIO18 lee 1 (HIGH). El ESP32 solo captura
> y envía mientras el botón está presionado.

### Comportamiento del sistema con el botón

| Estado del botón | ESP32 |
|---|---|
| Sin presionar | Inactivo — no captura, no envía |
| Presionado | Captura ventanas de 1024 samples y las envía continuamente |
| Soltado | Se detiene inmediatamente al terminar la ventana actual |

---

## Qué son los samples y por qué son importantes

El MAX4466 produce un voltaje analógico que sube y baja siguiendo la forma de
onda del sonido. El ADC (Conversor Analógico-Digital) del ESP32 convierte ese
voltaje a un número entero cada cierto tiempo.

```
Voltaje analógico [0V – 3.3V]  →  ADC 12 bits  →  Entero [0 – 4095]
```

Con silencio, el micrófono produce ~1.65V (la mitad del rango), que el ADC
convierte a ~2048. Con sonido, ese valor oscila hacia arriba y hacia abajo
alrededor de 2048.

**Los samples son simplemente esas lecturas numéricas del ADC tomadas a una
frecuencia constante de 8000 veces por segundo.**

No son frecuencias. No son notas musicales. Son solo números que describen cómo
varió el voltaje del micrófono momento a momento. El backend de tu compañero
aplica la FFT a esos números para extraer las frecuencias.

---

## Parámetros que debes respetar (críticos)

Estos valores están acordados con el backend. No los cambies sin avisar:

| Parámetro | Valor | Significado |
|---|---|---|
| `fs` | **8000 Hz** | Tomas 8000 muestras por segundo |
| `N` | **1024** | Muestras por ventana (bloque) |
| Resolución ADC | **12 bits** (0 – 4095) | Nativa del ESP32, no cambiar |
| Tiempo entre envíos | **128 ms** | Resulta de N / fs = 1024 / 8000 |

### Por qué fs = 8000 Hz

Por el teorema de Nyquist, la frecuencia máxima que puedes detectar es la mitad
de fs:

```
f_max = fs / 2 = 8000 / 2 = 4000 Hz
```

Eso cubre todo el rango útil: voz humana (85 Hz – 3000 Hz) y notas musicales
del piano (~27 Hz – 4186 Hz).

### Por qué N = 1024

1024 es potencia de 2, lo cual es obligatorio para que el algoritmo FFT
(Cooley-Tukey) funcione de forma óptima en el backend. Cada ventana de 1024
muestras tomadas a 8000 Hz corresponde exactamente a 128 ms de audio:

```
tiempo de ventana = N / fs = 1024 / 8000 = 0.128 s = 128 ms
```

---

## Qué debes enviar al backend

Cada 128 ms debes mandar un HTTP POST con un JSON con esta estructura exacta:

```json
{
  "fs": 8000,
  "n": 1024,
  "timestamp": 1718042400123,
  "samples": [2048, 2061, 2075, 2089, 2048, 1998, 1953, 2010, ...]
}
```

### Descripción de cada campo

| Campo | Tipo | Descripción |
|---|---|---|
| `fs` | entero | Frecuencia de muestreo. Siempre 8000 |
| `n` | entero | Número de samples. Siempre 1024 |
| `timestamp` | entero largo | Tiempo actual en milisegundos (`millis()`) |
| `samples` | arreglo de 1024 enteros | Las lecturas del ADC en orden cronológico |

> **El arreglo `samples` debe tener siempre exactamente 1024 valores.**
> Si manda más o menos, el backend rechaza el paquete.

### Endpoint al que debes hacer el POST

```
http://<IP_DE_LA_LAPTOP_DE_TU_COMPAÑERO>:8000/audio
```

La IP la acuerdan en el momento — ambos deben estar en la misma red WiFi.

---

## Código de referencia (Arduino C++)

```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Configuración ──────────────────────────────────────────
const char* SSID         = "TU_RED_WIFI";
const char* PASSWORD     = "TU_CONTRASEÑA";
const char* BACKEND_URL  = "http://192.168.1.X:8000/audio";

const int   ADC_PIN      = 34;       // GPIO34 — señal del micrófono
const int   BTN_PIN      = 18;       // GPIO18 — botón de captura
const int   LED_PIN      = 2;        // LED onboard — indica grabación activa
const int   FS           = 8000;     // Hz — no cambiar
const int   N_SAMPLES    = 1024;     // muestras por ventana — no cambiar
const int   SAMPLE_US    = 1000000 / FS;  // microsegundos entre muestras = 125 µs

uint16_t samples[N_SAMPLES];

// ── Setup ──────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);          // ADC de 12 bits → valores 0–4095
  analogSetAttenuation(ADC_11db);    // rango completo 0–3.3V

  pinMode(BTN_PIN, INPUT);           // botón con pull-down externo de 10kΩ
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);        // LED apagado al inicio

  WiFi.begin(SSID, PASSWORD);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado. IP: " + WiFi.localIP().toString());
  Serial.println("Listo. Mantén presionado el botón para capturar audio.");
}

// ── Captura de audio ───────────────────────────────────────
void capturarVentana() {
  for (int i = 0; i < N_SAMPLES; i++) {
    unsigned long t0 = micros();
    samples[i] = analogRead(ADC_PIN);     // lectura ADC [0–4095]
    while (micros() - t0 < SAMPLE_US);   // esperar hasta siguiente muestra
  }
}

// ── Envío al backend ───────────────────────────────────────
void enviarMuestras() {
  if (WiFi.status() != WL_CONNECTED) return;

  StaticJsonDocument<8192> doc;
  doc["fs"]        = FS;
  doc["n"]         = N_SAMPLES;
  doc["timestamp"] = millis();

  JsonArray arr = doc.createNestedArray("samples");
  for (int i = 0; i < N_SAMPLES; i++) {
    arr.add(samples[i]);
  }

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(BACKEND_URL);
  http.addHeader("Content-Type", "application/json");

  int code = http.POST(body);
  if (code > 0) {
    Serial.println("POST enviado. Código: " + String(code));
  } else {
    Serial.println("Error HTTP: " + String(code));
  }
  http.end();
}

// ── Loop principal ─────────────────────────────────────────
void loop() {
  if (digitalRead(BTN_PIN) == HIGH) {
    // Botón presionado → capturar y enviar
    digitalWrite(LED_PIN, HIGH);     // enciende LED — indica grabación activa
    capturarVentana();               // toma 1024 muestras a 8000 Hz → 128 ms
    enviarMuestras();                // empaca y manda el JSON al backend
  } else {
    // Botón suelto → inactivo
    digitalWrite(LED_PIN, LOW);      // apaga LED
  }
}
```

### Librerías necesarias (instalar en Arduino IDE)

- `ArduinoJson` by Benoit Blanchon — versión 6.x
- `WiFi` — viene incluida con el core ESP32
- `HTTPClient` — viene incluida con el core ESP32

Para instalarlas: **Arduino IDE → Tools → Manage Libraries → buscar por nombre**

---

## Verificación antes de entregar tu parte

Antes de que tu compañero conecte el backend, puedes verificar que todo funciona
abriendo el **Serial Monitor** (115200 baud) y comprobando:

- [ ] Mensaje "Conectado. IP: 192.168.X.X" al arrancar
- [ ] Mensaje "Listo. Mantén presionado el botón para capturar audio." al arrancar
- [ ] Sin presionar el botón: el LED onboard permanece **apagado**, no se envían POST
- [ ] Al presionar el botón: el LED onboard se **enciende** y aparece "POST enviado. Código: 200" cada ~128 ms
- [ ] Al soltar el botón: el LED se **apaga** y los POST se detienen
- [ ] Los valores del ADC oscilan alrededor de ~2048 en silencio
- [ ] Los valores se mueven claramente cuando hablas o silbas cerca del micrófono

Si ves valores siempre en 0 o siempre en 4095, revisa la conexión del MAX4466.
Si el botón no responde, verifica la resistencia pull-down de 10kΩ a GND.

---

## Qué NO tienes que hacer

- No calcules la FFT en el ESP32 — eso lo hace el backend
- No filtres ni proceses los samples — mándalos crudos
- No cambies `fs` ni `N` sin avisarle a tu compañero — rompe el backend

---

## Resumen visual del flujo

```
[ Botón presionado ]
    │  GPIO18 = HIGH
    ▼
MAX4466 (micrófono)
    │  voltaje analógico 0–3.3V
    ▼
ESP32 ADC GPIO34
    │  convierte a enteros 0–4095
    │  8000 veces por segundo
    │  acumula 1024 muestras (128 ms)
    │  LED onboard encendido
    ▼
HTTP POST → http://<IP>:8000/audio
    │  JSON: { fs, n, timestamp, samples[1024] }
    ▼
Backend Python (tu compañero)
    │  centra la señal (resta media)
    │  aplica ventana Hanning
    │  calcula FFT con NumPy
    │  extrae frecuencias y amplitudes
    ▼
Frontend Web
    espectro de audio en tiempo real

[ Botón suelto ] → ESP32 inactivo, LED apagado, no se envía nada
```
