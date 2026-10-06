"""
rapport_metriques.py
Capture les métriques ASM vs C depuis MQTT et génère un rapport comparatif.
"""

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
from pathlib import Path

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "iot/metrics"

OUTPUT_DIR = Path("rapport_data")
OUTPUT_DIR.mkdir(exist_ok=True)

# Stockage des mesures
mesures = []

def parse_metrics(payload):
    """Décode le message de métriques publié par l'ESP32."""
    try:
        parties = payload.split("|")
        asm_data = parties[0].split(",")
        c_data = parties[1].split(",")
        gains = parties[2].split(",")

        return {
            "asm": {
                "temps_us": float(asm_data[1]),
                "cpu_cycles": float(asm_data[2]),
                "ram_octets": float(asm_data[3]),
                "energie_mj": float(asm_data[4]),
                "latence_us": float(asm_data[5]),
            },
            "c": {
                "temps_us": float(c_data[1]),
                "cpu_cycles": float(c_data[2]),
                "ram_octets": float(c_data[3]),
                "energie_mj": float(c_data[4]),
                "latence_us": float(c_data[5]),
            },
            "gains": {
                "temps_pourcent": float(gains[0]),
                "energie_pourcent": float(gains[1]),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Erreur parsing : {e}")
        return None

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    data = parse_metrics(payload)
    if data:
        mesures.append(data)
        print(f"[{len(mesures):3d}] ASM: {data['asm']['temps_us']:.1f} µs | "
              f"C: {data['c']['temps_us']:.1f} µs | "
              f"Gain: {data['gains']['temps_pourcent']:.1f}%")

def capturer(duree_secondes=120):
    """Capture les métriques pendant X secondes."""
    print(f"Capture des métriques pendant {duree_secondes} secondes...")
    print(f"Broker : {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Topic  : {MQTT_TOPIC}")
    print("-" * 70)

    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)

    debut = time.time()
    while time.time() - debut < duree_secondes:
        client.loop(timeout=1.0)

    client.disconnect()
    print("-" * 70)
    print(f"Capture terminée : {len(mesures)} mesures")

    # Sauvegarde brute
    with open(OUTPUT_DIR / "mesures_brutes.json", "w", encoding="utf-8") as f:
        json.dump(mesures, f, indent=2, ensure_ascii=False)

    return mesures

def moyenne(valeurs):
    return sum(valeurs) / len(valeurs) if valeurs else 0

def generer_rapport():
    """Génère le rapport comparatif."""
    if not mesures:
        print("Aucune mesure disponible.")
        return

    # Extraire toutes les valeurs
    asm_temps = [m["asm"]["temps_us"] for m in mesures]
    asm_cpu = [m["asm"]["cpu_cycles"] for m in mesures]
    asm_ram = [m["asm"]["ram_octets"] for m in mesures]
    asm_energie = [m["asm"]["energie_mj"] for m in mesures]
    asm_latence = [m["asm"]["latence_us"] for m in mesures]

    c_temps = [m["c"]["temps_us"] for m in mesures]
    c_cpu = [m["c"]["cpu_cycles"] for m in mesures]
    c_ram = [m["c"]["ram_octets"] for m in mesures]
    c_energie = [m["c"]["energie_mj"] for m in mesures]
    c_latence = [m["c"]["latence_us"] for m in mesures]

    gains_temps = [m["gains"]["temps_pourcent"] for m in mesures]
    gains_energie = [m["gains"]["energie_pourcent"] for m in mesures]

    # Générer le rapport
    rapport = []
    rapport.append("# Comparaison ASM vs C — Mesures réelles\n")
    rapport.append(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
    rapport.append(f"Nombre de mesures : {len(mesures)}\n")
    rapport.append("")

    rapport.append("## 1. Temps de traitement (µs)\n")
    rapport.append("| Version | Min | Moyenne | Max |")
    rapport.append("|---------|-----|---------|-----|")
    rapport.append(f"| **ASM** | {min(asm_temps):.2f} | {moyenne(asm_temps):.2f} | {max(asm_temps):.2f} |")
    rapport.append(f"| **C**   | {min(c_temps):.2f} | {moyenne(c_temps):.2f} | {max(c_temps):.2f} |")
    rapport.append("")
    rapport.append(f"**Gain moyen ASM vs C : {moyenne(gains_temps):.1f}%**\n")

    rapport.append("## 2. Consommation CPU (cycles)\n")
    rapport.append("| Version | Min | Moyenne | Max |")
    rapport.append("|---------|-----|---------|-----|")
    rapport.append(f"| **ASM** | {min(asm_cpu):.0f} | {moyenne(asm_cpu):.0f} | {max(asm_cpu):.0f} |")
    rapport.append(f"| **C**   | {min(c_cpu):.0f} | {moyenne(c_cpu):.0f} | {max(c_cpu):.0f} |")
    rapport.append("")

    rapport.append("## 3. Consommation RAM (octets)\n")
    rapport.append("| Version | Min | Moyenne | Max |")
    rapport.append("|---------|-----|---------|-----|")
    rapport.append(f"| **ASM** | {min(asm_ram):.0f} | {moyenne(asm_ram):.0f} | {max(asm_ram):.0f} |")
    rapport.append(f"| **C**   | {min(c_ram):.0f} | {moyenne(c_ram):.0f} | {max(c_ram):.0f} |")
    rapport.append("")

    rapport.append("## 4. Énergie consommée (mJ)\n")
    rapport.append("| Version | Min | Moyenne | Max |")
    rapport.append("|---------|-----|---------|-----|")
    rapport.append(f"| **ASM** | {min(asm_energie):.6f} | {moyenne(asm_energie):.6f} | {max(asm_energie):.6f} |")
    rapport.append(f"| **C**   | {min(c_energie):.6f} | {moyenne(c_energie):.6f} | {max(c_energie):.6f} |")
    rapport.append("")
    rapport.append(f"**Gain moyen énergie ASM vs C : {moyenne(gains_energie):.1f}%**\n")

    rapport.append("## 5. Latence (µs)\n")
    rapport.append("| Version | Min | Moyenne | Max |")
    rapport.append("|---------|-----|---------|-----|")
    rapport.append(f"| **ASM** | {min(asm_latence):.2f} | {moyenne(asm_latence):.2f} | {max(asm_latence):.2f} |")
    rapport.append(f"| **C**   | {min(c_latence):.2f} | {moyenne(c_latence):.2f} | {max(c_latence):.2f} |")
    rapport.append("")

    rapport.append("## 6. Synthèse\n")
    rapport.append(f"L'implémentation en assembleur Xtensa réduit :")
    rapport.append(f"- le temps de traitement de **{moyenne(gains_temps):.1f}%**")
    rapport.append(f"- la consommation CPU d'environ **{moyenne(gains_temps):.1f}%**")
    rapport.append(f"- la consommation d'énergie de **{moyenne(gains_energie):.1f}%**")
    rapport.append(f"- la latence d'environ **{moyenne(gains_temps):.1f}%**")

    contenu = "\n".join(rapport)

    # Sauvegarder
    with open(OUTPUT_DIR / "RAPPORT_COMPARATIF.md", "w", encoding="utf-8") as f:
        f.write(contenu)

    print("\n" + "=" * 70)
    print("RAPPORT GÉNÉRÉ")
    print("=" * 70)
    print(contenu)
    print("=" * 70)
    print(f"Sauvegardé dans : {OUTPUT_DIR / 'RAPPORT_COMPARATIF.md'}")

if __name__ == "__main__":
    import sys
    duree = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    capturer(duree)
    generer_rapport()