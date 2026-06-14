"""
run_chiloe_gif.py — GIF de anomalía SST del mar interior de Chiloé (2026)

Descarga REP + NRT para el bbox del mar interior de Chiloé, calcula la anomalía
diaria por celda vs. climatología 1993-2020, genera un GIF animado (un frame
por día de 2026) y exporta:

  - data/sites/chiloe_mar_interior/anomalia_diaria_2026.nc   (cubo dataset)
  - data/sites/chiloe_mar_interior/anomalia_media_diaria_2026.csv
  - figures/sites/chiloe_mar_interior/mapa_anomalia_2026_chiloe.gif
  - figures/sites/chiloe_mar_interior/mapa_anomalia_2026_chiloe_final.png
  - figures/sites/chiloe_mar_interior/conclusiones_chiloe_2026.md

Reutiliza constantes y funciones de config.py, run_point.py y run_site.py.
Las descargas son idempotentes: si el .nc ya existe en disco no se vuelve
a descargar.

Uso:
    python run_chiloe_gif.py
    python run_chiloe_gif.py --lat -42.63 --lon -73.05 --name chiloe_mar_interior
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import copernicusmarine
from scipy.ndimage import uniform_filter1d

from config import DATASET_ID, FECHA_INICIO, VARIABLE
from mapviz import add_coastline
from run_point import DPI
from run_site import (
    DATASET_ID_NRT,
    NRT_FECHA_INICIO,
    REP_FECHA_FIN,
    calcular_climatologia_diaria,
    combinar_bbox,
    detectar_eventos_mhw,
)

# ---------------------------------------------------------------------------
# Bbox del mar interior de Chiloé
# Cubre: Reloncaví (norte) → Golfo de Corcovado (sur), isla + mar interior
# ---------------------------------------------------------------------------
BBOX_LAT = [-43.6, -41.4]   # ° S → ° S
BBOX_LON = [-74.3, -72.4]   # ° W → ° W

SITES_DATA_DIR   = Path("data/sites")
SITES_FIGURES_DIR = Path("figures/sites")

BASELINE_START = 1993
BASELINE_END   = 2020
CLIM_VENTANA   = 11   # suavizado circular de climatología (±5 días)
ROLLING_DIAS   = 7    # media móvil trailing para suavizar el GIF

GIF_FPS     = 8
GIF_FIGSIZE = (9, 8)
GIF_DPI     = 100


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parsear_argumentos():
    p = argparse.ArgumentParser(
        description="GIF de anomalía SST del mar interior de Chiloé (2026)."
    )
    p.add_argument("--lat", type=float, default=-42.63,
                   help="Lat del centroide (marca en el mapa); default: -42.63")
    p.add_argument("--lon", type=float, default=-73.05,
                   help="Lon del centroide; default: -73.05")
    p.add_argument("--name", type=str, default="chiloe_mar_interior",
                   help="Nombre del subdirectorio de salida (default: chiloe_mar_interior)")
    p.add_argument("--baseline-start", type=int, default=BASELINE_START)
    p.add_argument("--baseline-end",   type=int, default=BASELINE_END)
    return p.parse_args()


def verificar_credenciales():
    u  = os.getenv("COPERNICUSMARINE_SERVICE_USERNAME")
    pw = os.getenv("COPERNICUSMARINE_SERVICE_PASSWORD")
    if not u or not pw:
        print("ℹ️  Sin credenciales en entorno; se usarán las guardadas con "
              "`copernicusmarine login`.")


# ---------------------------------------------------------------------------
# Descarga con bbox explícito (lat_min/max, lon_min/max)
# ---------------------------------------------------------------------------

def descargar_bbox_preciso(
    dataset_id, etiqueta,
    lat_min, lat_max, lon_min, lon_max,
    fecha_inicio, fecha_fin,
    archivo_salida, data_dir,
):
    """Descarga un subset espacio-temporal con bounds explícitos. Idempotente."""
    if archivo_salida.exists():
        mb = archivo_salida.stat().st_size / 1e6
        print(f"   ↪ Ya existe {archivo_salida.name} ({mb:.1f} MB), se reutiliza.")
        return
    print(f"→ Descargando {etiqueta}  "
          f"(lat [{lat_min},{lat_max}], lon [{lon_min},{lon_max}], "
          f"{fecha_inicio} → {fecha_fin})...")
    try:
        copernicusmarine.subset(
            dataset_id=dataset_id,
            variables=[VARIABLE],
            minimum_latitude=lat_min,
            maximum_latitude=lat_max,
            minimum_longitude=lon_min,
            maximum_longitude=lon_max,
            start_datetime=f"{fecha_inicio}T00:00:00",
            end_datetime=f"{fecha_fin}T23:59:59",
            output_filename=archivo_salida.name,
            output_directory=str(data_dir),
        )
        mb = archivo_salida.stat().st_size / 1e6
        print(f"   ✓ {archivo_salida.name} ({mb:.1f} MB)")
    except Exception as exc:
        print(f"   ✗ Error al descargar {etiqueta}: {exc}")
        raise


# ---------------------------------------------------------------------------
# Climatología diaria vectorizada por celda
# ---------------------------------------------------------------------------

def climatologia_diaria_por_celda(rep_celsius, baseline_start, baseline_end,
                                   ventana=CLIM_VENTANA):
    """
    Climatología diaria por celda: media del DOY × lat × lon calculada sobre
    [baseline_start, baseline_end], suavizada con ventana circular de `ventana`
    días sobre el eje dayofyear.

    Devuelve xr.DataArray con dims (dayofyear, latitude, longitude).
    """
    base = rep_celsius.sel(
        time=slice(f"{baseline_start}-01-01", f"{baseline_end}-12-31")
    )
    # groupby dayofyear produce dims (dayofyear, latitude, longitude)
    clim = base.groupby("time.dayofyear").mean("time")

    # Suavizado circular a lo largo del eje dayofyear (valores 1-365 o 1-366)
    vals   = clim.values                                        # (ndoy, nlat, nlon)
    smooth = uniform_filter1d(vals, size=ventana, axis=0, mode="wrap")

    return xr.DataArray(
        smooth,
        coords=clim.coords,
        dims=clim.dims,
        attrs={
            "long_name": (
                f"Climatología diaria SST suavizada (ventana {ventana} días, "
                f"baseline {baseline_start}–{baseline_end})"
            ),
            "units": "°C",
        },
    )


# ---------------------------------------------------------------------------
# Anomalía 2026
# ---------------------------------------------------------------------------

def anomalia_por_celda_2026(sst_2026, clim_por_celda):
    """
    Anomalía diaria = SST(día) − clim(DOY) por celda, para todos los días de
    2026 disponibles. Usa groupby para alinear automáticamente dayofyear.
    """
    anom = sst_2026.groupby("time.dayofyear") - clim_por_celda
    anom.attrs = {
        "long_name": "Anomalía SST vs. climatología diaria",
        "units": "°C",
    }
    return anom


# ---------------------------------------------------------------------------
# Exportar dataset
# ---------------------------------------------------------------------------

def guardar_dataset(anom, clim, data_dir):
    """Exporta el cubo de anomalías + climatología a NetCDF."""
    ds = xr.Dataset(
        {
            "anomalia_sst":   anom,
            "climatologia_sst": clim,
        },
        attrs={
            "title":    "Anomalía diaria SST — Mar interior de Chiloé 2026",
            "baseline": f"{BASELINE_START}–{BASELINE_END}",
            "source":   "METOFFICE-GLO-SST-L4 REP + NRT | OSTIA 0.05°",
            "created":  date.today().isoformat(),
        },
    )
    salida = data_dir / "anomalia_diaria_2026.nc"
    ds.to_netcdf(salida)
    mb = salida.stat().st_size / 1e6
    print(f"   ✓ {salida} ({mb:.1f} MB)")


def guardar_csv_media_diaria(anom_smooth, data_dir):
    """CSV con la anomalía media espacial diaria (post-rolling)."""
    media = anom_smooth.mean(dim=["latitude", "longitude"])
    df = pd.DataFrame({
        "time":             pd.DatetimeIndex(anom_smooth.time.values),
        "anomalia_media_c": media.values.round(4),
    })
    salida = data_dir / "anomalia_media_diaria_2026.csv"
    df.to_csv(salida, index=False)
    print(f"   ✓ {salida} ({len(df)} días)")
    return df


# ---------------------------------------------------------------------------
# GIF animado
# ---------------------------------------------------------------------------

def generar_gif(anom_smooth, lat_centroide, lon_centroide, nombre, figuras_dir):
    """
    Genera el GIF animado de anomalía SST 2026 (1 frame/día) con:
    - pcolormesh RdBu_r, escala fija y simétrica
    - Costa, tierra, grilla de coordenadas
    - Texto dinámico: fecha + anomalía media
    - Frame final exportado como PNG HD
    """
    times       = pd.DatetimeIndex(anom_smooth.time.values)
    ntimes      = len(times)
    anom_media  = anom_smooth.mean(dim=["latitude", "longitude"]).values
    lons        = anom_smooth.longitude.values
    lats        = anom_smooth.latitude.values

    # Escala de color fija y simétrica: P98 del valor absoluto del período
    vmax = float(np.nanpercentile(np.abs(anom_smooth.values), 98))
    vmax = max(np.ceil(vmax * 10) / 10, 0.1)   # mínimo 0.1 °C, redondear a 1 decimal
    print(f"   → Escala de color fija: ±{vmax:.1f} °C  (P98 del período)")

    # ─── Configurar figura de la animación ───────────────────────────────────
    fig, ax = plt.subplots(
        figsize=GIF_FIGSIZE,
        subplot_kw={"projection": ccrs.PlateCarree()}
    )
    ax.set_extent(
        [BBOX_LON[0], BBOX_LON[1], BBOX_LAT[0], BBOX_LAT[1]],
        crs=ccrs.PlateCarree()
    )

    # Fondo del océano (antes del pcolormesh)
    ax.add_feature(cfeature.OCEAN, facecolor="#d0e8f5", zorder=0)

    # pcolormesh de anomalía (zorder=1, debajo de la tierra)
    frame0 = anom_smooth.isel(time=0).values
    pcm = ax.pcolormesh(
        lons, lats, frame0,
        cmap="RdBu_r", vmin=-vmax, vmax=vmax,
        transform=ccrs.PlateCarree(), zorder=1,
    )

    # Capas topográficas encima de la anomalía (costa GSHHG full, incluye
    # islas y canales del mar interior que Natural Earth 10m no resuelve)
    add_coastline(ax, scale="full", zorder=3)
    ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.6, zorder=3)

    # Grilla
    gl = ax.gridlines(draw_labels=True, alpha=0.3, zorder=2,
                      linewidth=0.5, color="gray")
    gl.top_labels   = False
    gl.right_labels = False

    # Colorbar
    cbar = fig.colorbar(
        pcm, ax=ax, shrink=0.72, pad=0.08,
        label="Anomalía SST (°C)\nvs. climatología 1993–2020",
    )
    cbar.ax.tick_params(labelsize=9)

    # Título fijo
    ax.set_title(
        "Anomalía térmica SST — Mar interior de Chiloé (2026)\n"
        f"Media móvil {ROLLING_DIAS} días · Referencia climatológica "
        f"{BASELINE_START}–{BASELINE_END}",
        fontsize=11, pad=8,
    )

    # Textos dinámicos (se actualizan en cada frame)
    _bbox_props = dict(facecolor="white", alpha=0.80,
                       boxstyle="round,pad=0.3", edgecolor="none")
    fecha_text = ax.text(
        0.02, 0.975, "", transform=ax.transAxes,
        fontsize=14, fontweight="bold", va="top", ha="left",
        bbox=_bbox_props, zorder=7,
    )
    anom_text = ax.text(
        0.02, 0.900, "", transform=ax.transAxes,
        fontsize=11, va="top", ha="left",
        bbox=_bbox_props, zorder=7,
    )
    fuente_text = ax.text(
        0.99, 0.01,
        "Datos: Copernicus Marine (OSTIA 0.05°)\nrun_chiloe_gif.py",
        transform=ax.transAxes, fontsize=7,
        va="bottom", ha="right", color="#555555", zorder=7,
    )

    # ─── Función de actualización por frame ──────────────────────────────────
    def update(i):
        frame_data = anom_smooth.isel(time=i).values
        pcm.set_array(frame_data.ravel())

        fecha = times[i]
        fecha_text.set_text(f"{fecha.strftime('%d %b %Y')}")

        val    = float(anom_media[i])
        signo  = "+" if val >= 0 else ""
        color  = ("#c0392b" if val > 0.15
                  else ("#2471a3" if val < -0.15 else "#333333"))
        anom_text.set_text(f"Δ media: {signo}{val:.2f} °C")
        anom_text.set_color(color)

        return pcm, fecha_text, anom_text

    # ─── Renderizar y guardar ─────────────────────────────────────────────────
    print(f"   → Renderizando {ntimes} frames  ({ntimes / GIF_FPS:.0f} s a {GIF_FPS} fps)…")
    ani    = animation.FuncAnimation(fig, update, frames=ntimes,
                                     interval=1000 / GIF_FPS, blit=False)
    writer = animation.PillowWriter(fps=GIF_FPS)
    gif_path = figuras_dir / "mapa_anomalia_2026_chiloe.gif"
    ani.save(str(gif_path), writer=writer, dpi=GIF_DPI)
    plt.close(fig)

    mb = gif_path.stat().st_size / 1e6
    print(f"   ✓ {gif_path}  ({mb:.1f} MB, {ntimes} frames)")

    # ─── Frame final como PNG HD ──────────────────────────────────────────────
    fig2, ax2 = plt.subplots(
        figsize=(10, 9),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )
    ax2.set_extent([BBOX_LON[0], BBOX_LON[1], BBOX_LAT[0], BBOX_LAT[1]],
                   crs=ccrs.PlateCarree())
    ax2.add_feature(cfeature.OCEAN,   facecolor="#d0e8f5", zorder=0)
    pcm2 = ax2.pcolormesh(
        lons, lats, anom_smooth.isel(time=-1).values,
        cmap="RdBu_r", vmin=-vmax, vmax=vmax,
        transform=ccrs.PlateCarree(), zorder=1,
    )
    add_coastline(ax2, scale="full", zorder=3)
    ax2.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.6, zorder=3)
    gl2 = ax2.gridlines(draw_labels=True, alpha=0.3, zorder=2,
                        linewidth=0.5, color="gray")
    gl2.top_labels = False; gl2.right_labels = False
    fig2.colorbar(pcm2, ax=ax2, shrink=0.72, pad=0.08,
                  label="Anomalía SST (°C) vs. climatología 1993–2020")
    ax2.set_title(
        f"Anomalía SST — Mar interior de Chiloé · {times[-1]:%d %b %Y}\n"
        f"Media móvil {ROLLING_DIAS} días · Referencia {BASELINE_START}–{BASELINE_END}",
        fontsize=12, pad=10,
    )
    ax2.text(0.02, 0.975, f"{times[-1].strftime('%d %b %Y')}",
             transform=ax2.transAxes, fontsize=14, fontweight="bold",
             va="top", ha="left",
             bbox=dict(facecolor="white", alpha=0.80, boxstyle="round,pad=0.3"),
             zorder=7)
    png_path = figuras_dir / "mapa_anomalia_2026_chiloe_final.png"
    fig2.savefig(str(png_path), dpi=DPI, bbox_inches="tight")
    plt.close(fig2)
    print(f"   ✓ {png_path}")

    return gif_path


# ---------------------------------------------------------------------------
# Ranking histórico ene–jun
# ---------------------------------------------------------------------------

def ranking_historico(rep_celsius, clim_por_celda):
    """
    Para cada año 1993-2025, calcula la anomalía media del recuadro en ene–jun
    y devuelve un DataFrame ordenado de mayor a menor.
    """
    # Media espacial: serie temporal diaria escalar
    rep_mean  = rep_celsius.mean(dim=["latitude", "longitude"])
    clim_mean = clim_por_celda.mean(dim=["latitude", "longitude"])  # (dayofyear,)

    ndoy = int(clim_mean.dayofyear.max())
    clim_dict = {
        int(d): float(clim_mean.sel(dayofyear=d))
        for d in clim_mean.dayofyear.values
    }

    df = pd.DataFrame({
        "time": pd.DatetimeIndex(rep_mean.time.values),
        "sst":  rep_mean.values,
    })
    df["anio"]  = df["time"].dt.year
    df["mes"]   = df["time"].dt.month
    df["doy"]   = df["time"].dt.dayofyear.clip(upper=ndoy)
    df["clim"]  = df["doy"].map(clim_dict)
    df["anom"]  = df["sst"] - df["clim"]

    # Solo ene–jun
    ranking = (
        df[df["mes"] <= 6]
        .groupby("anio")["anom"]
        .mean()
        .round(3)
        .reset_index(name="anomalia_media_c")
        .sort_values("anomalia_media_c", ascending=False)
        .reset_index(drop=True)
    )
    return ranking


def tendencia_decada(rep_celsius):
    """Pendiente lineal °C/década sobre la media espacial del REP."""
    media = rep_celsius.mean(dim=["latitude", "longitude"])
    coef  = media.polyfit(dim="time", deg=1)
    pend_ns = float(coef["polyfit_coefficients"].sel(degree=1))
    ns_por_decada = 1e9 * 60 * 60 * 24 * 365.25 * 10
    return round(pend_ns * ns_por_decada, 3)


# ---------------------------------------------------------------------------
# Conclusiones
# ---------------------------------------------------------------------------

def generar_conclusiones(
    anom_smooth, df_media, ds_rep, clim_por_celda,
    baseline_start, baseline_end,
    nombre, figuras_dir,
):
    """Calcula métricas y escribe conclusiones_chiloe_2026.md en markdown."""

    times          = pd.DatetimeIndex(anom_smooth.time.values)
    anom_vals      = df_media["anomalia_media_c"].values
    rep_celsius    = (ds_rep[VARIABLE] - 273.15)

    # 1. Media general ene–jun 2026
    anom_media_total = round(float(anom_vals.mean()), 2)
    signo_str = "por encima" if anom_media_total > 0 else "por debajo"

    # 2. Peak cálido y frío
    idx_max = int(np.argmax(anom_vals))
    idx_min = int(np.argmin(anom_vals))
    fecha_max, val_max = times[idx_max], round(float(anom_vals[idx_max]), 2)
    fecha_min, val_min = times[idx_min], round(float(anom_vals[idx_min]), 2)

    # 3. % días con anomalía positiva
    pct_pos = round(float((anom_vals > 0).mean()) * 100, 1)

    # 4. MHW en el centroide (reutiliza chiloe_chulin si está disponible)
    csv_centroide = Path("data/sites/chiloe_chulin/site_daily_chiloe_chulin.csv")
    if csv_centroide.exists():
        df_diario = pd.read_csv(csv_centroide, parse_dates=["time"])
        clim_d  = calcular_climatologia_diaria(df_diario, baseline_start, baseline_end)
        df_ev, _ = detectar_eventos_mhw(df_diario, clim_d)
        ev26 = df_ev[df_ev["inicio"] >= "2026-01-01"]
        n_ev      = len(ev26)
        dias_mhw  = int(ev26["duracion_dias"].sum()) if n_ev > 0 else 0
        int_max   = round(float(ev26["intensidad_max_c"].max()), 2) if n_ev > 0 else 0.0
        if n_ev > 0:
            mhw_str = (
                f"Se detectaron **{n_ev} evento(s) de ola de calor marina (MHW)** en el "
                f"centroide de referencia (Chiloé Chulín), con un total de **{dias_mhw} días** "
                f"en condición MHW (SST > percentil 90 climático por ≥ 5 días consecutivos) y "
                f"una intensidad máxima de **+{int_max} °C** sobre la climatología."
            )
        else:
            mhw_str = (
                "No se detectaron eventos de ola de calor marina (MHW) en el centroide de "
                "referencia (Chiloé Chulín) durante el período analizado."
            )
    else:
        mhw_str = (
            "_(Serie diaria del centroide chiloe_chulin no encontrada; "
            "ejecutar `run_site.py` para el análisis de MHW.)_"
        )

    # 5. Ranking histórico ene–jun
    df_rank = ranking_historico(rep_celsius, clim_por_celda)
    anom_2026 = round(float(anom_vals.mean()), 3)
    df_with_2026 = (
        pd.concat(
            [df_rank, pd.DataFrame([{"anio": 2026, "anomalia_media_c": anom_2026}])],
            ignore_index=True,
        )
        .sort_values("anomalia_media_c", ascending=False)
        .reset_index(drop=True)
    )
    pos_2026  = int(df_with_2026[df_with_2026["anio"] == 2026].index[0]) + 1
    n_total   = len(df_with_2026)
    anio_rec  = int(df_rank.iloc[0]["anio"])
    val_rec   = round(float(df_rank.iloc[0]["anomalia_media_c"]), 2)

    # Top-5 para tabla (incluye 2026 si entra)
    top5 = df_with_2026.head(5)

    # 6. Tendencia °C/década
    tend      = tendencia_decada(rep_celsius)
    tend_tipo = "calentamiento" if tend > 0 else "enfriamiento"

    # ─── Redactar markdown ───────────────────────────────────────────────────
    fecha_ini_str = times[0].strftime("%d de %B de %Y")
    fecha_fin_str = times[-1].strftime("%d de %B de %Y")

    top5_rows = "\n".join(
        f"| {int(r['anio'])} | {r['anomalia_media_c']:+.3f} |"
        for _, r in top5.iterrows()
    )

    contenido = f"""# Anomalías térmicas de la SST en el mar interior de Chiloé — Enero–Junio 2026

