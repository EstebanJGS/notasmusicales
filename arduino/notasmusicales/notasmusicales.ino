// ── Librerías del core ESP32 (no requieren instalación adicional) ──────────────
#include <WiFi.h>
#include <HTTPClient.h>

// ── Configuración ─────────────────────────────────────────────────────────────
const char* ssid       = "TU_SSID";
const char* password   = "TU_PASSWORD";
const char* serverUrl  = "http://TU_SERVIDOR:5000/audio";

// Pon en false para probar lectura sin servidor
#define SEND_ENABLED false

#define MIC_PIN          34
#define SAMPLE_RATE      8000
#define BUFFER_SIZE      2048
#define SAMPLE_PERIOD_US (1000000 / SAMPLE_RATE)

#define ONSET_WINDOW      32
#define ONSET_THRESHOLD   800    // ajustar según ruido ambiente (rango 0-4095)
#define BASELINE_SAMPLES  200

// ── Variables globales ────────────────────────────────────────────────────────
uint16_t buffer[BUFFER_SIZE];
int baseline = 0;

// ── WiFi ──────────────────────────────────────────────────────────────────────

void connectWiFi() {
  if (!SEND_ENABLED) {
    Serial.println("[WiFi] Modo sin servidor — WiFi desactivado");
    return;
  }
  Serial.printf("[WiFi] Conectando a %s", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] Conectado. IP: %s\n", WiFi.localIP().toString().c_str());
}

// ── Calibración ───────────────────────────────────────────────────────────────

void calibrateBaseline() {
  Serial.println("[CAL] Calibrando baseline...");
  long sum = 0;
  for (int i = 0; i < BASELINE_SAMPLES; i++) {
    sum += analogRead(MIC_PIN);
    delayMicroseconds(500);
  }
  baseline = sum / BASELINE_SAMPLES;
  Serial.printf("[CAL] Baseline = %d (rango 0-4095)\n", baseline);
}

// ── Onset detection ───────────────────────────────────────────────────────────

bool detectOnset() {
  long sumSq = 0;
  for (int i = 0; i < ONSET_WINDOW; i++) {
    int v = analogRead(MIC_PIN) - baseline;
    sumSq += (long)v * v;
    delayMicroseconds(SAMPLE_PERIOD_US);
  }
  int rms = (int)sqrt((float)sumSq / ONSET_WINDOW);
  Serial.printf("[ADC] RMS = %4d  (umbral = %d)%s\n",
                rms, ONSET_THRESHOLD, rms > ONSET_THRESHOLD ? "  << ONSET" : "");
  return rms > ONSET_THRESHOLD;
}

// ── Captura ───────────────────────────────────────────────────────────────────

void captureBuffer() {
  Serial.printf("[CAP] Capturando %d muestras @ %d Hz...\n", BUFFER_SIZE, SAMPLE_RATE);
  uint16_t minVal = 4095, maxVal = 0;
  long sum = 0;

  for (int i = 0; i < BUFFER_SIZE; i++) {
    unsigned long t0 = micros();
    buffer[i] = (uint16_t)analogRead(MIC_PIN);
    if (buffer[i] < minVal) minVal = buffer[i];
    if (buffer[i] > maxVal) maxVal = buffer[i];
    sum += buffer[i];
    while (micros() - t0 < SAMPLE_PERIOD_US) {}
  }

  int avg = sum / BUFFER_SIZE;
  Serial.printf("[CAP] OK — min=%d  max=%d  prom=%d  amplitud=%d\n",
                minVal, maxVal, avg, maxVal - minVal);
}

// ── Envío HTTP binario ────────────────────────────────────────────────────────

void sendBuffer() {
  if (!SEND_ENABLED) {
    Serial.println("[HTTP] Envío desactivado — buffer listo para análisis");
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Sin conexión WiFi");
    return;
  }
  Serial.printf("[HTTP] Enviando %d bytes a %s...\n",
                BUFFER_SIZE * (int)sizeof(uint16_t), serverUrl);
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/octet-stream");
  http.addHeader("X-Sample-Rate", String(SAMPLE_RATE));
  int code = http.POST((uint8_t*)buffer, BUFFER_SIZE * sizeof(uint16_t));
  if (code > 0) {
    Serial.printf("[HTTP] Respuesta %d: %s\n", code, http.getString().c_str());
  } else {
    Serial.printf("[HTTP] Error: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

// ── Setup / Loop ──────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n========== NOTAS MUSICALES ESP32 ==========");
  Serial.printf("Buffer: %d muestras | Sample rate: %d Hz | Duracion: %.0f ms\n",
                BUFFER_SIZE, SAMPLE_RATE, (float)BUFFER_SIZE / SAMPLE_RATE * 1000);
  Serial.printf("Onset threshold: %d | Servidor: %s\n",
                ONSET_THRESHOLD, SEND_ENABLED ? "ACTIVO" : "DESACTIVADO");
  Serial.println("============================================");

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  connectWiFi();
  calibrateBaseline();
  Serial.println("[SYS] Listo — esperando sonido...\n");
}

void loop() {
  if (detectOnset()) {
    Serial.println("[SYS] ---- Nota detectada ----");
    captureBuffer();
    sendBuffer();
    delay(300);
    calibrateBaseline();
    Serial.println("[SYS] Esperando siguiente nota...\n");
  }
}
