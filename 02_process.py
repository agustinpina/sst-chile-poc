"""
Procesa los NetCDFs descargados:
  - Convierte Kelvin → Celsius
  - Calcula media mensual y anual (promedio espacial)  → CSVs históricos
  - Calcula anomalía diaria 2026 vs climatología 1993-2020 → CSV + NetCDF
  - Exporta CSVs por región con columna "region"
"""
import sys

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import uniform_filter1d

from config import (
    BASELINE_END, BASELINE_START, DATA_DIR, NRT_FECHA_INICIO,
    REP_FECHA_FIN, REGIONES, VARIABLE,
)

CLIM_VENTANA = 11  # días, suavizado circular ±5 días alrededor de cada DOY


def procesar_region(nombre):
    archivo = DATA_DIR / f"{nombre}_sst.nc"
    if not archivo.exists():
        print(f"   ✗ No existe {archivo}, saltando.")
        return

    print(f"→ Procesando {nombre}...")
    try:
        ds = xr.open_dataset(archivo)
    except Exception as exc:
        print(f"   ✗ Error abriendo {archivo}: {exc}")
        return

    # Kelvin → Celsius
    sst_celsius = ds[VARIABLE] - 273.15

    # Promedio espacial (lat, lon) → serie temporal diaria
    sst_serie = sst_celsius.mean(dim=["latitude", "longitude"], skipna=True)

    # Resample mensual y anual
    sst_mensual = sst_serie.resample(time="1MS").mean(skipna=True)
    sst_anual = sst_serie.resample(time="1YS").mean(skipna=True)

    df_mensual = sst_mensual.to_dataframe(name="sst_celsius").reset_index()
    df_mensual["region"] = nombre

    df_anual = sst_anual.to_dataframe(name="sst_celsius").reset_index()
    df_anual["region"] = nombre

    salida_mensual = DATA_DIR / f"sst_monthly_{nombre}.csv"
    salida_anual = DATA_DIR / f"sst_annual_{nombre}.csv"
    df_mensual.to_csv(salida_mensual, index=False)
    df_anual.to_csv(salida_anual, index=False)

    print(f"   ✓ {salida_mensual.name} ({len(df_mensual)} filas)")
    print(f"   ✓ {salida_anual.name} ({len(df_anual)} filas)")
    ds.close()


def empalmar_rep_nrt(nombre):
    """Carga REP + NRT, empalma en REP_FECHA_FIN. Retorna DataArray (time, lat, lon) en °C."""
    ds_rep = xr.open_dataset(DATA_DIR / f"{nombre}_sst.nc")
    sst_rep = (ds_rep[VARIABLE] - 273.15).sel(time=slice(None, REP_FECHA_FIN))
    ds_rep.close()

    archivo_nrt = DATA_DIR / f"{nombre}_nrt.nc"
    if not archivo_nrt.exists():
        return sst_rep

    ds_nrt = xr.open_dataset(archivo_nrt)
    sst_nrt = (ds_nrt[VARIABLE] - 273.15).sel(time=slice(NRT_FECHA_INICIO, None))
    # Alinear grilla NRT → REP (mismo producto OSTIA 0.05°, diferencias mínimas)
    sst_nrt = sst_nrt.interp_like(sst_rep.isel(time=0), method="nearest")
    # Solo fechas posteriores al corte REP para no duplicar
    sst_nrt = sst_nrt.sel(time=sst_nrt.time > np.datetime64(REP_FECHA_FIN))
    ds_nrt.close()

    return xr.concat([sst_rep, sst_nrt], dim="time")


def calcular_climatologia_diaria(sst_celsius):
    """Climatología diaria por celda (DOY 1-365), suavizada circularmente."""
    baseline = sst_celsius.sel(
        time=slice(f"{BASELINE_START}-01-01", f"{BASELINE_END}-12-31")
    )
    clim = baseline.groupby("time.dayofyear").mean(dim="time", skipna=True)
    # Convolución circular sobre el eje DOY con scipy (evita artefactos en extremos)
    vals_smooth = uniform_filter1d(
        clim.values.astype(float), size=CLIM_VENTANA, axis=0, mode="wrap"
    )
    return clim.copy(data=vals_smooth)


def procesar_anomalia_2026(nombre):
    archivo_rep = DATA_DIR / f"{nombre}_sst.nc"
    archivo_nrt = DATA_DIR / f"{nombre}_nrt.nc"

    if not archivo_rep.exists():
        print(f"   ✗ No existe {archivo_rep}, saltando anomalías 2026.")
        return
    if not archivo_nrt.exists():
        print(f"   ✗ No existe {nombre}_nrt.nc — corre 01_download.py primero.")
        return

    print(f"→ Anomalías 2026 – {nombre}...")
    sst = empalmar_rep_nrt(nombre)

    print(f"   → Climatología diaria (baseline {BASELINE_START}–{BASELINE_END})...")
    clim = calcular_climatologia_diaria(sst)

    sst_2026 = sst.sel(time=sst.time.dt.year == 2026)
    if len(sst_2026.time) == 0:
        print(f"   ✗ No hay datos de 2026 para {nombre}.")
        return

    anom_2026 = (sst_2026.groupby("time.dayofyear") - clim).drop_vars("dayofyear")

    # Promedio espacial → CSV para fig4
    df = pd.DataFrame({
        "time": sst_2026.time.values,
        "sst_celsius": sst_2026.mean(dim=["latitude", "longitude"], skipna=True).values,
        "anomaly": anom_2026.mean(dim=["latitude", "longitude"], skipna=True).values,
    })
    salida_csv = DATA_DIR / f"sst_anom_2026_{nombre}.csv"
    df.to_csv(salida_csv, index=False)
    print(f"   ✓ {salida_csv.name} ({len(df)} filas)")

    # Por celda → NetCDF para GIF
    salida_nc = DATA_DIR / f"sst_anom_2026_{nombre}.nc"
    xr.Dataset({"anomalia": anom_2026}).to_netcdf(salida_nc)
    print(f"   ✓ {salida_nc.name}")


def main():
    if not DATA_DIR.exists():
        print(f"❌ No existe {DATA_DIR}. Ejecuta primero 01_download.py")
        sys.exit(1)

    for nombre in REGIONES:
        procesar_region(nombre)

    print()
    for nombre in REGIONES:
        procesar_anomalia_2026(nombre)

    print("\n✅ Procesamiento completo.")


if __name__ == "__main__":
    main()