**Producto:** OSTIA SST L4 (METOFFICE-GLO-SST-L4, 0.05°) · REP (1993-2025) + NRT (2026)
**Período analizado:** {fecha_ini_str} → {fecha_fin_str} ({len(times)} días)
**Referencia climatológica:** {baseline_start}–{baseline_end}
**Área:** Mar interior de Chiloé
(lat {BBOX_LAT[0]}° – {BBOX_LAT[1]}° S · lon {BBOX_LON[0]}° – {BBOX_LON[1]}° W)

---

## Síntesis

La temperatura superficial del mar en el mar interior de Chiloé se mantuvo en promedio
**{anom_media_total:+.2f} °C {signo_str} de la climatología de referencia**
({baseline_start}–{baseline_end}) durante el período enero–junio de 2026.

- **{pct_pos:.0f} %** de los días presentó anomalía media positiva (más cálido que el
  promedio histórico del mismo período).
- El momento **más cálido** del período fue el **{fecha_max.strftime('%d de %B de %Y')}**,
  con una anomalía media de **{val_max:+.2f} °C** sobre la climatología.
- El momento **más frío** fue el **{fecha_min.strftime('%d de %B de %Y')}**,
  con una anomalía de **{val_min:+.2f} °C**.

## Ranking histórico enero–junio (1993–2026)

