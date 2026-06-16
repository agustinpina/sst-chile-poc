"""
run_caudal.py — Descarga caudal mensual del Río Puelo (DGA Chile) como proxy
del forzante de agua dulce del mar interior de Chiloé / Reloncaví.

El Río Puelo es la entrada de agua dulce dominante al Seno de Reloncaví
(principal cuerpo receptor del mar interior). Su caudal es el proxy más
directo del mecanismo de estratificación que se asocia con los episodios FAN
de 2016 (bajo caudal por sequía + El Niño) y 2021 (bajo caudal por sequía
a pesar de La Niña).

# ponytail: un solo río (Puelo), no una red hídrica. Proxy del mecanismo,
# no un balance hídrico. Si el caudal de Puelo no está disponible, el script
# cae a un modo cualitativo que describe la anomalía de precipitación de las
# temporadas históricas usando datos bibliográficos conocidos.

Fuente primaria: DGA Chile — API pública BNA/SNIA
  Estación Puelo en Puelo: código DGA 8420001-0
  Servicio: https://snia.dga.cl/BnaExportV2/exportacion/...
  (servicio frecuentemente inestable — se intenta con timeout corto)

Salida: data/caudal/puelo.csv (cols: time, caudal_m3s, fuente)
        data/caudal/puelo_cualitativo.md  (si falla la API)
Uso:    python run_caudal.py
"""
import sys
import urllib.request
import json
from pathlib import Path

import pandas as pd

CAUDAL_DIR = Path("data/caudal")
CAUDAL_CSV = CAUDAL_DIR / "puelo.csv"
CAUDAL_CUALITATIVO_MD = CAUDAL_DIR / "puelo_cualitativo.md"

# Estación DGA Río Puelo en Puelo (código BNA 8420001-0)
# ponytail: endpoint y código verificados jun-2026; DGA puede cambiar URLs sin aviso.
DGA_ESTACION = "8420001-0"
DGA_URL = (
    f"https://snia.dga.cl/BnaExportV2/exportacion/fluviometria/"
    f"{DGA_ESTACION}?fechaInicio=1993-01-01&tipoDato=medio"
)

# Texto cualitativo de respaldo basado en la literatura (León-Muñoz et al. 2018,
# Mardones et al. 2021, Díaz et al. 2023) para cuando la API DGA no responde.
TEXTO_CUALITATIVO = """\
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
"""


def intentar_dga():
    """Intenta descargar el caudal mensual desde la API DGA/BNA.
    Retorna DataFrame o None si falla."""
    print(f"→ Intentando API DGA (estación Puelo {DGA_ESTACION})...")
    try:
        req = urllib.request.Request(DGA_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"   ✗ API DGA no disponible: {exc}")
        return None

    # La estructura exacta del JSON de DGA puede variar; intentamos el formato común
    try:
        registros = data.get("data", data) if isinstance(data, dict) else data
        filas = []
        for r in registros:
            fecha = r.get("fecha") or r.get("date") or r.get("Fecha")
            valor = r.get("valor") or r.get("value") or r.get("Valor")
            if fecha and valor is not None:
                filas.append({"time": pd.to_datetime(fecha), "caudal_m3s": float(valor)})
        if not filas:
            print("   ✗ Respuesta DGA no contiene filas reconocibles.")
            return None
        df = pd.DataFrame(filas).sort_values("time").reset_index(drop=True)
        df = df.set_index("time").resample("1MS").mean().reset_index()
        df["fuente"] = "DGA BNA estación 8420001-0"
        return df
    except Exception as exc:
        print(f"   ✗ Error parseando respuesta DGA: {exc}")
        return None


def main():
    CAUDAL_DIR.mkdir(parents=True, exist_ok=True)

    if CAUDAL_CSV.exists():
        print(f"   ↪ Ya existe {CAUDAL_CSV}, se reutiliza.")
        return pd.read_csv(CAUDAL_CSV, parse_dates=["time"])

    df = intentar_dga()

    if df is not None:
        df.to_csv(CAUDAL_CSV, index=False)
        print(f"   ✓ {CAUDAL_CSV} ({len(df)} meses, "
              f"{df['time'].min():%Y-%m} → {df['time'].max():%Y-%m})")
        return df
    else:
        # Fallback: guardar nota cualitativa y avisar
        CAUDAL_CUALITATIVO_MD.write_text(TEXTO_CUALITATIVO, encoding="utf-8")
        print(f"   ⚠️  API DGA no respondió. Se guardó nota cualitativa en {CAUDAL_CUALITATIVO_MD}")
        print("   ℹ️  El análisis de convergencia usará 'sin datos' para caudal.")
        return None


if __name__ == "__main__":
    resultado = main()
    if resultado is not None:
        print(resultado.tail(12).to_string(index=False))
        # Self-check básico: la serie debe tener datos en 2015-16 y 2020-21
        for año, mes in [(2016, 2), (2021, 3)]:
            fila = resultado[(resultado["time"].dt.year == año) &
                             (resultado["time"].dt.month == mes)]
            assert not fila.empty, f"Falta {año}-{mes:02d} en la serie de caudal"
        print("✅ Self-check caudal ok")
    else:
        print(f"ℹ️  Ver {CAUDAL_CUALITATIVO_MD} para contexto cualitativo.")
