#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── Configuración ──────────────────────────────────────────
const char* SSID         = "VictorWifi";
const char* PASSWORD     = "08Mayo_2006";
const char* BACKEND_URL  = "http://192.168.1.85:8000/audio";

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
