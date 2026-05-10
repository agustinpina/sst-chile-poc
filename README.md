# sst-chile-poc

POC en Python que analiza la temperatura superficial del mar (SST) en las
zonas salmonicultoras de Chile (Los Lagos, Aysén, Magallanes) usando datos
satelitales OSTIA L4 de [Copernicus Marine Service](https://marine.copernicus.eu/).
Se ejecuta de forma reproducible: cada run queda aislado por `RUN_ID = YYYY-MM`.

## Estructura

```
sst-chile-poc/
├── config.py                ← rutas, regiones, RUN_ID dinámico
├── 01_download.py           ← descarga Copernicus por región
├── 02_process.py            ← agregación mensual/anual
├── 03_visualize.py          ← 3 figuras (series, ciclo, mapa)
├── explore.ipynb            ← notebook de exploración ad-hoc
├── requirements.txt
├── .github/workflows/update_sst.yml   ← cron trimestral
├── data/runs/{run_id}/      ← NetCDFs + CSVs + run_log.txt
└── figures/runs/{run_id}/   ← PNGs
```

## Instalación y uso local

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export COPERNICUSMARINE_SERVICE_USERNAME="tu_usuario"
export COPERNICUSMARINE_SERVICE_PASSWORD="tu_password"

python 01_download.py --test   # 2023-2024, valida el pipeline (~8 MB)
python 01_download.py          # descarga completa (1993 → mes anterior)
python 02_process.py
python 03_visualize.py
```

## Exploración interactiva

Usar `explore.ipynb` para análisis ad-hoc.

```bash
jupyter notebook explore.ipynb
```

El notebook selecciona automáticamente el run más reciente en `data/runs/`.
No guardar outputs en el `.ipynb` antes de hacer commit.

## GitHub Action

El workflow `.github/workflows/update_sst.yml` corre **trimestralmente**
(1 ene/abr/jul/oct, 06:00 UTC) y también puede dispararse manualmente desde
`Actions → Update SST quarterly → Run workflow`.

**Secrets requeridos** — configurar en `Settings → Secrets and variables → Actions`:

| Secret | Descripción |
|--------|-------------|
| `COPERNICUSMARINE_SERVICE_USERNAME` | Usuario de marine.copernicus.eu |
| `COPERNICUSMARINE_SERVICE_PASSWORD` | Contraseña de marine.copernicus.eu |

## Frecuencia recomendada

Trimestral. Cada ejecución crea un nuevo `data/runs/YYYY-MM/` sin
sobreescribir runs anteriores.

## Créditos

Datos: [Copernicus Marine Service](https://marine.copernicus.eu/) — producto
OSTIA SST L4 (`METOFFICE-GLO-SST-L4-REP-OBS-SST`).
