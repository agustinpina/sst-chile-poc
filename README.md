# SST en regiones salmonicultoras de Chile

Pipeline en Python que analiza la **temperatura superficial del mar (SST)** en las zonas salmonicultoras de Chile (Los Lagos, Aysén, Magallanes) usando datos satelitales OSTIA L4 de [Copernicus Marine Service](https://marine.copernicus.eu/).

Incluye un módulo separado para chequear la exposición térmica de un **centro de cultivo específico** a partir de sus coordenadas geográficas.

---

## Estructura

```
├── config.py          ← rutas, regiones, parámetros del producto Copernicus
├── 01_download.py     ← descarga NetCDFs por región (Copernicus API)
├── 02_process.py      ← agrega a series mensuales y anuales (CSV)
├── 03_visualize.py    ← genera figuras: series, ciclo estacional, mapas
├── run_centro.py      ← chequeo SST para un centro de cultivo (lat/lon)
├── mapviz.py          ← utilidad de cartografía (costa GSHHG)
└── requirements.txt
```

Los datos generados (`data/`, `figures/`, `output/`) se producen localmente y están en `.gitignore`.

---

## Instalación

```bash
git clone https://github.com/agustinpina/sst-chile-poc.git
cd sst-chile-poc
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**Credenciales Copernicus** (requeridas para descargar datos):

```bash
export COPERNICUSMARINE_SERVICE_USERNAME="tu_usuario"
export COPERNICUSMARINE_SERVICE_PASSWORD="tu_password"
```

Registrarse gratis en [marine.copernicus.eu](https://marine.copernicus.eu/). Alternativa: guardar credenciales de forma permanente con `copernicusmarine login`.

---

## Uso: pipeline regional

Analiza las tres regiones salmonicultoras (Los Lagos, Aysén, Magallanes) en secuencia:

```bash
# 1. Descargar datos de Copernicus (primera ejecución: varios GB; reutiliza si ya existen)
python 01_download.py --test   # prueba rápida con 2023-2024 (~46 MB)
python 01_download.py          # descarga completa 1993 → presente

# 2. Procesar: generar series mensuales y anuales (CSV)
python 02_process.py

# 3. Visualizar: generar figuras
python 03_visualize.py
```

**Salidas** en `data/runs/YYYY-MM/` y `figures/runs/YYYY-MM/`:
- `sst_monthly_{region}.csv` / `sst_annual_{region}.csv`
- `fig1_serie_anual.png` — serie histórica de SST media anual
- `fig2_ciclo_estacional.png` — ciclo estacional por región
- `fig3_mapa_{region}.png` — mapa de SST media del período

---

## Uso: chequeo por centro de cultivo

Para analizar la exposición térmica de un centro específico, proporciona sus coordenadas:

```bash
python run_centro.py --lat -42.6256807 --lon -73.0538369 --name centro_ancud
```

**Argumentos:**

| Argumento | Descripción | Default |
|-----------|-------------|---------|
| `--lat` | Latitud decimal (negativa = sur) | requerido |
| `--lon` | Longitud decimal (negativa = oeste) | requerido |
| `--name` | Nombre identificador del centro | derivado de lat/lon |
| `--baseline-start` | Año inicio climatología de referencia | 1993 |
| `--baseline-end` | Año fin climatología de referencia | 2020 |

**Salidas** en `output/<name>/`:
- `centro_<name>_sst.nc` — serie completa en NetCDF
- `centro_monthly_<name>.csv` — serie mensual con SST, climatología y anomalía
- `anom_serie.png` — anomalías mensuales con tendencia decenal
- `anom_heatmap.png` — mapa de calor mensual por año
- `anom_anual.png` — anomalía media por año

**Resumen en consola:**
```
📊 Resumen — centro_ancud
   Último dato:   2025-12  ·  12.4 °C
   Anomalía:      +1.1 °C  (vs climatología 1993-2020)
   Tendencia:     +0.18 °C/década
```

---

## Créditos

Datos satelitales: [Copernicus Marine Service](https://marine.copernicus.eu/) — producto OSTIA SST L4 (`METOFFICE-GLO-SST-L4-REP-OBS-SST`, versión `202003`). Cobertura: 1981-10-01 → 2025-12-18.
