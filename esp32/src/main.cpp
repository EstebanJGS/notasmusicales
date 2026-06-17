#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "config.h"

uint16_t buffer[BUFFER_SIZE];
int baseline = 0;

// ── WiFi ──────────────────────────────────────────────────────────────────────

void connectWiFi() {
    Serial.printf("Conectando a %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(200);
        Serial.print(".");
    }
    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
}

// ── Calibración ───────────────────────────────────────────────────────────────

void calibrateBaseline() {
    long sum = 0;
    for (int i = 0; i < BASELINE_SAMPLES; i++) {
        sum += analogRead(MIC_PIN);
        delayMicroseconds(500);
    }
    baseline = sum / BASELINE_SAMPLES;
    Serial.printf("Baseline: %d\n", baseline);
}

// ── Onset detection (RMS de energía sobre ventana corta) ──────────────────────

bool detectOnset() {
    long sumSq = 0;
    for (int i = 0; i < ONSET_WINDOW; i++) {
        int v = analogRead(MIC_PIN) - baseline;
        sumSq += (long)v * v;
        delayMicroseconds(SAMPLE_PERIOD_US);
    }
    int rms = (int)sqrt((float)sumSq / ONSET_WINDOW);
    return rms > ONSET_THRESHOLD;
}

// ── Captura ───────────────────────────────────────────────────────────────────

void captureBuffer() {
    for (int i = 0; i < BUFFER_SIZE; i++) {
        unsigned long t0 = micros();
        buffer[i] = (uint16_t)analogRead(MIC_PIN);
        while (micros() - t0 < SAMPLE_PERIOD_US) {}   // sample rate fijo
    }
}

// ── Envío binario ─────────────────────────────────────────────────────────────

void sendBuffer() {
    if (WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    String url = String("http://") + SERVER_HOST + ":" + SERVER_PORT + SERVER_ENDPOINT;
    http.begin(url);
    http.addHeader("Content-Type", "application/octet-stream");
    http.addHeader("X-Sample-Rate", String(SAMPLE_RATE));

    int code = http.POST((uint8_t*)buffer, BUFFER_SIZE * sizeof(uint16_t));
    Serial.printf("POST %d\n", code);
    http.end();
}

// ── Setup / Loop ──────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    analogReadResolution(12);          // 0-4095
    analogSetAttenuation(ADC_11db);    // rango ~0-3.3 V
    connectWiFi();
    calibrateBaseline();
}

void loop() {
    if (detectOnset()) {
        captureBuffer();
        sendBuffer();
        delay(300);              // debounce — evita doble disparo del mismo golpe
        calibrateBaseline();     // recalibra para la siguiente nota
    }
}
