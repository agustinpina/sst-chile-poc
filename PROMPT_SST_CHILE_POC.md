# PROMPT: sst-chile-poc
> Instrucciones completas para Claude Code — proyecto de análisis de SST en zonas salmonicultoras de Chile

---

## Descripción general

Construir un proyecto Python llamado `sst-chile-poc` que analice la temperatura superficial del mar (SST) en las regiones salmonicultoras de Chile usando datos satelitales de Copernicus Marine Service.

El proyecto debe ser **actualizable**: cada vez que se ejecuta genera una carpeta con el período correspondiente y no sobreescribe runs anteriores. Incluye automatización trimestral vía GitHub Actions y un notebook de exploración interactiva.

---

## Contexto de datos

- **Producto:** OSTIA SST L4 (`METOFFICE-GLO-SST-L4-REP-OBS-SST`, versión `202003`)
  - ⚠️ El ID legacy `SST_GLO_SST_L4_REP_OBSERVATIONS_010_011` ya no existe en el catálogo.
- **Variable:** `analysed_sst` (convertir de Kelvin a Celsius: restar 273.15)
- **Cobertura del dataset:** 1981-10-01 → 2025-12-18 (producto reprocessado, no NRT)
- **Período de descarga:** `1993-01-01` hasta `2025-12-18` como máximo
- **Resolución:** 0.05° (~5.5 km), 1 dato por día

---

## Regiones de interés

Definir en `config.py` como diccionario, usando los límites oficiales de cada región administrativa chilena:

```python
REGIONES = {
    # Límites oficiales de cada región administrativa
    # Conversión de grados°minutos' a decimal: dd + mm/60
    "los_lagos":  {"lat": [-44.05, -40.22], "lon": [-74.82, -71.57]},  # 40°13'–44°03' S, 74°49'–71°34' W
    "aysen":      {"lat": [-49.27, -43.63], "lon": [-75.50, -71.10]},  # 43°38'–49°16' S, hasta el Pacífico
    "magallanes": {"lat": [-56.50, -48.60], "lon": [-75.67, -70.00]},  # 48°36'–56°30' S, costa chilena hasta ~70°W
}
```

---

## Estructura de archivos

```
sst-chile-poc/
├── PROMPT_SST_CHILE_POC.md     ← este archivo
├── CLAUDE.md                   ← guía para Claude Code
├── config.py
├── 01_download.py
├── 02_process.py
├── 03_visualize.py
├── explore.ipynb
├── requirements.txt
├── README.md
├── .github/
│   └── workflows/
│       └── update_sst.yml
├── data/
│   └── runs/
│       └── {run_id}/           ← ej: 2026-05
│           ├── los_lagos_sst.nc
│           ├── aysen_sst.nc
│           ├── magallanes_sst.nc
│           └── run_log.txt
└── figures/
    └── runs/
        └── {run_id}/
            ├── fig1_serie_anual.png
            ├── fig2_ciclo_estacional.png
            ├── fig3_mapa_los_lagos.png
            ├── fig3_mapa_aysen.png
            └── fig3_mapa_magallanes.png
```

---

## config.py

- `FECHA_INICIO` fija: `"1993-01-01"`
- `FECHA_FIN` dinámica: último día del mes anterior a hoy
  (si hoy es 10 mayo 2026 → `FECHA_FIN = "2026-04-30"`, pero el dataset REP solo llega a `2025-12-18`)
- `RUN_ID = f"{año_actual}-{mes_actual:02d}"` → `"2026-05"`
- `DATA_DIR  = Path(f"data/runs/{RUN_ID}/")`
- `FIGURES_DIR = Path(f"figures/runs/{RUN_ID}/")`
- Crear ambos directorios con `pathlib .mkdir(parents=True, exist_ok=True)`
- `DATASET_ID = "METOFFICE-GLO-SST-L4-REP-OBS-SST"`
- `VARIABLE = "analysed_sst"`
- `FRECUENCIA_RECOMENDADA = "trimestral (Q1/Q2/Q3/Q4)"`

---

## 01_download.py

- Usar `copernicusmarine.subset()` con parámetros desde `config.py`
- Una descarga por región → `data/runs/{run_id}/{region}_sst.nc`
- Credenciales via variables de entorno:
  - `COPERNICUSMARINE_SERVICE_USERNAME`
  - `COPERNICUSMARINE_SERVICE_PASSWORD`
- Antes de descargar: verificar si ya existe `data/runs/{run_id}/`
  - Si existe: print advertencia y abortar (no sobreescribir)
  - Si no existe: proceder
- Al finalizar, escribir `data/runs/{run_id}/run_log.txt` con:
  - Fecha y hora de ejecución
  - Período descargado (`FECHA_INICIO` → `FECHA_FIN`)
  - Tamaño de cada archivo `.nc` descargado
  - Versión del producto Copernicus usado
