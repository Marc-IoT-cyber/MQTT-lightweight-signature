# Comparaison ASM vs C — Mesures réelles

Date : 06/10/2026 08:59

Nombre de mesures : 8


## 1. Temps de traitement (µs)

| Version | Min | Moyenne | Max |
|---------|-----|---------|-----|
| **ASM** | 11.87 | 11.88 | 11.89 |
| **C**   | 20.47 | 20.47 | 20.48 |

**Gain moyen ASM vs C : 42.0%**

## 2. Consommation CPU (cycles)

| Version | Min | Moyenne | Max |
|---------|-----|---------|-----|
| **ASM** | 2848 | 2850 | 2853 |
| **C**   | 4912 | 4913 | 4914 |

## 3. Consommation RAM (octets)

| Version | Min | Moyenne | Max |
|---------|-----|---------|-----|
| **ASM** | 0 | 2684351616 | 4294965504 |
| **C**   | 0 | 0 | 0 |

## 4. Énergie consommée (mJ)

| Version | Min | Moyenne | Max |
|---------|-----|---------|-----|
| **ASM** | 0.001566 | 0.001567 | 0.001569 |
| **C**   | 0.002702 | 0.002702 | 0.002703 |

**Gain moyen énergie ASM vs C : 42.0%**

## 5. Latence (µs)

| Version | Min | Moyenne | Max |
|---------|-----|---------|-----|
| **ASM** | 11.87 | 11.88 | 11.89 |
| **C**   | 20.47 | 20.47 | 20.48 |

## 6. Synthèse

L'implémentation en assembleur Xtensa réduit :
- le temps de traitement de **42.0%**
- la consommation CPU d'environ **42.0%**
- la consommation d'énergie de **42.0%**
- la latence d'environ **42.0%**