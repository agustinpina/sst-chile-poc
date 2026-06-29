"""
Chequeo de SST para un centro de cultivo específico (lat/lon).

Descarga la serie completa 1993 → fin de cobertura del dataset para una
celda alrededor del punto, calcula una climatología mensual de referencia
(baseline) y la anomalía mes a mes, y genera figuras de anomalía.

Resultados: output/<name>/
  - centro_<name>_sst.nc         ← datos brutos (NetCDF)
  - centro_monthly_<name>.csv    ← serie mensual con climatología y anomalía
  - anom_serie.png               ← serie de anomalías con tendencia
  - anom_heatmap.png             ← mapa de calor mensual
  - anom_anual.png               ← anomalía media por año

Uso:
    python run_centro.py --lat -42.6256807 --lon -73.0538369 --name centro_ancud
"""
import argparse
import os
import sys
from pathlib import Path

import copernicusmarine
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from scipy import stats

from config import DATASET_ID, FECHA_FIN, FECHA_INICIO, VARIABLE

DPI = 150
# El dataset (versión 202003, reprocesado) no tiene datos más allá de 2025-12-18,
# aunque FECHA_FIN de config.py sea posterior.
FECHA_FIN_DATASET = "2025-12-31"

OUTPUT_DIR = Path("output")

COLOR_POS = "#d62728"
COLOR_NEG = "#1f77b4"


def parsear_argumentos():
    parser = argparse.ArgumentParser(
        description="Chequeo de SST para un centro de cultivo específico (lat/lon)."
    )
    parser.add_argument("--lat", type=float, required=True,
                        help="Latitud decimal (ej. -42.6256807)")
    parser.add_argument("--lon", type=float, required=True,
                        help="Longitud decimal (ej. -73.0538369)")
    parser.add_argument("--name", type=str, default=None,
                        help="Nombre identificador del centro (default: derivado de lat/lon)")
    parser.add_argument("--start", type=str, default=FECHA_INICIO,
                        help=f"Fecha inicio descarga (default: {FECHA_INICIO})")
    parser.add_argument("--end", type=str, default=None,
                        help=f"Fecha fin descarga (default: min(FECHA_FIN, {FECHA_FIN_DATASET}))")
    parser.add_argument("--baseline-start", type=int, default=1993,
                        help="Año inicio del período de referencia para climatología (default: 1993)")
    parser.add_argument("--baseline-end", type=int, default=2020,
                        help="Año fin del período de referencia para climatología (default: 2020)")
    return parser.parse_args()


def nombre_por_defecto(lat, lon):
    return f"lat{lat:.2f}_lon{lon:.2f}".replace("-", "m").replace(".", "p")


def verificar_credenciales():
    user = os.getenv("COPERNICUSMARINE_SERVICE_USERNAME")
    pwd = os.getenv("COPERNICUSMARINE_SERVICE_PASSWORD")
    if not user or not pwd:
        # copernicusmarine también acepta un login guardado vía
        # `copernicusmarine login` (~/.copernicusmarine-credentials);
        # si no hay env vars, dejamos que la librería intente con eso.
        print("ℹ️  No hay COPERNICUSMARINE_SERVICE_USERNAME/PASSWORD en el entorno;")
        print("   se intentará usar credenciales guardadas (`copernicusmarine login`).")


def descargar_centro(nombre, lat, lon, fecha_inicio, fecha_fin, archivo_salida, centro_dir):
    if archivo_salida.exists():
        print(f"   ↪ Ya existe {archivo_salida.name}, se reutiliza (no se vuelve a descargar).")
        return

    # Bbox pequeño (±0.1°, ~2 celdas de margen en grilla 0.05°) alrededor del
    # punto para garantizar que `.sel(..., method="nearest")` tenga vecinos
    # disponibles y no caiga justo en un borde de máscara de tierra.
    margen = 0.10
    print(f"→ Descargando centro {nombre} (lat={lat}, lon={lon}, "
          f"{fecha_inicio} → {fecha_fin})...")
    try:
        copernicusmarine.subset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE],
            minimum_longitude=lon - margen,
            maximum_longitude=lon + margen,
            minimum_latitude=lat - margen,
            maximum_latitude=lat + margen,
            start_datetime=f"{fecha_inicio}T00:00:00",
            end_datetime=f"{fecha_fin}T23:59:59",
            output_filename=archivo_salida.name,
            output_directory=str(centro_dir),
        )
        tamanio_mb = archivo_salida.stat().st_size / (1024 * 1024)
        print(f"   ✓ {archivo_salida.name} ({tamanio_mb:.1f} MB)")
    except Exception as exc:
        print(f"   ✗ Error al descargar centro {nombre}: {exc}")
        raise


def procesar_centro(archivo, lat, lon, baseline_start, baseline_end):
    """Extrae la celda más cercana, calcula serie mensual, climatología y anomalía."""
    ds = xr.open_dataset(archivo)
    sst_celsius = ds[VARIABLE] - 273.15

    celda = sst_celsius.sel(latitude=lat, longitude=lon, method="nearest")
    lat_celda = float(celda.latitude)
    lon_celda = float(celda.longitude)
    print(f"   ↪ Celda más cercana: lat={lat_celda:.3f}, lon={lon_celda:.3f}")

    nan_frac = float(np.isnan(celda.values).mean())
    if nan_frac > 0:
        print(f"   ⚠️  La celda tiene {nan_frac:.1%} de valores NaN "
              "(posible máscara de tierra/hielo).")

    serie_mensual = celda.resample(time="1MS").mean(skipna=True)
    df = serie_mensual.to_dataframe(name="sst_celsius").reset_index()
    df = df[["time", "sst_celsius"]].copy()
    df["mes"] = df["time"].dt.month
    df["anio"] = df["time"].dt.year

    baseline = df[(df["anio"] >= baseline_start) & (df["anio"] <= baseline_end)]
    if baseline.empty:
        raise ValueError(
            f"El período de referencia {baseline_start}-{baseline_end} "
            "no tiene datos en la serie descargada."
        )
    climatologia = baseline.groupby("mes")["sst_celsius"].mean().rename("clim")

    df = df.merge(climatologia, on="mes", how="left")
    df["anomaly"] = df["sst_celsius"] - df["clim"]
    df = df.drop(columns=["mes", "anio"]).sort_values("time").reset_index(drop=True)

    ds.close()
    return df, (lat_celda, lon_celda)


