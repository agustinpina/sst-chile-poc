# PROMPT: sst-chile-poc
> Instrucciones completas para Claude Code — proyecto de análisis de SST en zonas salmonicultoras de Chile

---

## Descripción general

Construir un proyecto Python llamado `sst-chile-poc` que analice la temperatura superficial del mar (SST) en las regiones salmonicultoras de Chile usando datos satelitales de Copernicus Marine Service.

El proyecto debe ser **actualizable**: cada vez que se ejecuta genera una carpeta con el período correspondiente y no sobreescribe runs anteriores. Incluye automatización trimestral vía GitHub Actions y un notebook de exploración interactiva.

---

## Contexto de datos

- **Producto:** OSTIA SST L4 (`SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`)
- **Variable:** `analysed_sst` (convertir de Kelvin a Celsius)
- **Período:** `1993-01-01` hasta el último día del mes anterior a hoy (dinámico)
- **Resolución:** 0.05° (~5 km)

---

## Regiones de interés

Definir en `config.py` como diccionario:

```python
REGIONES = {
    "los_lagos":  {"lat": [-42.5, -41.0], "lon": [-73.5, -72.0]},
    "aysen":      {"lat": [-45.5, -43.5], "lon": [-74.5, -72.5]},
    "magallanes": {"lat": [-53.0, -50.0], "lon": [-74.5, -71.5]},
}
```

---

## Estructura de archivos

```
sst-chile-poc/
├── PROMPT_SST_CHILE_POC.md     ← este archivo
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
        └── {run_id}/           ← mismo run_id
            ├── fig1_serie_anual.png
            ├── fig2_ciclo_estacional.png
            └── fig3_mapa_promedio.png
```

---

## config.py

- `FECHA_INICIO` fija: `"1993-01-01"`
- `FECHA_FIN` dinámica: último día del mes anterior a hoy
  (si hoy es 9 mayo 2026 → `FECHA_FIN = "2026-04-30"`)
- `RUN_ID = f"{año_actual}-{mes_actual:02d}"` → `"2026-05"`
- `DATA_DIR  = Path(f"data/runs/{RUN_ID}/")`
- `FIGURES_DIR = Path(f"figures/runs/{RUN_ID}/")`
- Crear ambos directorios con `pathlib .mkdir(parents=True, exist_ok=True)`
- `DATASET_ID = "SST_GLO_SST_L4_REP_OBSERVATIONS_010_011"`
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
- Flag opcional `--test` que descarga solo 2 años (2023–2024) para validar el pipeline sin descargar la serie completa

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

Generar 3 figuras en `figures/runs/{run_id}/` a 150 dpi:

### Fig 1 — Serie temporal anual (1993 → FECHA_FIN)
- Una línea por región, colores diferenciados, leyenda
- Línea de tendencia lineal (`scipy.stats.linregress`) por región
- Anotar pendiente en la leyenda: `"+X.XX °C/década"`
- Título dinámico: `f"SST media anual – zonas salmonicultoras Chile (1993–{año_fin})"`

### Fig 2 — Ciclo estacional (climatología mensual)
- Media mensual por región (promedio todos los años)
- Banda sombreada ±1 SD
- Eje X: meses (Ene–Dic), eje Y: °C
- Título: `"Ciclo estacional SST – zonas salmonicultoras Chile"`

### Fig 3 — Mapa SST promedio (últimos 5 años desde FECHA_FIN)
- Un panel por región usando Cartopy
- Colormap: `'RdYlBu_r'`, rango 8–18°C
- Coastline, gridlines, colorbar
- Título dinámico: `f"SST media {año_fin-4}–{año_fin} por zona"`

---

## Notebook de exploración: explore.ipynb

Crear un notebook Jupyter con las siguientes secciones como celdas markdown + código:

### Celda 0 — Setup
- Importar desde `config.py` (no redefinir constantes):
  ```python
  from config import DATA_DIR, FIGURES_DIR, REGIONES, FECHA_FIN, RUN_ID
  ```
- Imports estándar: `xarray`, `pandas`, `matplotlib`, `pathlib`

