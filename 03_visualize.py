"""
Genera figuras a 150 dpi en figures/runs/{RUN_ID}/:
  fig1_serie_anual.png           → series anuales + tendencia por región
  fig2_ciclo_estacional.png      → climatología mensual con banda ±1 SD
  fig3_mapa_{region}.png (×3)    → mapa SST por región en figura separada
  fig4_anomalia_2026.png         → anomalías diarias 2026 vs climatología 1993-2020
  fig5_anomalia_{region}.gif (×3) → animación espacial de anomalías 2026
  fig6_anom_mensual_{region}.png (×3) → anomalía mensual, análogo GCH2025 Fig7
  fig7_distribucion_{region}.png (×3) → distribución diaria por año, análogo GCH2025 Fig1
"""
import sys

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

from config import (
    BASELINE_END, BASELINE_START, DATA_DIR, FECHA_FIN, FIGURES_DIR, REGIONES, VARIABLE,
)
from mapviz import add_coastline, render_field, styled_colorbar
from style import (
    apply_style, add_credit, add_minmax, CREAM, CMAP_SST, CMAP_ANOM,
    SST_VMIN, SST_VMAX, ANOM_ABS, CREDIT_GCH2025,
)

DPI = 150
DPI_GIF = 96
GIF_FPS = 8
ROLLING_DIAS = 7
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


def figura_mapa_region(nombre, bbox):
    """Genera un mapa SST promedio para una región, usando los años reales del NetCDF."""
    archivo = DATA_DIR / f"{nombre}_sst.nc"
    if not archivo.exists():
        print(f"   ✗ No existe {archivo}, saltando.")
        return

    ds = xr.open_dataset(archivo)
    sst = ds[VARIABLE] - 273.15

    # Rango de años real en el archivo (no depende de FECHA_FIN)
    anio_inicio_datos = int(str(ds.time.values[0])[:4])
    anio_fin_datos = int(str(ds.time.values[-1])[:4])

    sst_promedio = sst.mean(dim="time", skipna=True)

    fig, ax = plt.subplots(
        figsize=(8, 7),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )
    # Fondo del axes crema para que las celdas sin dato se fundan con la tierra
    ax.set_facecolor(CREAM)
    ax.set_extent([bbox["lon"][0], bbox["lon"][1], bbox["lat"][0], bbox["lat"][1]])

    im = render_field(ax, sst_promedio.longitude.values, sst_promedio.latitude.values,
                      sst_promedio.values, CMAP_SST, SST_VMIN, SST_VMAX, ccrs.PlateCarree())
    # Costa GSHHG "high" (encima del SST, ver mapviz.py): mucho más detalle
    # que Natural Earth 10m. "full" sería excesivamente lento/pesado para
    # regiones tan extensas como Aysén/Magallanes.
    add_coastline(ax, scale="high", zorder=3)

    # Gridlines mínimas: solo bottom y left, sin etiquetas top/right
    gl = ax.gridlines(draw_labels=True, alpha=0.15, linewidth=0.5, color="#2A2A2A")
    gl.top_labels = False
    gl.right_labels = False

    styled_colorbar(fig, im, ax, "SST (°C)")

    ax.set_title(
        f"SST media {anio_inicio_datos}–{anio_fin_datos} · {nombre.replace('_', ' ').title()}",
        fontsize=13,
    )
    ds.close()

    add_minmax(fig, sst_promedio.values)
    add_credit(fig)

    salida = FIGURES_DIR / f"fig3_mapa_{nombre}.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_mapas_por_region():
    for nombre, bbox in REGIONES.items():
        figura_mapa_region(nombre, bbox)