En comparación con el mismo período enero–junio de todos los años disponibles
(1993–2025 en REP + 2026 con NRT), **2026 ocupa el puesto {pos_2026} de {n_total}**
en la escala de anomalía cálida. El año con la mayor anomalía positiva del registro
es **{anio_rec}** (**{val_rec:+.2f} °C**).

### Top 5 años más cálidos (ene–jun)

| Año | Anomalía (°C) |
|-----|---------------|
{top5_rows}

## Olas de calor marinas (MHW)

{mhw_str}

_(Definición Hobday et al. 2016: SST > percentil 90 climático durante ≥ 5 días
consecutivos; huecos de ≤ 2 días se unen. Centroide Chiloé Chulín, lat -42.63°,
lon -73.05°.)_

## Tendencia de largo plazo

La SST media del mar interior de Chiloé muestra una tendencia de
**{tend:+.3f} °C/década** en el registro REP (1993–2025), consistente con un
{tend_tipo} sostenido del océano en la región.

---

## Metodología

| Parámetro | Valor |
|-----------|-------|
| Producto REP | `METOFFICE-GLO-SST-L4-REP-OBS-SST` |
| Producto NRT | `METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2` |
| Resolución espacial | 0.05° (~5.5 km) |
| Cobertura REP | 1993-01-01 → {REP_FECHA_FIN} |
| Cobertura NRT | {NRT_FECHA_INICIO} → {times[-1]:%Y-%m-%d} |
| Baseline climatológico | {baseline_start}–{baseline_end} |
| Suavizado climatología | Ventana circular de {CLIM_VENTANA} días (±5 días) |
| Suavizado GIF | Media móvil trailing de {ROLLING_DIAS} días por celda |
| Detección MHW | Hobday et al. 2016 (p90, ≥ 5 días, gaps ≤ 2 días) |
| Generado | {date.today().isoformat()} |

