"""
Descarga subconjuntos del producto Copernicus OSTIA SST L4 para cada
región salmonicultora de Chile y los guarda como NetCDF en
data/runs/{RUN_ID}/.

Uso:
    python 01_download.py            # descarga completa (1993 → ayer)
    python 01_download.py --test     # solo 2023-2024 para validar pipeline
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import copernicusmarine

from config import (
    DATA_DIR, DATASET_ID, FECHA_FIN, FECHA_INICIO, REGIONES, RUN_ID, VARIABLE,
)


def parsear_argumentos():
    parser = argparse.ArgumentParser(description="Descarga SST Copernicus por región.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Descarga solo 2023-2024 (validación rápida del pipeline).",
    )
    return parser.parse_args()


def verificar_run_existente():
    """Aborta si ya existen NetCDFs en data/runs/{RUN_ID}/ para evitar sobreescritura."""
    archivos_existentes = list(DATA_DIR.glob("*_sst.nc"))
    if archivos_existentes:
        print(f"⚠️  El run {RUN_ID} ya tiene datos en {DATA_DIR}:")
        for archivo in archivos_existentes:
            print(f"   - {archivo.name}")
        print("Aborta para no sobreescribir. Borra la carpeta si deseas regenerar.")
        sys.exit(1)


def verificar_credenciales():
    user = os.getenv("COPERNICUSMARINE_SERVICE_USERNAME")
    pwd = os.getenv("COPERNICUSMARINE_SERVICE_PASSWORD")
    if not user or not pwd:
        print("❌ Faltan credenciales. Exporta:")
        print("   export COPERNICUSMARINE_SERVICE_USERNAME=...")
        print("   export COPERNICUSMARINE_SERVICE_PASSWORD=...")
        sys.exit(1)


def descargar_region(nombre, bbox, fecha_inicio, fecha_fin):
    archivo_salida = DATA_DIR / f"{nombre}_sst.nc"
    print(f"→ Descargando {nombre} ({fecha_inicio} → {fecha_fin})...")
    try:
        copernicusmarine.subset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE],
            minimum_longitude=bbox["lon"][0],
            maximum_longitude=bbox["lon"][1],
            minimum_latitude=bbox["lat"][0],
            maximum_latitude=bbox["lat"][1],
            start_datetime=f"{fecha_inicio}T00:00:00",
            end_datetime=f"{fecha_fin}T23:59:59",
            output_filename=archivo_salida.name,
            output_directory=str(DATA_DIR),
        )
        tamanio_mb = archivo_salida.stat().st_size / (1024 * 1024)
        print(f"   ✓ {archivo_salida.name} ({tamanio_mb:.1f} MB)")
        return tamanio_mb
    except Exception as exc:
        print(f"   ✗ Error al descargar {nombre}: {exc}")
        raise


def escribir_log(fecha_inicio, fecha_fin, tamanios):
    log_path = DATA_DIR / "run_log.txt"
    with log_path.open("w", encoding="utf-8") as fh:
        fh.write(f"Run ID: {RUN_ID}\n")
        fh.write(f"Ejecutado: {datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"Período: {fecha_inicio} → {fecha_fin}\n")
        fh.write(f"Producto: {DATASET_ID}\n")
        fh.write(f"Variable: {VARIABLE}\n")
        fh.write("Archivos descargados:\n")
        for nombre, mb in tamanios.items():
            fh.write(f"  - {nombre}_sst.nc: {mb:.1f} MB\n")
    print(f"📝 Log escrito en {log_path}")


def main():
    args = parsear_argumentos()
    verificar_credenciales()
    verificar_run_existente()

    if args.test:
        fecha_inicio, fecha_fin = "2023-01-01", "2024-12-31"
        print(f"🧪 Modo --test: descargando solo {fecha_inicio} → {fecha_fin}")
    else:
        fecha_inicio, fecha_fin = FECHA_INICIO, FECHA_FIN
        print(f"📡 Descarga completa: {fecha_inicio} → {fecha_fin}")

    tamanios = {}
    for nombre, bbox in REGIONES.items():
        tamanios[nombre] = descargar_region(nombre, bbox, fecha_inicio, fecha_fin)

    escribir_log(fecha_inicio, fecha_fin, tamanios)
    print(f"\n✅ Descarga finalizada. Run: {RUN_ID}")


if __name__ == "__main__":
    main()
