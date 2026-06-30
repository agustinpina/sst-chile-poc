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
# Pipeline regional (en orden obligatorio)
python 01_download.py --test   # descarga 2023-2024 (~46 MB, valida sin esperar horas)
python 01_download.py          # descarga completa 1993 → dic 2025 (varios GB)
python 02_process.py           # genera CSVs desde los NetCDFs del run actual
python 03_visualize.py         # genera 5 PNGs desde los CSVs/NetCDFs del run actual

# Chequeo por centro de cultivo
python run_centro.py --lat -42.6256807 --lon -73.0538369 --name centro_ancud
# Salidas en output/<name>/: NetCDF, CSV mensual, 3 PNGs, resumen en consola

# Verificar dependencias
python -c "import copernicusmarine, xarray, cartopy, scipy; print('ok')"
```

## Arquitectura y flujo de datos

`config.py` es la única fuente de verdad para rutas, regiones y dataset ID. **Nunca redefinir constantes fuera de `config.py`.**

`RUN_ID = "YYYY-MM"` (mes actual) determina todas las rutas. Cada run es inmutable: si `data/runs/{RUN_ID}/` ya contiene NetCDFs, `01_download.py` aborta en lugar de sobreescribir. Para regenerar un run: `rm -rf data/runs/{RUN_ID} figures/runs/{RUN_ID}`.

Flujo de datos — pipeline regional:
```
Copernicus API → [01_download.py] → data/runs/{RUN_ID}/*_sst.nc
                                              ↓
                               [02_process.py] → sst_monthly_*.csv
                                                  sst_annual_*.csv
                                              ↓
                               [03_visualize.py] → figures/runs/{RUN_ID}/fig1_serie_anual.png
                                                    figures/runs/{RUN_ID}/fig2_ciclo_estacional.png
                                                    figures/runs/{RUN_ID}/fig3_mapa_{region}.png (×3)
```

Flujo de datos — chequeo por centro:
```
Copernicus API → [run_centro.py] → output/<name>/centro_<name>_sst.nc
                                              ↓
                                   centro_monthly_<name>.csv
                                   anom_serie.png / anom_heatmap.png / anom_anual.png
                                   resumen térmico en consola
```

Todos los datos generados (`data/`, `figures/`, `output/`) están en `.gitignore` y se producen localmente.

## Datos importantes

- **Dataset Copernicus:** `METOFFICE-GLO-SST-L4-REP-OBS-SST` (versión `202003`). El ID del PROMPT original era un ID legacy incorrecto (`SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`).
- **Cobertura temporal del dataset:** 1981-10-01 → 2025-12-18. No tiene datos en 2026 (es un producto reprocessado, no NRT). `FECHA_FIN` en `config.py` calcula el mes anterior a hoy, pero el dataset no llega más allá de dic 2025.
- **Variable:** `analysed_sst` en Kelvin → restar 273.15 para Celsius.
- **Regiones** en `config.py` — límites oficiales de cada región administrativa chilena:
  - `los_lagos`: lat [-44.05, -40.22], lon [-74.82, -71.57]
  - `aysen`: lat [-49.27, -43.63], lon [-75.50, -71.10]
  - `magallanes`: lat [-56.50, -48.60], lon [-75.67, -70.00] (recortado a -70°W para excluir Argentina)
- Los datos y figuras **no se commitean** (están en `.gitignore`). Cada usuario los genera localmente.
- El título de los mapas (fig3) se deriva de las fechas reales del NetCDF, no de `FECHA_FIN`.

## Agent skills

### Issue tracker

Issues are tracked as GitHub issues in `agustinpina/sst-chile-poc` via the `gh` CLI; external PRs are also a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` + `docs/adr/` at repo root). See `docs/agents/domain.md`.