---
_Generado automáticamente por `run_chiloe_gif.py`_
"""

    salida = figuras_dir / "conclusiones_chiloe_2026.md"
    salida.write_text(contenido, encoding="utf-8")
    print(f"   ✓ {salida}")
    return salida


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    args           = parsear_argumentos()
    nombre         = args.name
    baseline_start = args.baseline_start
    baseline_end   = args.baseline_end

    data_dir    = SITES_DATA_DIR   / nombre
    figuras_dir = SITES_FIGURES_DIR / nombre
    data_dir.mkdir(parents=True,    exist_ok=True)
    figuras_dir.mkdir(parents=True, exist_ok=True)

    archivo_rep = data_dir / f"rep_{nombre}_sst.nc"
    archivo_nrt = data_dir / f"nrt_{nombre}_sst.nc"
    hoy = date.today().isoformat()

    print(f"🌊  Sitio: {nombre}")
    print(f"    Bbox:  lat {BBOX_LAT}  lon {BBOX_LON}")
    print(f"    Centroide (marca): lat={args.lat}, lon={args.lon}")
    verificar_credenciales()

    # ── 1. Descargas ──────────────────────────────────────────────────────────
    descargar_bbox_preciso(
        DATASET_ID, "REP (1993 → dic-2025)",
        BBOX_LAT[0], BBOX_LAT[1], BBOX_LON[0], BBOX_LON[1],
        FECHA_INICIO, REP_FECHA_FIN,
        archivo_rep, data_dir,
    )
    descargar_bbox_preciso(
        DATASET_ID_NRT, "NRT (2025-dic → hoy)",
        BBOX_LAT[0], BBOX_LAT[1], BBOX_LON[0], BBOX_LON[1],
        NRT_FECHA_INICIO, hoy,
        archivo_nrt, data_dir,
    )

    # ── 2. Cargar y combinar ──────────────────────────────────────────────────
    print("→ Cargando datasets...")
    ds_rep    = xr.open_dataset(archivo_rep)
    ds_nrt    = xr.open_dataset(archivo_nrt)
    combinado = combinar_bbox(ds_rep, ds_nrt)

    rep_celsius  = (ds_rep[VARIABLE]    - 273.15)
    comb_celsius = (combinado[VARIABLE] - 273.15)

    print(f"   ↪ REP:       {str(ds_rep.time.values[0])[:10]} → "
          f"{str(ds_rep.time.values[-1])[:10]}")
    print(f"   ↪ Combinado: {str(combinado.time.values[0])[:10]} → "
          f"{str(combinado.time.values[-1])[:10]}")
    print(f"   ↪ Grid:      {dict(combinado.sizes)}")

    # ── 3. Climatología diaria por celda ─────────────────────────────────────
    print(f"→ Climatología diaria por celda "
          f"(baseline {baseline_start}–{baseline_end}, ventana {CLIM_VENTANA} días)...")
    clim_por_celda = climatologia_diaria_por_celda(
        rep_celsius, baseline_start, baseline_end
    )
    print(f"   ↪ clim dims: {dict(clim_por_celda.sizes)}")

    # ── 4. Anomalía diaria 2026 por celda ────────────────────────────────────
    print("→ Calculando anomalía diaria 2026 por celda...")
    sst_2026 = comb_celsius.sel(time=slice("2026-01-01", "2026-12-31"))
    print(f"   ↪ Días de 2026 disponibles: {len(sst_2026.time)}")

    anom = anomalia_por_celda_2026(sst_2026, clim_por_celda)

    # Media móvil trailing (reduce ruido moteado en el GIF)
    anom_smooth = anom.rolling(time=ROLLING_DIAS, min_periods=1).mean()

    # ── 5. Exportar dataset ───────────────────────────────────────────────────
    print("→ Exportando dataset...")
    guardar_dataset(anom, clim_por_celda, data_dir)
    df_media = guardar_csv_media_diaria(anom_smooth, data_dir)

    # ── 6. Generar GIF ────────────────────────────────────────────────────────
    print("🎨 Generando GIF animado...")
    generar_gif(anom_smooth, args.lat, args.lon, nombre, figuras_dir)

    # ── 7. Conclusiones ───────────────────────────────────────────────────────
    print("📝 Generando conclusiones...")
    generar_conclusiones(
        anom_smooth, df_media, ds_rep, clim_por_celda,
        baseline_start, baseline_end,
        nombre, figuras_dir,
    )

    ds_rep.close()
    ds_nrt.close()

    print(f"\n✅ Listo.")
    print(f"   GIF:         figures/sites/{nombre}/mapa_anomalia_2026_chiloe.gif")
    print(f"   PNG final:   figures/sites/{nombre}/mapa_anomalia_2026_chiloe_final.png")
    print(f"   Dataset:     data/sites/{nombre}/anomalia_diaria_2026.nc")
    print(f"   Conclusiones: figures/sites/{nombre}/conclusiones_chiloe_2026.md")


if __name__ == "__main__":
    main()