def figura_anomalia_2026():
    """fig4: anomalía diaria 2026 por región (barchart + media móvil)."""
    dfs = {}
    for nombre in REGIONES:
        ruta = DATA_DIR / f"sst_anom_2026_{nombre}.csv"
        if ruta.exists():
            dfs[nombre] = pd.read_csv(ruta, parse_dates=["time"])
    if not dfs:
        print("   ✗ No hay CSVs de anomalía 2026. Ejecuta 02_process.py primero.")
        return

    fig, axes = plt.subplots(len(REGIONES), 1, figsize=(13, 10), sharex=True)
    for ax, nombre in zip(axes, REGIONES):
        df = dfs.get(nombre)
        if df is None or df.empty:
            ax.set_visible(False)
            continue
        colores_bar = np.where(df["anomaly"] >= 0, "#d62728", "#1f77b4")
        ax.bar(df["time"], df["anomaly"], width=1, color=colores_bar, alpha=0.55,
               label="Anomalía diaria")
        rolling = df["anomaly"].rolling(ROLLING_DIAS, min_periods=1, center=True).mean()
        ax.plot(df["time"], rolling, color=COLORES[nombre], lw=2,
                label=f"Media móvil {ROLLING_DIAS} días")
        ax.axhline(0, color="black", lw=0.8)
        ax.set_ylabel("Anomalía (°C)")
        ultimo = df.dropna(subset=["anomaly"]).iloc[-1]
        ax.set_title(
            f"{nombre.replace('_', ' ').title()}  —  "
            f"último dato: {pd.Timestamp(ultimo['time']).strftime('%Y-%m-%d')} "
            f"({ultimo['anomaly']:+.2f} °C)"
        )
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(alpha=0.3)

    fig.suptitle(
        f"Anomalía SST 2026 vs. climatología {BASELINE_START}–{BASELINE_END}\n"
        "Zonas salmonicultoras Chile",
        fontsize=13,
    )
    fig.autofmt_xdate()
    salida = FIGURES_DIR / "fig4_anomalia_2026.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def cargar_csv_anom_diaria(nombre):
    ruta = DATA_DIR / f"sst_anom_daily_{nombre}.csv"
    if not ruta.exists():
        print(f"   ✗ No existe {ruta}, saltando (corre 02_process.py).")
        return None
    return pd.read_csv(ruta, parse_dates=["time"])