def figura_serie_anomalia(df, nombre, baseline_start, baseline_end, salida_dir):
    fig, ax = plt.subplots(figsize=(12, 6))
    colores = np.where(df["anomaly"] >= 0, COLOR_POS, COLOR_NEG)
    ax.bar(df["time"], df["anomaly"], width=25, color=colores, alpha=0.6,
           label="Anomalía mensual")

    media_movil = df["anomaly"].rolling(window=12, min_periods=12).mean()
    ax.plot(df["time"], media_movil, color="black", lw=1.8, label="Media móvil 12 meses")

    x_num = df["time"].astype("int64").to_numpy()
    reg = stats.linregress(x_num, df["anomaly"].to_numpy())
    pendiente_decada = reg.slope * 1e9 * 60 * 60 * 24 * 365.25 * 10  # ns → °C/década
    ax.plot(df["time"], reg.intercept + reg.slope * x_num, ls="--", color="dimgray",
            label=f"Tendencia ({pendiente_decada:+.2f} °C/década)")

    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"Anomalía de SST – {nombre}\n"
                 f"(referencia: climatología {baseline_start}-{baseline_end})")
    ax.set_xlabel("Año")
    ax.set_ylabel("Anomalía SST (°C)")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    salida = salida_dir / "anom_serie.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_heatmap_anomalia(df, nombre, salida_dir):
    pivot = df.assign(anio=df["time"].dt.year, mes=df["time"].dt.month) \
              .pivot(index="anio", columns="mes", values="anomaly")
    pivot = pivot.reindex(columns=range(1, 13))

    fig, ax = plt.subplots(figsize=(9, max(6, 0.28 * len(pivot))))
    vmax = float(np.nanmax(np.abs(pivot.values))) or 1.0
    im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title(f"Anomalía de SST mes a mes – {nombre}")
    fig.colorbar(im, ax=ax, label="Anomalía SST (°C)", shrink=0.8)
    salida = salida_dir / "anom_heatmap.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_anomalia_anual(df, nombre, salida_dir):
    anual = df.assign(anio=df["time"].dt.year).groupby("anio")["anomaly"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(10, 6))
    colores = np.where(anual["anomaly"] >= 0, COLOR_POS, COLOR_NEG)
    ax.bar(anual["anio"], anual["anomaly"], color=colores, alpha=0.8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"Anomalía media anual de SST – {nombre}")
    ax.set_xlabel("Año")
    ax.set_ylabel("Anomalía SST (°C)")
    ax.grid(alpha=0.3, axis="y")
    salida = salida_dir / "anom_anual.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def main():
    args = parsear_argumentos()
    nombre = args.name or nombre_por_defecto(args.lat, args.lon)
    fecha_fin = args.end or min(FECHA_FIN, FECHA_FIN_DATASET)

    centro_dir = OUTPUT_DIR / nombre
    centro_dir.mkdir(parents=True, exist_ok=True)

    archivo_nc = centro_dir / f"centro_{nombre}_sst.nc"

    print(f"📍 Centro: {nombre} (lat={args.lat}, lon={args.lon})")
    verificar_credenciales()
    descargar_centro(nombre, args.lat, args.lon, args.start, fecha_fin, archivo_nc, centro_dir)

    print(f"→ Procesando {nombre}...")
    try:
        df, celda = procesar_centro(archivo_nc, args.lat, args.lon,
                                    args.baseline_start, args.baseline_end)
    except ValueError as e:
        sys.exit(f"❌ {e}")

    salida_csv = centro_dir / f"centro_monthly_{nombre}.csv"
    df.to_csv(salida_csv, index=False)
    print(f"   ✓ {salida_csv.name} ({len(df)} filas)")

    print("🎨 Generando figuras...")
    figura_serie_anomalia(df, nombre, args.baseline_start, args.baseline_end, centro_dir)
    figura_heatmap_anomalia(df, nombre, centro_dir)
    figura_anomalia_anual(df, nombre, centro_dir)

    # Resumen térmico
    ultimo = df.dropna(subset=["sst_celsius"]).iloc[-1]
    x_num = df["time"].astype("int64").to_numpy()
    reg = stats.linregress(x_num, df["anomaly"].to_numpy())
    tendencia = reg.slope * 1e9 * 60 * 60 * 24 * 365.25 * 10

    print(f"\n📊 Resumen — {nombre}")
    print(f"   Último dato:   {ultimo['time'].strftime('%Y-%m')}  ·  {ultimo['sst_celsius']:.1f} °C")
    print(f"   Anomalía:      {ultimo['anomaly']:+.1f} °C  "
          f"(vs climatología {args.baseline_start}-{args.baseline_end})")
    print(f"   Tendencia:     {tendencia:+.2f} °C/década")
    print(f"\n✅ Listo. Resultados en {centro_dir}/")
    print(f"   Celda usada: lat={celda[0]:.3f}, lon={celda[1]:.3f}")


if __name__ == "__main__":
    main()
