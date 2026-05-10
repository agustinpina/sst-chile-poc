"""
Genera tres figuras a 150 dpi en figures/runs/{RUN_ID}/:
  fig1_serie_anual.png      → series anuales + tendencia por región
  fig2_ciclo_estacional.png → climatología mensual con banda ±1 SD
  fig3_mapa_promedio.png    → mapa SST últimos 5 años por región (Cartopy)
"""
import sys

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

from config import DATA_DIR, FECHA_FIN, FIGURES_DIR, REGIONES, VARIABLE

DPI = 150
COLORES = {"los_lagos": "#1f77b4", "aysen": "#2ca02c", "magallanes": "#d62728"}
ANIO_FIN = int(FECHA_FIN[:4])


def cargar_csv_anual_combinado():
    frames = []
    for nombre in REGIONES:
        ruta = DATA_DIR / f"sst_annual_{nombre}.csv"
        if not ruta.exists():
            print(f"   ✗ No existe {ruta}")
            continue
        df = pd.read_csv(ruta, parse_dates=["time"])
        frames.append(df)
    if not frames:
        sys.exit("❌ No hay CSVs anuales. Ejecuta 02_process.py primero.")
    return pd.concat(frames, ignore_index=True)


def cargar_csv_mensual_combinado():
    frames = []
    for nombre in REGIONES:
        ruta = DATA_DIR / f"sst_monthly_{nombre}.csv"
        if ruta.exists():
            frames.append(pd.read_csv(ruta, parse_dates=["time"]))
    if not frames:
        sys.exit("❌ No hay CSVs mensuales.")
    return pd.concat(frames, ignore_index=True)


def figura_serie_anual(df_anual):
    fig, ax = plt.subplots(figsize=(10, 6))
    for nombre in REGIONES:
        sub = df_anual[df_anual["region"] == nombre].sort_values("time")
        if sub.empty:
            continue
        anios = sub["time"].dt.year.to_numpy()
        valores = sub["sst_celsius"].to_numpy()
        # Tendencia lineal: °C por año → °C/década
        reg = stats.linregress(anios, valores)
        pendiente_decada = reg.slope * 10
        etiqueta = f"{nombre} ({pendiente_decada:+.2f} °C/década)"
        ax.plot(anios, valores, marker="o", color=COLORES[nombre], label=etiqueta)
        ax.plot(anios, reg.intercept + reg.slope * anios, ls="--",
                color=COLORES[nombre], alpha=0.5)
    anio_inicio = int(df_anual["time"].dt.year.min())
    ax.set_title(f"SST media anual – zonas salmonicultoras Chile ({anio_inicio}–{ANIO_FIN})")
    ax.set_xlabel("Año")
    ax.set_ylabel("SST (°C)")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    salida = FIGURES_DIR / "fig1_serie_anual.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_ciclo_estacional(df_mensual):
    fig, ax = plt.subplots(figsize=(10, 6))
    df_mensual = df_mensual.copy()
    df_mensual["mes"] = df_mensual["time"].dt.month
    for nombre in REGIONES:
        sub = df_mensual[df_mensual["region"] == nombre]
        if sub.empty:
            continue
        clima = sub.groupby("mes")["sst_celsius"].agg(["mean", "std"]).reset_index()
        ax.plot(clima["mes"], clima["mean"], marker="o",
                color=COLORES[nombre], label=nombre)
        ax.fill_between(clima["mes"], clima["mean"] - clima["std"],
                        clima["mean"] + clima["std"], color=COLORES[nombre], alpha=0.2)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"])
    ax.set_title("Ciclo estacional SST – zonas salmonicultoras Chile")
    ax.set_xlabel("Mes")
    ax.set_ylabel("SST (°C)")
    ax.legend()
    ax.grid(alpha=0.3)
    salida = FIGURES_DIR / "fig2_ciclo_estacional.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_mapa_promedio():
    anio_inicio_mapa = ANIO_FIN - 4
    fig, axes = plt.subplots(
        1, len(REGIONES), figsize=(15, 6),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )
    if len(REGIONES) == 1:
        axes = [axes]

    im = None
    for ax, (nombre, bbox) in zip(axes, REGIONES.items()):
        archivo = DATA_DIR / f"{nombre}_sst.nc"
        if not archivo.exists():
            ax.set_title(f"{nombre}: sin datos")
            continue
        ds = xr.open_dataset(archivo)
        sst = ds[VARIABLE] - 273.15
        sst_recortado = sst.sel(time=slice(f"{anio_inicio_mapa}-01-01", FECHA_FIN))
        sst_promedio = sst_recortado.mean(dim="time", skipna=True)
        im = sst_promedio.plot(
            ax=ax, cmap="RdYlBu_r", vmin=8, vmax=18,
            transform=ccrs.PlateCarree(), add_colorbar=False,
        )
        ax.coastlines(resolution="10m")
        ax.add_feature(cfeature.BORDERS, linestyle=":")
        ax.gridlines(draw_labels=True, alpha=0.3)
        ax.set_title(nombre)
        ds.close()

    fig.suptitle(f"SST media {anio_inicio_mapa}–{ANIO_FIN} por zona", fontsize=14)
    if im is not None:
        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        fig.colorbar(im, cax=cbar_ax, label="SST (°C)")
    salida = FIGURES_DIR / "fig3_mapa_promedio.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def main():
    print("🎨 Generando figuras...")
    df_anual = cargar_csv_anual_combinado()
    df_mensual = cargar_csv_mensual_combinado()
    figura_serie_anual(df_anual)
    figura_ciclo_estacional(df_mensual)
    figura_mapa_promedio()
    print(f"\n✅ Figuras en {FIGURES_DIR}")


if __name__ == "__main__":
    main()