def figura_anom_mensual_region(nombre):
    """fig6: análogo a GCH2025 Fig7 — anomalía mensual (área roja/azul) por región."""
    df = cargar_csv_anom_diaria(nombre)
    if df is None or df.empty:
        return

    mensual = df.set_index("time")["anomaly"].resample("MS").mean().reset_index()

    fig, ax = plt.subplots(figsize=(11, 5))
    t, y = mensual["time"], mensual["anomaly"]
    ax.fill_between(t, 0, y, where=(y >= 0), color="#c0392b", alpha=0.85, interpolate=True)
    ax.fill_between(t, 0, y, where=(y < 0), color="#1f5c8c", alpha=0.85, interpolate=True)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("Anomalía SST (°C)")
    ax.set_title(
        f"Anomalía mensual SST vs. ref. {BASELINE_START}-{BASELINE_END} · "
        f"{nombre.replace('_', ' ').title()}"
    )
    ax.grid(alpha=0.3)
    add_credit(fig, nota=CREDIT_GCH2025)

    salida = FIGURES_DIR / f"fig6_anom_mensual_{nombre}.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_distribucion_region(nombre):
    """fig7: análogo a GCH2025 Fig1 — distribución (ridgeline) de anomalías diarias por año."""
    df = cargar_csv_anom_diaria(nombre)
    if df is None or df.empty:
        return

    df = df.dropna(subset=["anomaly"]).copy()
    df["anio"] = df["time"].dt.year
    anios = sorted(df["anio"].unique())
    if len(anios) < 2:
        print(f"   ✗ Muy pocos años para distribución en {nombre}, saltando.")
        return

    grilla = np.linspace(-4, 4, 400)
    cmap = plt.cm.RdYlBu_r
    norm = plt.Normalize(vmin=anios[0], vmax=anios[-1])
    paso = 1.0  # separación vertical entre ridgelines

    fig, ax = plt.subplots(figsize=(9, 0.35 * len(anios) + 2))
    for i, anio in enumerate(anios):
        valores = df.loc[df["anio"] == anio, "anomaly"].to_numpy()
        if len(valores) < 5:
            continue
        base = i * paso
        densidad = stats.gaussian_kde(valores)(grilla)
        densidad = densidad / densidad.max() * paso * 0.9  # normaliza altura
        ax.fill_between(grilla, base, base + densidad, color=cmap(norm(anio)), alpha=0.85, lw=0)
        ax.plot(grilla, base + densidad, color="black", lw=0.4, alpha=0.5)

    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.set_yticks([i * paso for i in range(len(anios))])
    ax.set_yticklabels([str(a) for a in anios], fontsize=7)
    ax.set_xlabel("Anomalía SST (°C)")
    ax.set_title(
        f"Distribución diaria de anomalías SST vs. ref. {BASELINE_START}-{BASELINE_END} · "
        f"{nombre.replace('_', ' ').title()}"
    )
    ax.grid(alpha=0.2, axis="x")
    add_credit(fig, nota=CREDIT_GCH2025)

    salida = FIGURES_DIR / f"fig7_distribucion_{nombre}.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_gif_anomalia_region(nombre, bbox):
    """fig5: GIF animado de anomalía SST 2026 diaria por celda."""
    archivo = DATA_DIR / f"sst_anom_2026_{nombre}.nc"
    if not archivo.exists():
        print(f"   ✗ No existe {archivo.name}, saltando GIF {nombre}.")
        return

    ds = xr.open_dataset(archivo)
    anom = ds["anomalia"]
    anom_smooth = anom.rolling(time=ROLLING_DIAS, min_periods=1, center=True).mean()
    times = pd.DatetimeIndex(anom_smooth.time.values)

    fig, ax = plt.subplots(
        figsize=(9, 8), subplot_kw={"projection": ccrs.PlateCarree()}
    )
    ax.set_extent([bbox["lon"][0], bbox["lon"][1], bbox["lat"][0], bbox["lat"][1]])
    add_coastline(ax, scale="high", zorder=3)
    ax.gridlines(draw_labels=True, alpha=0.3)

    frame0 = anom_smooth.isel(time=0)
    im = render_field(ax, frame0.longitude.values, frame0.latitude.values, frame0.values,
                      CMAP_ANOM, -ANOM_ABS, ANOM_ABS, ccrs.PlateCarree())
    styled_colorbar(fig, im, ax,
                    f"Anomalía SST (°C) vs. climatología {BASELINE_START}–{BASELINE_END}",
                    shrink=0.8, pad=0.08)
    add_credit(fig)
    titulo = ax.set_title("")
    fecha_txt = ax.text(0.01, 0.02, "", transform=ax.transAxes,
                        fontsize=11, fontweight="bold", color="black",
                        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))

    def update(i):
        frame = anom_smooth.isel(time=i).values
        im.set_array(frame.ravel())
        titulo.set_text(
            f"Anomalía SST 2026 – {nombre.replace('_', ' ').title()}\n"
            f"(media móvil {ROLLING_DIAS} días · ref. {BASELINE_START}–{BASELINE_END})"
        )
        fecha_txt.set_text(times[i].strftime("%Y-%m-%d"))
        return im, titulo, fecha_txt

    ntimes = len(times)
    print(f"   → Renderizando {ntimes} frames ({ntimes / GIF_FPS:.0f} s a {GIF_FPS} fps)…")
    ani = animation.FuncAnimation(
        fig, update, frames=ntimes, interval=1000 / GIF_FPS, blit=False
    )
    salida = FIGURES_DIR / f"fig5_anomalia_{nombre}.gif"
    ani.save(str(salida), writer="pillow", fps=GIF_FPS,
             savefig_kwargs={"dpi": DPI_GIF})
    plt.close(fig)
    ds.close()
    print(f"   ✓ {salida}")


def main():
    apply_style()
    print("🎨 Generando figuras...")
    df_anual = cargar_csv_anual_combinado()
    df_mensual = cargar_csv_mensual_combinado()
    figura_serie_anual(df_anual)
    figura_ciclo_estacional(df_mensual)
    figura_mapas_por_region()
    figura_anomalia_2026()
    for nombre in REGIONES:
        figura_anom_mensual_region(nombre)
        figura_distribucion_region(nombre)
    print("🎬 Generando GIFs de anomalía 2026...")
    for nombre, bbox in REGIONES.items():
        figura_gif_anomalia_region(nombre, bbox)
    print(f"\n✅ Figuras en {FIGURES_DIR}")


if __name__ == "__main__":
    main()
