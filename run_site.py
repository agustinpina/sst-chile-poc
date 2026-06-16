"""
Script puntual (one-off) para evaluar un SITIO de centro marino: descarga un
bbox alrededor de un centroide (en vez de la celda única de run_point.py),
combina el producto reprocesado (REP, climatología homogénea 1993→dic-2025)
con el producto casi-en-tiempo-real (NRT, cubre 2026) y genera:

  - mapas espaciales: SST media reciente, anomalía y tendencia °C/década
  - serie temporal de anomalías del centroide extendida a 2026
  - indicadores de ola de calor marina (MHW, Hobday et al. 2016) en el
    centroide: eventos, duración, intensidad y días MHW por año

Reutiliza config.py (DATASET_ID, VARIABLE, FECHA_INICIO) y las figuras de
serie/anomalía de run_point.py — no las reimplementa.

Uso:
    python run_site.py --lat -42.6256807 --lon -73.0538369 --name chiloe_chulin
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import copernicusmarine
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from config import DATASET_ID, FECHA_INICIO, VARIABLE
from mapviz import add_coastline
from run_point import (
    COLOR_NEG, COLOR_POS, DPI,
    figura_anomalia_anual, figura_heatmap_anomalia, figura_serie_anomalia,
)

# El producto REP (reprocesado) no tiene datos más allá de esta fecha (ver
# CLAUDE.md). Para 2026 se usa el producto NRT (near-real-time).
REP_FECHA_FIN = "2025-12-18"
DATASET_ID_NRT = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
# Arranca un poco antes del corte REP para garantizar solape sin huecos.
NRT_FECHA_INICIO = "2025-12-01"

SITES_DATA_DIR = Path("data/sites")
SITES_FIGURES_DIR = Path("figures/sites")

# Marine heatwave (Hobday et al. 2016): evento = SST > percentil 90 climático
# durante >= 5 días consecutivos; eventos separados por <= 2 días se unen.
MHW_PERCENTIL = 0.90
MHW_VENTANA_DIAS = 5
MHW_DURACION_MIN = 5
MHW_GAP_MAX = 2


def parsear_argumentos():
    parser = argparse.ArgumentParser(
        description="Análisis SST de sitio (mapas + anomalías + olas de calor marinas)."
    )
    parser.add_argument("--lat", type=float, default=None,
                        help="Latitud del centroide (requerido en modo centroide).")
    parser.add_argument("--lon", type=float, default=None,
                        help="Longitud del centroide (requerido en modo centroide).")
    parser.add_argument("--name", type=str, default="chiloe_chulin")
    parser.add_argument("--margen", type=float, default=0.30,
                        help="Medio-ancho del bbox en grados alrededor del centroide (default: 0.30). "
                             "Solo en modo centroide.")
    # ponytail: area mode averages spatially (skipna) instead of picking nearest cell;
    #           upgrade to polygon mask only if land contamination becomes measurable.
    parser.add_argument("--modo", choices=["centroide", "area"], default="centroide",
                        help="centroide: celda más cercana al lat/lon; "
                             "area: promedio espacial del bbox completo (skipna=land NaNs out).")
    parser.add_argument("--lat-min", type=float, default=None)
    parser.add_argument("--lat-max", type=float, default=None)
    parser.add_argument("--lon-min", type=float, default=None)
    parser.add_argument("--lon-max", type=float, default=None)
    parser.add_argument("--baseline-start", type=int, default=1993)
    parser.add_argument("--baseline-end", type=int, default=2020)
    return parser.parse_args()


def verificar_credenciales():
    user = os.getenv("COPERNICUSMARINE_SERVICE_USERNAME")
    pwd = os.getenv("COPERNICUSMARINE_SERVICE_PASSWORD")
    if not user or not pwd:
        print("ℹ️  No hay COPERNICUSMARINE_SERVICE_USERNAME/PASSWORD en el entorno;")
        print("   se intentará usar credenciales guardadas (`copernicusmarine login`).")


def descargar_bbox(dataset_id, etiqueta, lat_min, lat_max, lon_min, lon_max,
                    fecha_inicio, fecha_fin, archivo_salida, data_dir):
    if archivo_salida.exists():
        print(f"   ↪ Ya existe {archivo_salida.name}, se reutiliza (no se vuelve a descargar).")
        return
    print(f"→ Descargando {etiqueta} bbox (lat[{lat_min},{lat_max}] lon[{lon_min},{lon_max}], "
          f"{fecha_inicio} → {fecha_fin})...")
    try:
        copernicusmarine.subset(
            dataset_id=dataset_id,
            variables=[VARIABLE],
            minimum_longitude=lon_min,
            maximum_longitude=lon_max,
            minimum_latitude=lat_min,
            maximum_latitude=lat_max,
            start_datetime=f"{fecha_inicio}T00:00:00",
            end_datetime=f"{fecha_fin}T23:59:59",
            output_filename=archivo_salida.name,
            output_directory=str(data_dir),
        )
        tamanio_mb = archivo_salida.stat().st_size / (1024 * 1024)
        print(f"   ✓ {archivo_salida.name} ({tamanio_mb:.1f} MB)")
    except Exception as exc:
        print(f"   ✗ Error al descargar {etiqueta}: {exc}")
        raise


def alinear_grilla(ds_nrt, ds_rep):
    """Reindexa NRT sobre la grilla de REP (mismo producto OSTIA 0.05°,
    pero el subset puede devolver extents/orden ligeramente distintos)."""
    return ds_nrt.reindex(latitude=ds_rep["latitude"], longitude=ds_rep["longitude"],
                          method="nearest", tolerance=1e-3)


def combinar_bbox(ds_rep, ds_nrt):
    """Concatena REP (hasta REP_FECHA_FIN) + NRT (desde el día siguiente) en
    un único cubo espacio-temporal homogéneo en grilla."""
    ds_nrt_alineado = alinear_grilla(ds_nrt, ds_rep)
    corte = pd.Timestamp(REP_FECHA_FIN)
    parte_rep = ds_rep.sel(time=slice(None, corte))
    parte_nrt = ds_nrt_alineado.sel(time=slice(corte + pd.Timedelta(days=1), None))
    return xr.concat([parte_rep, parte_nrt], dim="time")


def serie_diaria_centroide(ds_rep, ds_nrt, lat, lon):
    """Serie diaria del centroide empalmando REP + NRT (sin duplicar fechas)."""
    corte = pd.Timestamp(REP_FECHA_FIN)
    celda_rep = (ds_rep[VARIABLE] - 273.15).sel(latitude=lat, longitude=lon, method="nearest")
    celda_nrt = (ds_nrt[VARIABLE] - 273.15).sel(latitude=lat, longitude=lon, method="nearest")
    lat_celda, lon_celda = float(celda_rep.latitude), float(celda_rep.longitude)

    df_rep = celda_rep.sel(time=slice(None, corte)).to_dataframe(name="sst_celsius").reset_index()
    df_nrt = celda_nrt.sel(time=slice(corte + pd.Timedelta(days=1), None)).to_dataframe(name="sst_celsius").reset_index()
    df = pd.concat([df_rep[["time", "sst_celsius"]], df_nrt[["time", "sst_celsius"]]], ignore_index=True)
    df = df.dropna(subset=["sst_celsius"]).drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    return df, (lat_celda, lon_celda)


def serie_diaria_area(ds_rep, ds_nrt):
    """Serie diaria del área completa (promedio espacial skipna) empalmando REP + NRT.
    skipna=True descarta celdas de tierra/islas que son NaN en analysed_sst."""
    corte = pd.Timestamp(REP_FECHA_FIN)
    sst_rep = (ds_rep[VARIABLE] - 273.15).mean(dim=["latitude", "longitude"], skipna=True)
    sst_nrt = (ds_nrt[VARIABLE] - 273.15).mean(dim=["latitude", "longitude"], skipna=True)
    df_rep = sst_rep.sel(time=slice(None, corte)).to_dataframe(name="sst_celsius").reset_index()
    df_nrt = sst_nrt.sel(time=slice(corte + pd.Timedelta(days=1), None)).to_dataframe(name="sst_celsius").reset_index()
    df = pd.concat([df_rep[["time", "sst_celsius"]], df_nrt[["time", "sst_celsius"]]], ignore_index=True)
    return df.dropna(subset=["sst_celsius"]).drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)


def calcular_mensual_clima_anomalia(df_diario, baseline_start, baseline_end):
    """Resample mensual + climatología (sobre baseline) + anomalía."""
    serie = df_diario.set_index("time")["sst_celsius"]
    mensual = serie.resample("1MS").mean()
    df = mensual.rename("sst_celsius").reset_index()
    df["mes"] = df["time"].dt.month
    df["anio"] = df["time"].dt.year

    base = df[(df["anio"] >= baseline_start) & (df["anio"] <= baseline_end)]
    if base.empty:
        sys.exit(f"❌ El período de referencia {baseline_start}-{baseline_end} "
                 "no tiene datos en la serie descargada.")
    climatologia = base.groupby("mes")["sst_celsius"].mean().rename("clim")

    df = df.merge(climatologia, on="mes", how="left")
    df["anomaly"] = df["sst_celsius"] - df["clim"]
    return df.drop(columns=["mes", "anio"]).sort_values("time").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Mapas espaciales
# ---------------------------------------------------------------------------

def _mapa_base(figsize=(8, 7)):
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={"projection": ccrs.PlateCarree()})
    ax.add_feature(cfeature.BORDERS, linestyle=":", zorder=1)
    ax.gridlines(draw_labels=True, alpha=0.3)
    # Costa GSHHG full (encima del SST, ver mapviz.py): islas y canales
    # del mar interior que Natural Earth 10m no resuelve.
    add_coastline(ax, scale="full", zorder=3)
    return fig, ax


def _marcar_centroide(ax, lat, lon):
    ax.scatter(lon, lat, marker="*", s=220, color="black", edgecolor="white",
               linewidth=1.2, transform=ccrs.PlateCarree(), zorder=5,
               label="Centro marino (centroide)")
    ax.legend(loc="lower left", fontsize=9)


def figura_mapa_sst_media(combinado, lat, lon, nombre, salida_dir):
    ultimo = pd.Timestamp(combinado.time.values[-1])
    desde = ultimo - pd.DateOffset(months=11)
    recientes = (combinado[VARIABLE] - 273.15).sel(time=slice(desde, None))
    media = recientes.mean(dim="time", skipna=True)

    fig, ax = _mapa_base()
    im = media.plot(ax=ax, cmap="RdYlBu_r", transform=ccrs.PlateCarree(), add_colorbar=False)
    fig.colorbar(im, ax=ax, label="SST (°C)", shrink=0.8, pad=0.08)
    _marcar_centroide(ax, lat, lon)
    ax.set_title(f"SST media – últimos 12 meses ({desde:%Y-%m} a {ultimo:%Y-%m})\n"
                 f"{nombre.replace('_', ' ').title()}", fontsize=13)
    salida = salida_dir / "mapa_sst_media.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_mapa_anomalia(ds_rep, combinado, lat, lon, nombre, baseline_start, baseline_end, salida_dir):
    base = ds_rep.sel(time=slice(f"{baseline_start}-01-01", f"{baseline_end}-12-31"))
    clim_por_celda_mes = (base[VARIABLE] - 273.15).groupby("time.month").mean("time")

    ultimo = pd.Timestamp(combinado.time.values[-1])
    desde = ultimo - pd.DateOffset(months=11)
    recientes = (combinado[VARIABLE] - 273.15).sel(time=slice(desde, None))
    anomalia_por_tiempo = recientes.groupby("time.month") - clim_por_celda_mes
    mapa_anomalia = anomalia_por_tiempo.mean(dim="time", skipna=True)

    vmax = float(np.nanmax(np.abs(mapa_anomalia.values))) or 1.0
    fig, ax = _mapa_base()
    im = mapa_anomalia.plot(ax=ax, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                            transform=ccrs.PlateCarree(), add_colorbar=False)
    fig.colorbar(im, ax=ax, label="Anomalía SST (°C)", shrink=0.8, pad=0.08)
    _marcar_centroide(ax, lat, lon)
    ax.set_title(f"Anomalía SST – últimos 12 meses vs. climatología {baseline_start}-{baseline_end}\n"
                 f"{nombre.replace('_', ' ').title()}", fontsize=13)
    salida = salida_dir / "mapa_anomalia.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_mapa_tendencia(ds_rep, lat, lon, nombre, salida_dir):
    """Tendencia °C/década por celda, ajustada solo sobre REP (serie homogénea)."""
    sst = ds_rep[VARIABLE] - 273.15
    coef = sst.polyfit(dim="time", deg=1, skipna=True)
    pendiente_ns = coef["polyfit_coefficients"].sel(degree=1)
    # datetime64[ns] → ns desde época: convertir pendiente a °C/década
    ns_por_decada = 1e9 * 60 * 60 * 24 * 365.25 * 10
    tendencia_decada = pendiente_ns * ns_por_decada

    vmax = float(np.nanmax(np.abs(tendencia_decada.values))) or 0.1
    fig, ax = _mapa_base()
    im = tendencia_decada.plot(ax=ax, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                               transform=ccrs.PlateCarree(), add_colorbar=False)
    fig.colorbar(im, ax=ax, label="Tendencia SST (°C/década)", shrink=0.8, pad=0.08)
    _marcar_centroide(ax, lat, lon)
    anio_ini = int(str(ds_rep.time.values[0])[:4])
    anio_fin = int(str(ds_rep.time.values[-1])[:4])
    ax.set_title(f"Tendencia SST {anio_ini}-{anio_fin} (°C/década)\n"
                 f"{nombre.replace('_', ' ').title()}", fontsize=13)
    salida = salida_dir / "mapa_tendencia.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


# ---------------------------------------------------------------------------
# Ola de calor marina (MHW, Hobday et al. 2016)
# ---------------------------------------------------------------------------

def calcular_climatologia_diaria(df_diario, baseline_start, baseline_end, ventana=MHW_VENTANA_DIAS):
    """Climatología diaria (media y percentil 90) por día-del-año, con ventana
    circular de ±`ventana` días, calculada sobre el período de referencia."""
    df = df_diario.copy()
    df["anio"] = df["time"].dt.year
    df["doy"] = df["time"].dt.dayofyear
    df["doy"] = df["doy"].where(df["doy"] <= 365, 365)  # 29-feb se pliega sobre el día 365

    base = df[(df["anio"] >= baseline_start) & (df["anio"] <= baseline_end)]
    dias = np.arange(1, 366)
    offsets = np.arange(-ventana, ventana + 1)
    medias = np.empty(365)
    percentiles = np.empty(365)
    for i, d in enumerate(dias):
        dias_ventana = ((d - 1 + offsets) % 365) + 1
        sub = base.loc[base["doy"].isin(dias_ventana), "sst_celsius"]
        medias[i] = sub.mean()
        percentiles[i] = sub.quantile(MHW_PERCENTIL)
    return pd.DataFrame({"doy": dias, "clim": medias, "p90": percentiles})


def detectar_eventos_mhw(df_diario, clim_diaria,
                         duracion_min=MHW_DURACION_MIN, gap_max=MHW_GAP_MAX):
    """Detecta eventos MHW: SST > p90 por >= duracion_min días consecutivos,
    uniendo huecos de hasta `gap_max` días (definición Hobday et al. 2016)."""
    df = df_diario.copy()
    df["doy"] = df["time"].dt.dayofyear
    df["doy"] = df["doy"].where(df["doy"] <= 365, 365)
    df = df.merge(clim_diaria, on="doy", how="left").sort_values("time").reset_index(drop=True)
    df["sobre_umbral"] = df["sst_celsius"] > df["p90"]

    grupo = (df["sobre_umbral"] != df["sobre_umbral"].shift()).cumsum()
    runs = (df[df["sobre_umbral"]]
            .groupby(grupo[df["sobre_umbral"]])
            .agg(inicio=("time", "min"), fin=("time", "max"))
            .sort_values("inicio").reset_index(drop=True))

    # Unir runs separados por <= gap_max días
    bloques = []
    for _, r in runs.iterrows():
        if bloques and (r["inicio"] - bloques[-1]["fin"]).days - 1 <= gap_max:
            bloques[-1]["fin"] = r["fin"]
        else:
            bloques.append({"inicio": r["inicio"], "fin": r["fin"]})

    eventos = []
    df["en_evento_mhw"] = False
    for b in bloques:
        duracion = (b["fin"] - b["inicio"]).days + 1
        if duracion < duracion_min:
            continue
        mascara = (df["time"] >= b["inicio"]) & (df["time"] <= b["fin"])
        intensidad = df.loc[mascara, "sst_celsius"] - df.loc[mascara, "clim"]
        df.loc[mascara, "en_evento_mhw"] = True
        umbral_delta = (df.loc[mascara, "p90"] - df.loc[mascara, "clim"]).clip(lower=0.01)
        ratio = intensidad.values / umbral_delta.values
        cat_diaria = np.floor(ratio).clip(1, 4).astype(int)
        eventos.append({
            "inicio": b["inicio"].date().isoformat(),
            "fin": b["fin"].date().isoformat(),
            "duracion_dias": duracion,
            "intensidad_media_c": round(float(intensidad.mean()), 2),
            "intensidad_max_c": round(float(intensidad.max()), 2),
            "categoria_max": int(cat_diaria.max()),
            "dias_cat2plus": int((cat_diaria >= 2).sum()),
        })
    return pd.DataFrame(eventos), df


def figura_mhw_serie(df_mhw, nombre, anios_recientes, salida_dir):
    ultimo = df_mhw["time"].max()
    desde = ultimo - pd.DateOffset(years=anios_recientes)
    sub = df_mhw[df_mhw["time"] >= desde]

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(sub["time"], sub["sst_celsius"], color="black", lw=0.9, label="SST diaria")
    ax.plot(sub["time"], sub["clim"], color="gray", lw=1.2, ls="--", label="Climatología diaria")
    ax.plot(sub["time"], sub["p90"], color=COLOR_POS, lw=1.2, ls=":",
            label=f"Umbral MHW (percentil {int(MHW_PERCENTIL*100)})")
    en_evento = sub["en_evento_mhw"]
    ax.fill_between(sub["time"], sub["sst_celsius"], sub["p90"],
                    where=en_evento, color=COLOR_POS, alpha=0.35,
                    interpolate=True, label="Evento MHW")
    ax.set_title(f"Detección de olas de calor marinas (MHW) – {nombre}\n"
                 f"(últimos {anios_recientes} años, definición Hobday et al. 2016)")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("SST (°C)")
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.3)
    salida = salida_dir / "mhw_serie.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_mhw_anual(df_mhw, nombre, salida_dir):
    anual = (df_mhw.assign(anio=df_mhw["time"].dt.year)
             .groupby("anio")["en_evento_mhw"].sum().reset_index(name="dias_mhw"))
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(anual["anio"], anual["dias_mhw"], color=COLOR_POS, alpha=0.8)
    ax.set_title(f"Días en evento de ola de calor marina (MHW) por año – {nombre}")
    ax.set_xlabel("Año")
    ax.set_ylabel("Días MHW")
    ax.grid(alpha=0.3, axis="y")
    salida = salida_dir / "mhw_anual.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def main():
    args = parsear_argumentos()
    nombre = args.name

    # Resolver bbox y display lat/lon según modo
    if args.modo == "area":
        for flag in ("lat_min", "lat_max", "lon_min", "lon_max"):
            if getattr(args, flag) is None:
                sys.exit(f"❌ --modo area requiere --{flag.replace('_', '-')}.")
        lat_min, lat_max = args.lat_min, args.lat_max
        lon_min, lon_max = args.lon_min, args.lon_max
        display_lat = (lat_min + lat_max) / 2
        display_lon = (lon_min + lon_max) / 2
    else:
        if args.lat is None or args.lon is None:
            sys.exit("❌ --modo centroide requiere --lat y --lon.")
        lat_min = args.lat - args.margen
        lat_max = args.lat + args.margen
        lon_min = args.lon - args.margen
        lon_max = args.lon + args.margen
        display_lat, display_lon = args.lat, args.lon

    data_dir = SITES_DATA_DIR / nombre
    figuras_dir = SITES_FIGURES_DIR / nombre
    data_dir.mkdir(parents=True, exist_ok=True)
    figuras_dir.mkdir(parents=True, exist_ok=True)

    archivo_rep = data_dir / f"rep_{nombre}_sst.nc"
    archivo_nrt = data_dir / f"nrt_{nombre}_sst.nc"
    hoy = date.today().isoformat()

    print(f"📍 Sitio: {nombre} (modo={args.modo}, "
          f"bbox lat[{lat_min},{lat_max}] lon[{lon_min},{lon_max}])")
    verificar_credenciales()
    descargar_bbox(DATASET_ID, "REP (1993→dic-2025)",
                   lat_min, lat_max, lon_min, lon_max,
                   FECHA_INICIO, REP_FECHA_FIN, archivo_rep, data_dir)
    descargar_bbox(DATASET_ID_NRT, "NRT (2026, near-real-time)",
                   lat_min, lat_max, lon_min, lon_max,
                   NRT_FECHA_INICIO, hoy, archivo_nrt, data_dir)

    print(f"→ Procesando {nombre}...")
    ds_rep = xr.open_dataset(archivo_rep)
    ds_nrt = xr.open_dataset(archivo_nrt)
    combinado = combinar_bbox(ds_rep, ds_nrt)

    if args.modo == "area":
        df_diario = serie_diaria_area(ds_rep, ds_nrt)
        print(f"   ↪ Modo área: promedio espacial de {df_diario['time'].min():%Y-%m-%d} "
              f"→ {df_diario['time'].max():%Y-%m-%d} ({len(df_diario)} días)")
    else:
        df_diario, celda = serie_diaria_centroide(ds_rep, ds_nrt, args.lat, args.lon)
        display_lat, display_lon = celda
        print(f"   ↪ Celda del centroide: lat={display_lat:.3f}, lon={display_lon:.3f}")
        print(f"   ↪ Serie diaria: {df_diario['time'].min():%Y-%m-%d} → {df_diario['time'].max():%Y-%m-%d} "
              f"({len(df_diario)} días)")

    salida_diaria = data_dir / f"site_daily_{nombre}.csv"
    df_diario.to_csv(salida_diaria, index=False)
    print(f"   ✓ {salida_diaria.name} ({len(df_diario)} filas)")

    df_mensual = calcular_mensual_clima_anomalia(df_diario, args.baseline_start, args.baseline_end)
    salida_mensual = data_dir / f"site_monthly_{nombre}.csv"
    df_mensual.to_csv(salida_mensual, index=False)
    print(f"   ✓ {salida_mensual.name} ({len(df_mensual)} filas)")

    print("🎨 Generando mapas espaciales...")
    figura_mapa_sst_media(combinado, display_lat, display_lon, nombre, figuras_dir)
    figura_mapa_anomalia(ds_rep, combinado, display_lat, display_lon, nombre,
                         args.baseline_start, args.baseline_end, figuras_dir)
    figura_mapa_tendencia(ds_rep, display_lat, display_lon, nombre, figuras_dir)

    print("🎨 Generando serie de anomalías...")
    figura_serie_anomalia(df_mensual, nombre, args.baseline_start, args.baseline_end, figuras_dir)
    figura_heatmap_anomalia(df_mensual, nombre, figuras_dir)
    figura_anomalia_anual(df_mensual, nombre, figuras_dir)

    print("🌡️  Detectando olas de calor marinas (MHW)...")
    clim_diaria = calcular_climatologia_diaria(df_diario, args.baseline_start, args.baseline_end)
    df_eventos, df_mhw = detectar_eventos_mhw(df_diario, clim_diaria)
    salida_eventos = data_dir / f"mhw_eventos_{nombre}.csv"
    df_eventos.to_csv(salida_eventos, index=False)
    print(f"   ✓ {salida_eventos.name} ({len(df_eventos)} eventos detectados)")
    figura_mhw_serie(df_mhw, nombre, anios_recientes=4, salida_dir=figuras_dir)
    figura_mhw_anual(df_mhw, nombre, figuras_dir)

    ds_rep.close()
    ds_nrt.close()

    print(f"\n✅ Listo. Datos en {data_dir}/, figuras en {figuras_dir}/")


if __name__ == "__main__":
    main()
