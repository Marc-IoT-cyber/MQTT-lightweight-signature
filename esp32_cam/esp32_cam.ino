/*
 * esp32_cam.ino
 * Capture d'image + signature HMAC + chiffrement XOR (ASM ou C)
 * Publication des métriques comparatives sur MQTT
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_camera.h>
#include <mbedtls/md.h>
#include <base64.h>
#include "crypto_asm.h"

/* ============================================================
 * Configuration
 * ============================================================ */
const char* WIFI_SSID     = "kkkk";
const char* WIFI_PASSWORD = "12345678";

const char* MQTT_SERVER   = "192.168.137.1";
const int   MQTT_PORT     = 1883;
const char* MQTT_TOPIC    = "iot/camera/photo";
const char* MQTT_METRICS  = "iot/metrics";

const char* SECRET_KEY    = "ma_cle_secrete_iot_2025";
const uint8_t XOR_KEY     = 0xAA;

const framesize_t FRAME_SIZE = FRAMESIZE_QQVGA;
const int         JPEG_QUALITY = 20;
const size_t      MQTT_BUFFER_SIZE = 16384;

const int CAPTURE_INTERVAL_MS = 15000;
const int BENCH_ITERATIONS = 1000;
const int BENCH_SIZE = 256;

/* Fréquence CPU ESP32 en Hz (240 MHz) */
const float CPU_FREQ_HZ = 240000000.0;
/* Consommation CPU ESP32 en mA (à 240 MHz, toutes périphéries actives) */
const float CPU_CURRENT_MA = 40.0;
/* Tension d'alimentation en V */
const float VOLTAGE_V = 3.3;

/* ============================================================
 * Broches ESP32-CAM
 * ============================================================ */
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

/* ============================================================
 * Variables
 * ============================================================ */
WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastCapture = 0;
unsigned long lastReconnect = 0;
unsigned long compteurMessages = 0;
unsigned long compteurEchecs = 0;

/* ============================================================
 * Prototypes
 * ============================================================ */
void reconnectWiFi();
void reconnectMQTT();
String computeHMAC(const String& message);
bool captureAndSend();
void publierMetriques();
void xor_cipher_c(uint8_t *data, uint8_t key, int len);
float mesurerEnergie(float temps_ms);
float mesurerCPU(float temps_us);

/* ============================================================
 * Setup
 * ============================================================ */
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=== ESP32-CAM - Signature légère MQTT ===\n");

    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size   = FRAME_SIZE;
    config.jpeg_quality = JPEG_QUALITY;
    config.fb_count     = 1;

    if (esp_camera_init(&config) != ESP_OK) {
        Serial.println("Erreur caméra");
        ESP.restart();
    }
    Serial.println("Caméra OK");

    reconnectWiFi();

    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    mqttClient.setBufferSize(MQTT_BUFFER_SIZE);
    mqttClient.setKeepAlive(60);
    reconnectMQTT();

    Serial.println("\n=== Prêt ===\n");
}

/* ============================================================
 * Reconnect Wi-Fi
 * ============================================================ */
void reconnectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.print("Wi-Fi...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int t = 0;
    while (WiFi.status() != WL_CONNECTED && t < 40) {
        delay(500);
        Serial.print(".");
        t++;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("Wi-Fi OK : %s\n", WiFi.localIP().toString().c_str());
    } else {
        ESP.restart();
    }
}

/* ============================================================
 * Reconnect MQTT
 * ============================================================ */
void reconnectMQTT() {
    if (mqttClient.connected()) return;

    String clientId = "ESP32CAM-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqttClient.connect(clientId.c_str())) {
        Serial.println("MQTT OK");
    } else {
        Serial.printf("MQTT echec rc=%d\n", mqttClient.state());
    }
}

/* ============================================================
 * HMAC-SHA256
 * ============================================================ */
String computeHMAC(const String& message) {
    byte hmacResult[32];
    mbedtls_md_context_t ctx;
    mbedtls_md_init(&ctx);
    mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
    mbedtls_md_hmac_starts(&ctx, (const unsigned char*)SECRET_KEY, strlen(SECRET_KEY));
    mbedtls_md_hmac_update(&ctx, (const unsigned char*)message.c_str(), message.length());
    mbedtls_md_hmac_finish(&ctx, hmacResult);
    mbedtls_md_free(&ctx);

    String hex = "";
    for (int i = 0; i < 32; i++) {
        if (hmacResult[i] < 16) hex += "0";
        hex += String(hmacResult[i], HEX);
    }
    return hex;
}

/* ============================================================
 * Version C du chiffrement (pour comparaison)
 * ============================================================ */
void xor_cipher_c(uint8_t *data, uint8_t key, int len) {
    for (int i = 0; i < len; i++) {
        data[i] ^= key;
    }
}

/* ============================================================
 * Estimation CPU et énergie
 * ============================================================ */
float mesurerCPU(float temps_us) {
    // Cycles = temps (s) × fréquence (Hz)
    float temps_s = temps_us / 1000000.0;
    return temps_s * CPU_FREQ_HZ;
}

float mesurerEnergie(float temps_ms) {
    // Energie (mJ) = Courant (mA) × Tension (V) × Temps (s)
    float temps_s = temps_ms / 1000.0;
    return CPU_CURRENT_MA * VOLTAGE_V * temps_s;
}

/* ============================================================
 * Publication des métriques comparatives
 * ============================================================ */