### Celda 1 — Selección de run
- Listar automáticamente los runs disponibles en `data/runs/`
- Cargar el más reciente por defecto:
  ```python
  runs_disponibles = sorted(Path("data/runs/").iterdir())
  run_a_explorar = runs_disponibles[-1]
  ```

### Celda 2 — Inspección del NetCDF
- Cargar los 3 archivos `.nc` del run seleccionado
- Mostrar: dimensiones, coordenadas, rango de fechas, valores min/max/mean
- Identificar valores faltantes (NaN) por región

### Celda 3 — Visualización rápida de serie temporal
- Plot interactivo de SST media mensual por región
- Sin formato final, solo para exploración rápida

### Celda 4 — Exploración de anomalías
- Calcular anomalía respecto a climatología (1993–2010 como baseline)
- Identificar meses con anomalía > +2°C o < -2°C
- Mostrar como tabla y como plot

### Celda 5 — Sandbox libre
```python
# Espacio libre para exploración ad-hoc
```

### Instrucciones importantes para el notebook
- No duplicar lógica de los scripts: siempre importar desde `config.py`
- No guardar outputs dentro del `.ipynb`
- Agregar al `.gitignore`: outputs de celdas se limpian antes de commit
- Agregar en README sección "Exploración interactiva":
  `"Usar explore.ipynb para análisis ad-hoc. Ejecutar: jupyter notebook explore.ipynb"`

---

## GitHub Action: .github/workflows/update_sst.yml

### Trigger
```yaml
schedule:
  - cron: "0 6 1 1,4,7,10 *"   # trimestral: 1 ene, 1 abr, 1 jul, 1 oct — 06:00 UTC
workflow_dispatch:               # permite correrlo manualmente desde GitHub UI
```

### Job: update-sst
- `runs-on: ubuntu-latest`

**Steps:**

1. Checkout del repo (`actions/checkout@v4`) con `fetch-depth: 0`
2. Setup Python 3.11 (`actions/setup-python@v5`)
3. Cache de pip (`actions/cache@v4`)
   - key: `pip-${{ hashFiles('requirements.txt') }}`
4. Instalar dependencias: `pip install -r requirements.txt`
5. Correr pipeline completo:
   ```bash
   python 01_download.py
   python 02_process.py
   python 03_visualize.py
   ```
6. Commit y push automático:
   - Git user: `"github-actions[bot]"`
   - `git add data/runs/ figures/runs/`
   - Mensaje dinámico: `"chore: SST update run {run_id} – {fecha_hoy}"`
   - Push a branch `main`
   - Solo hacer commit si hay cambios (`git diff --quiet` check)

### Variables de entorno en el workflow
```yaml
env:
  COPERNICUSMARINE_SERVICE_USERNAME: ${{ secrets.COPERNICUSMARINE_SERVICE_USERNAME }}
  COPERNICUSMARINE_SERVICE_PASSWORD: ${{ secrets.COPERNICUSMARINE_SERVICE_PASSWORD }}
```

### Secrets requeridos
Documentar en README — configurar en: `GitHub repo → Settings → Secrets → Actions`:
- `COPERNICUSMARINE_SERVICE_USERNAME`
- `COPERNICUSMARINE_SERVICE_PASSWORD`

---

## README.md

Generar con las siguientes secciones:

- Descripción del proyecto (2–3 líneas)
- Estructura de carpetas
- Instalación y uso local:
  ```bash
  pip install -r requirements.txt
  export COPERNICUSMARINE_SERVICE_USERNAME="tu_usuario"
  export COPERNICUSMARINE_SERVICE_PASSWORD="tu_password"
  python 01_download.py --test   # validar pipeline
  python 01_download.py          # descarga completa
  python 02_process.py
  python 03_visualize.py
  ```
- Sección "Exploración interactiva": instrucciones para `explore.ipynb`
- Sección "GitHub Action": pasos para configurar secrets
- Frecuencia de actualización recomendada: **trimestral**
- Créditos: datos de [Copernicus Marine Service](https://marine.copernicus.eu/) — OSTIA SST L4

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
- Flag `--test` en `01_download.py` para validar pipeline con 2 años
