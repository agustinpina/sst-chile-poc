"""
Configuración central del proyecto sst-chile-poc.

Define rutas, regiones, parámetros del producto Copernicus y el RUN_ID
dinámico que aísla cada ejecución en su propia carpeta.
"""
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Período de análisis
# ---------------------------------------------------------------------------
FECHA_INICIO = "1993-01-01"

# FECHA_FIN dinámica: último día del mes anterior a hoy
_hoy = date.today()
_primer_dia_mes_actual = _hoy.replace(day=1)
_ultimo_dia_mes_anterior = _primer_dia_mes_actual - timedelta(days=1)
FECHA_FIN = _ultimo_dia_mes_anterior.isoformat()  # ej: "2026-04-30"

# ---------------------------------------------------------------------------
# RUN_ID: identifica esta ejecución (no sobreescribe runs anteriores)
# ---------------------------------------------------------------------------
RUN_ID = f"{_hoy.year}-{_hoy.month:02d}"  # ej: "2026-05"

DATA_DIR = Path(f"data/runs/{RUN_ID}/")
FIGURES_DIR = Path(f"figures/runs/{RUN_ID}/")
DATA_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Producto Copernicus
# ---------------------------------------------------------------------------
DATASET_ID = "SST_GLO_SST_L4_REP_OBSERVATIONS_010_011"
VARIABLE = "analysed_sst"
FRECUENCIA_RECOMENDADA = "trimestral (Q1/Q2/Q3/Q4)"

# ---------------------------------------------------------------------------
# Regiones de interés (zonas salmonicultoras de Chile)
# ---------------------------------------------------------------------------
REGIONES = {
    "los_lagos":  {"lat": [-42.5, -41.0], "lon": [-73.5, -72.0]},
    "aysen":      {"lat": [-45.5, -43.5], "lon": [-74.5, -72.5]},
    "magallanes": {"lat": [-53.0, -50.0], "lon": [-74.5, -71.5]},
}