- Manejo de errores con `try/except`, mensajes claros en consola
- Flag opcional `--test` que descarga solo 2023–2024 para validar el pipeline sin descargar la serie completa

---

## 02_process.py

- Cargar cada NetCDF con `xarray` desde `data/runs/{run_id}/`
- Convertir Kelvin → Celsius (`analysed_sst - 273.15`)
- Calcular media mensual espacial (promedio sobre lat/lon)
- Calcular media anual
- Exportar:
  - `data/runs/{run_id}/sst_monthly_{region}.csv`
  - `data/runs/{run_id}/sst_annual_{region}.csv`
- Agregar columna `"region"` en cada CSV para facilitar concat posterior
- Print de progreso por región

---

## 03_visualize.py

Generar 5 figuras en `figures/runs/{run_id}/` a 150 dpi:

### Fig 1 — Serie temporal anual (1993 → último año disponible)
- Una línea por región, colores diferenciados, leyenda
- Línea de tendencia lineal (`scipy.stats.linregress`) por región
- Anotar pendiente en la leyenda: `"+X.XX °C/década"`
- Título dinámico basado en años reales de los datos

### Fig 2 — Ciclo estacional (climatología mensual)
- Media mensual por región (promedio todos los años)
- Banda sombreada ±1 SD
- Eje X: meses (Ene–Dic), eje Y: °C
- Título: `"Ciclo estacional SST – zonas salmonicultoras Chile"`

### Fig 3 — Mapa SST promedio por región (3 archivos separados)
- **Un PNG por región**: `fig3_mapa_los_lagos.png`, `fig3_mapa_aysen.png`, `fig3_mapa_magallanes.png`
- Promedio de todo el período disponible en el NetCDF
- **Título derivado de las fechas reales del NetCDF** (no de `FECHA_FIN`):
  `f"SST media {anio_inicio_datos}–{anio_fin_datos}\n{nombre}"`
- Colormap: `'RdYlBu_r'`, rango 8–18°C
- Coastline, land feature en gris, gridlines con etiquetas, colorbar integrada
- Cartopy `PlateCarree`, figsize=(8, 7)

---

## Notebook de exploración: explore.ipynb

Notebook Jupyter con las siguientes secciones:

### Celda 0 — Setup
- Importar desde `config.py`:
  ```python
  from config import DATA_DIR, FIGURES_DIR, REGIONES, FECHA_FIN, RUN_ID
  ```
- Imports: `xarray`, `pandas`, `matplotlib`, `pathlib`

### Celda 1 — Selección de run
- Listar automáticamente los runs disponibles en `data/runs/`
- Cargar el más reciente por defecto

### Celda 2 — Inspección del NetCDF
- Cargar los 3 archivos `.nc` del run seleccionado
- Mostrar: dimensiones, rango de fechas, valores min/max/mean, NaN por región

### Celda 3 — Visualización rápida de serie temporal
- Plot SST media mensual por región (sin formato final)

### Celda 4 — Exploración de anomalías
- Climatología baseline 1993–2010
- Identificar meses con anomalía > +2°C o < -2°C
- Tabla y plot

### Celda 5 — Sandbox libre
```python
# Espacio libre para exploración ad-hoc
```

---

## GitHub Action: .github/workflows/update_sst.yml

### Trigger
```yaml
schedule:
  - cron: "0 6 1 1,4,7,10 *"   # trimestral: 1 ene, 1 abr, 1 jul, 1 oct — 06:00 UTC
workflow_dispatch:
```

### Job: update-sst
- `runs-on: ubuntu-latest`
- Steps: checkout → Python 3.11 → pip cache → install → pipeline → commit+push condicional
- Git user: `"github-actions[bot]"`
- Mensaje: `"chore: SST update run {run_id} – {fecha_hoy}"`
- Solo commitear si hay cambios (`git diff --staged --quiet`)

### Secrets requeridos
- `COPERNICUSMARINE_SERVICE_USERNAME`
- `COPERNICUSMARINE_SERVICE_PASSWORD`

---

## Requirements.txt

```
copernicusmarine>=1.3
xarray>=2024.1
netCDF4>=1.6
numpy>=1.26
pandas>=2.1
matplotlib>=3.8
cartopy>=0.22
scipy>=1.12
jupyter>=1.0
```

---

## Requisitos técnicos generales

- Python 3.11+
- Comentarios en español
- Variables en español
- Print statements de progreso en consola
- Solo scripts `.py` ejecutables desde terminal (excepto `explore.ipynb`)
- Manejo de errores con `try/except` en descarga y carga de archivos
- Flag `--test` en `01_download.py` para validar pipeline con 2 años (2023–2024)