void publierMetriques() {
    Serial.println("\n=== Benchmark ASM vs C ===");

    uint8_t original[BENCH_SIZE];
    for (int i = 0; i < BENCH_SIZE; i++) original[i] = (uint8_t)(i & 0xFF);

    uint8_t buffer[BENCH_SIZE];

    /* --- ASM --- */
    unsigned long ram_avant_asm = ESP.getFreeHeap();
    memcpy(buffer, original, BENCH_SIZE);
    unsigned long t_asm_start = micros();
    for (int i = 0; i < BENCH_ITERATIONS; i++) {
        xor_cipher(buffer, XOR_KEY, BENCH_SIZE);
    }
    unsigned long t_asm_end = micros();
    unsigned long ram_apres_asm = ESP.getFreeHeap();

    float temps_asm_us = (float)(t_asm_end - t_asm_start) / BENCH_ITERATIONS;
    float ram_asm = (float)(ram_avant_asm - ram_apres_asm);

    /* --- C --- */
    unsigned long ram_avant_c = ESP.getFreeHeap();
    memcpy(buffer, original, BENCH_SIZE);
    unsigned long t_c_start = micros();
    for (int i = 0; i < BENCH_ITERATIONS; i++) {
        xor_cipher_c(buffer, XOR_KEY, BENCH_SIZE);
    }
    unsigned long t_c_end = micros();
    unsigned long ram_apres_c = ESP.getFreeHeap();

    float temps_c_us = (float)(t_c_end - t_c_start) / BENCH_ITERATIONS;
    float ram_c = (float)(ram_avant_c - ram_apres_c);

    /* --- Calculs dérivés --- */
    float cpu_asm = mesurerCPU(temps_asm_us);
    float cpu_c = mesurerCPU(temps_c_us);

    float energie_asm = mesurerEnergie(temps_asm_us / 1000.0);
    float energie_c = mesurerEnergie(temps_c_us / 1000.0);

    float latence_asm = temps_asm_us;
    float latence_c = temps_c_us;

    float gain_temps = 100.0 * (temps_c_us - temps_asm_us) / temps_c_us;
    float gain_energie = 100.0 * (energie_c - energie_asm) / energie_c;

    /* --- Affichage local --- */
    Serial.printf("Temps ASM  : %.2f us\n", temps_asm_us);
    Serial.printf("Temps C    : %.2f us\n", temps_c_us);
    Serial.printf("CPU ASM    : %.0f cycles\n", cpu_asm);
    Serial.printf("CPU C      : %.0f cycles\n", cpu_c);
    Serial.printf("RAM ASM    : %.0f octets\n", ram_asm);
    Serial.printf("RAM C      : %.0f octets\n", ram_c);
    Serial.printf("Energie ASM: %.6f mJ\n", energie_asm);
    Serial.printf("Energie C  : %.6f mJ\n", energie_c);
    Serial.printf("Gain temps : %.1f %%\n", gain_temps);
    Serial.printf("Gain energie : %.1f %%\n", gain_energie);

    /* --- Publication MQTT --- */
    if (mqttClient.connected()) {
        String metrics = "ASM,";
        metrics += String(temps_asm_us, 2) + ",";
        metrics += String(cpu_asm, 0) + ",";
        metrics += String(ram_asm, 0) + ",";
        metrics += String(energie_asm, 6) + ",";
        metrics += String(latence_asm, 2) + "|";
        metrics += "C,";
        metrics += String(temps_c_us, 2) + ",";
        metrics += String(cpu_c, 0) + ",";
        metrics += String(ram_c, 0) + ",";
        metrics += String(energie_c, 6) + ",";
        metrics += String(latence_c, 2) + "|";
        metrics += String(gain_temps, 2) + ",";
        metrics += String(gain_energie, 2);

        mqttClient.publish(MQTT_METRICS, metrics.c_str());
        Serial.println("Metriques publiees");
    }
}

/* ============================================================
 * Capture et envoi
 * ============================================================ */
bool captureAndSend() {
    Serial.println("\nCapture...");

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        compteurEchecs++;
        return false;
    }

    String image_b64 = base64::encode(fb->buf, fb->len);
    esp_camera_fb_return(fb);

    unsigned long t0 = micros();
    String signature = computeHMAC(image_b64);
    unsigned long t1 = micros();

    uint8_t sig_bytes[32];
    for (int i = 0; i < 32; i++) {
        sig_bytes[i] = strtol(signature.substring(i*2, i*2+2).c_str(), NULL, 16);
    }

    unsigned long t2 = micros();
    xor_cipher(sig_bytes, XOR_KEY, 32);
    unsigned long t3 = micros();

    float hmac_ms = (t1 - t0) / 1000.0;
    unsigned long xor_us = t3 - t2;

    Serial.printf("Image   : %u octets\n", fb->len);
    Serial.printf("HMAC    : %.2f ms\n", hmac_ms);
    Serial.printf("XOR ASM : %lu us\n", xor_us);

    String payload = image_b64 + "|" + signature;

    if (!mqttClient.connected()) reconnectMQTT();
    if (!mqttClient.connected()) {
        compteurEchecs++;
        return false;
    }

    bool ok = mqttClient.publish(MQTT_TOPIC, payload.c_str());
    if (ok) {
        compteurMessages++;
        Serial.printf("Publie  : OK (%u octets)\n", payload.length());
    } else {
        compteurEchecs++;
        Serial.println("Publie  : ECHEC");
    }

    return ok;
}

/* ============================================================
 * Loop
 * ============================================================ */
void loop() {
    unsigned long now = millis();

    if (WiFi.status() != WL_CONNECTED) {
        if (now - lastReconnect > 30000) {
            reconnectWiFi();
            lastReconnect = now;
        }
    }

    if (!mqttClient.connected()) {
        if (now - lastReconnect > 5000) {
            reconnectMQTT();
            lastReconnect = now;
        }
    } else {
        mqttClient.loop();
    }

    if (now - lastCapture >= CAPTURE_INTERVAL_MS) {
        lastCapture = now;
        captureAndSend();
        publierMetriques();
    }

    delay(100);
}
