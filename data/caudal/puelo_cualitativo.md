# Caudal fluvial Río Puelo — datos cualitativos (API DGA no disponible)

Fuente: bibliografía (León-Muñoz et al. 2018 Sci Rep; Mardones et al. 2021;
Díaz et al. 2023 Sci Total Environ). Los datos cuantitativos de caudal mensual
requieren acceso a la API DGA/BNA (https://snia.dga.cl).

## Veranos clave para el análisis FAN

| Verano | Condición caudal Puelo | Contexto |
|--------|------------------------|---------|
| 2015-16 | **Bajo** (sequía + El Niño fuerte) | Precede crisis Pseudochattonella feb-mar 2016 |
| 2020-21 | **Bajo** (2° sequía más severa en 70 años) | Precede evento Heterosigma Comau mar-abr 2021 |
| 2025-26 | Por determinar (monitorear vía DGA) | Aviso El Niño emitido jun-2026 |

## Mecanismo relevante

Bajo caudal → menor aporte de agua dulce → debilitamiento de la capa de mezcla
superficial → mayor estratificación → retención prolongada de fitoplancton
→ condiciones favorables para FAN de baja biomasa pero alta toxicidad
(Pseudochattonella, Heterosigma).

## Fuente de datos recomendada

Para incorporar datos cuantitativos mensuales:
- Estación DGA Río Puelo en Puelo (código BNA 8420001-0)
- API: https://snia.dga.cl/BnaExportV2/exportacion/fluviometria/8420001-0
- Alternativa: CAMELS-CL dataset (Alvarez-Garreton et al. 2018) — datos históricos
  mensuales de cuencas chilenas disponibles en CAMELS.

Ejecutar `python run_caudal.py` cuando la API DGA esté disponible para
reemplazar este archivo por datos reales.
