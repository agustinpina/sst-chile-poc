# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

```bash
source .venv/bin/activate   # siempre activar antes de ejecutar cualquier script
```

Python 3.11.9 vía pyenv (`.python-version` fija la versión). El venv tiene su propio kernel Jupyter registrado como `sst-chile-poc`.

Credenciales requeridas (no se commitean, no hay `.env`):
```bash
export COPERNICUSMARINE_SERVICE_USERNAME="..."
export COPERNICUSMARINE_SERVICE_PASSWORD="..."
```

## Comandos principales

```bash
# Pipeline completo (en orden obligatorio)
python 01_download.py --test   # descarga 2023-2024 (~8 MB, valida sin esperar horas)
python 01_download.py          # descarga completa 1993 → mes anterior (varios GB)
python 02_process.py           # genera CSVs desde los NetCDFs del run actual
python 03_visualize.py         # genera 3 PNGs desde los CSVs del run actual

# Notebook
jupyter notebook explore.ipynb

# Verificar dependencias
python -c "import copernicusmarine, xarray, cartopy, scipy; print('ok')"
```

## Arquitectura y flujo de datos

`config.py` se importa en los tres scripts — es la única fuente de verdad para rutas, regiones y el dataset ID. **Nunca redefinir constantes fuera de `config.py`.**

`RUN_ID = "YYYY-MM"` (mes actual) determina todas las rutas. Cada run es inmutable: si `data/runs/{RUN_ID}/` ya contiene NetCDFs, `01_download.py` aborta en lugar de sobreescribir. Para regenerar un run, borrar la carpeta.

Flujo de datos:
```
Copernicus API → [01_download.py] → data/runs/{RUN_ID}/*_sst.nc
                                              ↓
                               [02_process.py] → sst_monthly_*.csv
                                                  sst_annual_*.csv
                                              ↓
                               [03_visualize.py] → figures/runs/{RUN_ID}/*.png
```

`explore.ipynb` es de solo lectura sobre datos existentes — lee directamente los NetCDFs del run más reciente en `data/runs/`. No duplica lógica de los scripts.

## Datos importantes

- **Dataset Copernicus:** `METOFFICE-GLO-SST-L4-REP-OBS-SST` (versión `202003`). El PROMPT original usaba un ID legacy incorrecto (`SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`).
- **Variable:** `analysed_sst` en Kelvin → restar 273.15 para Celsius.
- **Regiones** en `config.py`: `los_lagos`, `aysen`, `magallanes` con bounding boxes lat/lon.
- Los datos/figuras **sí se commitean** al repo (la GitHub Action los publica automáticamente cada trimestre).

## GitHub Action

`.github/workflows/update_sst.yml` corre el pipeline completo el día 1 de cada trimestre (ene/abr/jul/oct, 06:00 UTC). Lee credenciales desde GitHub Secrets `COPERNICUSMARINE_SERVICE_USERNAME` / `COPERNICUSMARINE_SERVICE_PASSWORD`. Solo hace commit si hay cambios nuevos.
