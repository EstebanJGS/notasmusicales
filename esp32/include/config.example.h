#pragma once

// Copia este archivo a "config.h" y rellena tus valores reales.
// config.h está en .gitignore para no subir credenciales al repositorio.

// WiFi
#define WIFI_SSID     "TU_SSID"
#define WIFI_PASSWORD "TU_PASSWORD"

// Servidor Python
#define SERVER_HOST "192.168.1.100"
#define SERVER_PORT 5000
#define SERVER_ENDPOINT "/audio"

// ADC
#define MIC_PIN          34      // GPIO34 (ADC1_CH6) — solo lectura
#define SAMPLE_RATE      8000    // Hz
#define BUFFER_SIZE      2048    // muestras por nota (potencia de 2)
#define SAMPLE_PERIOD_US (1000000 / SAMPLE_RATE)

// Onset detection
#define ONSET_WINDOW      32     // muestras para calcular RMS de energía
#define ONSET_THRESHOLD   800    // ajustar según ruido ambiente (rango 0-4095)
#define BASELINE_SAMPLES  200    // muestras para calibrar silencio
