"""
Procesa los NetCDFs descargados:
  - Convierte Kelvin → Celsius
  - Calcula media mensual y anual (promedio espacial)
  - Exporta CSVs por región con columna "region"
"""
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

from config import DATA_DIR, REGIONES, VARIABLE


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


def main():
    if not DATA_DIR.exists():
        print(f"❌ No existe {DATA_DIR}. Ejecuta primero 01_download.py")
        sys.exit(1)

    for nombre in REGIONES:
        procesar_region(nombre)
    print("\n✅ Procesamiento completo.")


if __name__ == "__main__":
    main()
