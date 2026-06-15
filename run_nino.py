"""
run_nino.py — Pieza para redes: "El Niño 2026 y la salmonicultura de Chiloé".

Genera las figuras de un carrusel (5 slides verticales 1080x1350) + GIF para
comunicar a la industria/veterinarios qué implica el Aviso de El Niño emitido
por NOAA el 11-jun-2026 para la salmonicultura de Chiloé, con foco en los
casos documentados de 2016 (Pseudochattonella, El Niño + SAM+) y 2021
(Heterosigma, La Niña + SAM+).

Encuadre obligatorio (ver docs/El Niño Effects on Chilean salmon aquaculture.md):
  1. No afirmar "El Niño ya empezó" — se trata de un Aviso con pronóstico de
     intensificación hacia fines de 2026.
  2. El Niño NO equivale a mortandad: 2021 (>6.000 t) ocurrió en La Niña.
     El mensaje es "sube la probabilidad" (vía calor/estratificación/baja
     escorrentía), no causalidad directa.
  3. Mecanismo hidroclimático, no térmico-directo (gatilla FAN, comprime el
     ciclo de Caligus, agrava SRS por estrés/hipoxia).

Reutiliza:
  - data/sites/chiloe_chulin/site_monthly_chiloe_chulin.csv (serie 1993-2026)
  - data/sites/chiloe_chulin/mhw_eventos_chiloe_chulin.csv (eventos MHW)
  - data/sites/chiloe_mar_interior/rep_chiloe_mar_interior_sst.nc (mapas 2016/2021)
  - figures/sites/chiloe_mar_interior/mapa_anomalia_2026_chiloe.gif (ya vigente
    al 2026-06-13, se reutiliza sin recalcular)
  - run_chiloe_gif.climatologia_diaria_por_celda / anomalia_por_celda_2026
  - run_point.COLOR_POS / COLOR_NEG / DPI
  - mapviz.add_coastline

Nuevo dato externo: índice ONI de NOAA CPC (oni.ascii.txt), cacheado en
data/nino/oni.csv.

Uso:
    python run_nino.py
"""
import shutil
import sys
import urllib.request
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.patches import Patch, Rectangle

from config import VARIABLE
from mapviz import add_coastline
from run_point import COLOR_NEG, COLOR_POS, DPI
from run_chiloe_gif import (
    BASELINE_END,
    BASELINE_START,
    anomalia_por_celda_2026,
    climatologia_diaria_por_celda,
)

# ---------------------------------------------------------------------------
# Rutas y constantes
# ---------------------------------------------------------------------------
SITE_NAME = "chiloe_chulin"
SITE_DATA_DIR = Path("data/sites") / SITE_NAME
SITE_MONTHLY_CSV = SITE_DATA_DIR / f"site_monthly_{SITE_NAME}.csv"
MHW_EVENTS_CSV = SITE_DATA_DIR / f"mhw_eventos_{SITE_NAME}.csv"

MAR_INTERIOR_DIR = Path("data/sites/chiloe_mar_interior")
MAR_INTERIOR_REP_NC = MAR_INTERIOR_DIR / "rep_chiloe_mar_interior_sst.nc"

GIF_ORIGEN = Path("figures/sites/chiloe_mar_interior/mapa_anomalia_2026_chiloe.gif")
PNG_FINAL_ORIGEN = Path("figures/sites/chiloe_mar_interior/mapa_anomalia_2026_chiloe_final.png")

DATA_NINO_DIR = Path("data/nino")
FIGURES_NINO_DIR = Path("figures/nino_2026")
ONI_CACHE = DATA_NINO_DIR / "oni.csv"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

COLOR_NEUTRAL = "#cccccc"
COLOR_MHW = "#ff8c00"

# Coordenadas de los fiordos emblemáticos (para marcar en los mapas)
RELONCAVI = (-41.65, -72.55)   # Seno de Reloncaví (bloom Pseudochattonella, 2016)
COMAU = (-42.35, -72.50)       # Fiordo Comau (bloom Heterosigma, 2021)

# Mapeo de las 12 "temporadas" solapadas de 3 meses del ONI a un mes
# representativo dentro de YR (centro de la temporada).
SEAS_MES_CENTRO = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}

SLIDE_W_IN, SLIDE_H_IN = 7.2, 9.0  # 1080x1350 px @150dpi
SLIDE_DPI = 150


# ---------------------------------------------------------------------------
# 1. Índice ONI (NOAA CPC)
# ---------------------------------------------------------------------------

def clasificar_fase(anom):
    if anom >= 0.5:
        return "El Niño"
    if anom <= -0.5:
        return "La Niña"
    return "Neutral"


def descargar_oni():
    """Descarga (o reutiliza caché de) la serie ONI de NOAA CPC."""
    if ONI_CACHE.exists():
        print(f"   ↪ Ya existe {ONI_CACHE}, se reutiliza (no se vuelve a descargar).")
        return pd.read_csv(ONI_CACHE, parse_dates=["time"])

    print(f"→ Descargando índice ONI desde NOAA CPC ({ONI_URL})...")
    try:
        with urllib.request.urlopen(ONI_URL, timeout=30) as resp:
            texto = resp.read().decode("utf-8")
    except Exception as exc:
        sys.exit(f"❌ No se pudo descargar el índice ONI ({exc}) y no hay caché en {ONI_CACHE}.")

    filas = []
    for linea in texto.strip().splitlines()[1:]:
        partes = linea.split()
        if len(partes) != 4:
            continue
        seas, yr, total, anom = partes
        mes = SEAS_MES_CENTRO.get(seas)
        if mes is None:
            continue
        filas.append({
            "time": pd.Timestamp(year=int(yr), month=mes, day=1),
            "seas": seas,
            "total_c": float(total),
            "anom": float(anom),
        })

    df = pd.DataFrame(filas).sort_values("time").reset_index(drop=True)
    df["fase"] = df["anom"].apply(clasificar_fase)

    DATA_NINO_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(ONI_CACHE, index=False)
    print(f"   ✓ {ONI_CACHE} ({len(df)} filas, "
          f"{df['time'].min():%Y-%m} → {df['time'].max():%Y-%m})")
    return df


def construir_spans_fase(df_oni, fases=("El Niño", "La Niña")):
    """Agrupa filas mensuales consecutivas de la misma fase ENSO en
    intervalos [inicio, fin) para sombrear con axvspan."""
    df = df_oni.sort_values("time").reset_index(drop=True)
    spans = []
    actual = None
    for _, row in df.iterrows():
        fase = row["fase"]
        inicio = row["time"]
        fin = inicio + pd.DateOffset(months=1)
        if fase in fases:
            if actual is not None and actual["fase"] == fase and actual["fin"] == inicio:
                actual["fin"] = fin
            else:
                if actual is not None:
                    spans.append(actual)
                actual = {"fase": fase, "inicio": inicio, "fin": fin}
        else:
            if actual is not None:
                spans.append(actual)
                actual = None
    if actual is not None:
        spans.append(actual)
    return spans


# ---------------------------------------------------------------------------
# 2. Figura (e): barras ONI rojo/azul
# ---------------------------------------------------------------------------

def figura_barra_oni(df_oni, anio_inicio, anio_fin, archivo_salida, anotaciones=None,
                     titulo="Índice Oceánico El Niño (ONI) — NOAA CPC"):
    df = df_oni[(df_oni["time"].dt.year >= anio_inicio) & (df_oni["time"].dt.year <= anio_fin)].copy()
    color_map = {"El Niño": COLOR_POS, "La Niña": COLOR_NEG, "Neutral": COLOR_NEUTRAL}
    colores = df["fase"].map(color_map)

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(df["time"], df["anom"], width=25, color=colores)
    ax.axhline(0, color="black", lw=0.8)
    ax.axhline(0.5, color=COLOR_POS, lw=0.8, ls=":", alpha=0.6)
    ax.axhline(-0.5, color=COLOR_NEG, lw=0.8, ls=":", alpha=0.6)

    if anotaciones:
        for an in anotaciones:
            ax.axvline(an["time"], color="#333333", lw=1.0, ls="--", alpha=0.7)
            ax.annotate(an["texto"], xy=(an["time"], an["y"]), xytext=an["xytext"],
                         fontsize=9, ha=an.get("ha", "center"),
                         arrowprops=dict(arrowstyle="->", color="#333333", lw=0.8),
                         bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#999999", alpha=0.92))

    legend_handles = [
        Patch(facecolor=COLOR_POS, label="El Niño (ONI ≥ +0.5 °C)"),
        Patch(facecolor=COLOR_NEG, label="La Niña (ONI ≤ −0.5 °C)"),
        Patch(facecolor=COLOR_NEUTRAL, label="Neutral"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=9)
    ax.set_title(f"{titulo}\n({anio_inicio}–{anio_fin})", fontsize=13)
    ax.set_xlabel("Año")
    ax.set_ylabel("Anomalía ONI (°C)")
    ax.grid(alpha=0.3, axis="y")
    fig.text(0.01, 0.01,
             "Fuente: NOAA CPC, oni.ascii.txt (ERSSTv5, base 1991–2020). "
             "El ONI es el predecesor del RONI (oficial desde feb-2026); "
             "ambos pueden diferir ~0.1–0.5 °C.",
             fontsize=7.5, color="#555555")

    salida = FIGURES_NINO_DIR / archivo_salida
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


# ---------------------------------------------------------------------------
# 3. Figura centerpiece: overlay anomalía SST + fases ENSO + eventos FAN
# ---------------------------------------------------------------------------

def figura_overlay_centerpiece(df_mensual, df_oni, df_mhw):
    fig, ax = plt.subplots(figsize=(14, 7))

    # --- Fondo: fases ENSO (sombreado rojo/azul) -----------------------------
    df_oni_recorte = df_oni[df_oni["time"] >= df_mensual["time"].min()]
    spans = construir_spans_fase(df_oni_recorte)
    color_fase = {"El Niño": COLOR_POS, "La Niña": COLOR_NEG}
    for s in spans:
        ax.axvspan(s["inicio"], s["fin"], color=color_fase[s["fase"]],
                   alpha=0.10, lw=0, zorder=0)

    # --- Barras de anomalía SST mensual --------------------------------------
    colores = np.where(df_mensual["anomaly"] >= 0, COLOR_POS, COLOR_NEG)
    ax.bar(df_mensual["time"], df_mensual["anomaly"], width=25,
           color=colores, alpha=0.75, zorder=2)

    # --- Media móvil 12 meses --------------------------------------------------
    media_movil = df_mensual["anomaly"].rolling(window=12, min_periods=12).mean()
    ax.plot(df_mensual["time"], media_movil, color="black", lw=1.8, zorder=3)

    # --- Rug de eventos MHW (Hobday et al. 2016) -----------------------------
    for _, ev in df_mhw.iterrows():
        ax.axvspan(ev["inicio"], ev["fin"] + pd.Timedelta(days=1),
                   ymin=0.0, ymax=0.035, color=COLOR_MHW, alpha=0.9, zorder=4)

    ax.axhline(0, color="black", lw=0.8, zorder=1)
    ax.set_ylim(-1.55, 1.6)

    # --- Anotaciones: casos ancla 2016 y 2021 ---------------------------------
    def _valor(fecha):
        fila = df_mensual.loc[df_mensual["time"] == pd.Timestamp(fecha), "anomaly"]
        return float(fila.values[0]) if not fila.empty else 0.0

    ax.annotate(
        "2016 — Pseudochattonella: >40.000 t (~12%\n"
        "de la producción), >US$800M.\n"
        "El Niño fuerte + SAM positivo → verano\n"
        "cálido, seco y estratificado.",
        xy=(pd.Timestamp("2016-02-01"), _valor("2016-02-01")),
        xytext=(pd.Timestamp("1996-06-01"), 1.05),
        fontsize=8.5, ha="left", va="center",
        arrowprops=dict(arrowstyle="->", color="#333333", lw=0.9),
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOR_POS, alpha=0.95),
        zorder=6,
    )

    ax.annotate(
        "2021 — Heterosigma: >6.000 t\n"
        "(~US$4,4M, 12 centros).\n"
        "Ocurrió en LA NIÑA — mandó el SAM\n"
        "positivo (2° verano más seco en 70 años).",
        xy=(pd.Timestamp("2021-04-01"), _valor("2021-04-01")),
        xytext=(pd.Timestamp("2007-09-01"), -1.30),
        fontsize=8.5, ha="left", va="center",
        arrowprops=dict(arrowstyle="->", color="#333333", lw=0.9),
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=COLOR_NEG, alpha=0.95),
        zorder=6,
    )

    # --- Anotación: aviso 2026 (sin extrapolar la curva) ----------------------
    ax.text(
        0.99, 0.96,
        "Aviso El Niño NOAA (11-jun-2026):\n"
        "Niño-3.4 sem. +0.7 °C; RONI MAM +0.4 °C.\n"
        "63% prob. evento MUY FUERTE en NDJ\n"
        "2026–27 — coincide con ventana FAN dic–abr.",
        transform=ax.transAxes, fontsize=8, ha="right", va="top",
        bbox=dict(boxstyle="round,pad=0.35", fc="#fff8e1", ec="#cc9900", alpha=0.9),
        zorder=6,
    )

    ax.set_title(
        "Anomalía SST mensual + fases ENSO + eventos FAN — Chiloé Chulín (1993–2026)\n"
        "Referencia climatológica 1993–2020 · Producto OSTIA 0.05° (REP + NRT)",
        fontsize=13,
    )
    ax.set_xlabel("Año")
    ax.set_ylabel("Anomalía SST (°C)")
    ax.grid(alpha=0.25)

    # --- Leyenda manual (debajo del gráfico, fuera del área de datos) ----------
    legend_handles = [
        Patch(facecolor=COLOR_POS, alpha=0.75, label="Anomalía SST > 0"),
        Patch(facecolor=COLOR_NEG, alpha=0.75, label="Anomalía SST < 0"),
        plt.Line2D([0], [0], color="black", lw=1.8, label="Media móvil 12 meses"),
        Patch(facecolor=COLOR_POS, alpha=0.10, label="Fase El Niño (ONI)"),
        Patch(facecolor=COLOR_NEG, alpha=0.10, label="Fase La Niña (ONI)"),
        Patch(facecolor=COLOR_MHW, alpha=0.9, label="Días en MHW (Hobday et al. 2016)"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", bbox_to_anchor=(0.5, -0.06),
               fontsize=9, ncol=3, frameon=False)

    fig.text(0.01, -0.15,
             "Fuentes: Copernicus Marine METOFFICE-GLO-SST-L4 (OSTIA) · NOAA CPC ONI · "
             "MHW: Hobday et al. (2016) · "
             "Eventos FAN: León-Muñoz et al. (2018), Mardones et al. (2021, 2022), Díaz et al. (2023). "
             "La fase ENSO no implica causalidad directa con los eventos FAN: SAM, escorrentía y "
             "retención del fiordo son co-determinantes.",
             fontsize=7.5, color="#555555", wrap=True)

    fig.subplots_adjust(bottom=0.28)
    salida = FIGURES_NINO_DIR / "anomalia_enso_overlay.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


# ---------------------------------------------------------------------------
# 4. Mapas de anomalía SST — episodios 2016 y 2021 (mar interior de Chiloé)
# ---------------------------------------------------------------------------

def calcular_mapa_anomalia_periodo(rep_celsius, clim_por_celda, fecha_ini, fecha_fin):
    sst_periodo = rep_celsius.sel(time=slice(fecha_ini, fecha_fin))
    anom = anomalia_por_celda_2026(sst_periodo, clim_por_celda)
    return anom.mean(dim="time", skipna=True)


def plot_mapa_anomalia(mapa, vmax, titulo, marca, etiqueta_marca, salida_path):
    fig, ax = plt.subplots(figsize=(8, 7), subplot_kw={"projection": ccrs.PlateCarree()})
    ax.add_feature(cfeature.OCEAN, facecolor="#d0e8f5", zorder=0)
    im = mapa.plot(ax=ax, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                   transform=ccrs.PlateCarree(), add_colorbar=False, zorder=1)
    add_coastline(ax, scale="full", zorder=3)
    ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.6, zorder=3)
    gl = ax.gridlines(draw_labels=True, alpha=0.3, zorder=2, linewidth=0.5, color="gray")
    gl.top_labels = False
    gl.right_labels = False
    fig.colorbar(im, ax=ax, label="Anomalía SST (°C)", shrink=0.75, pad=0.08)

    lat_m, lon_m = marca
    ax.scatter(lon_m, lat_m, marker="*", s=220, color="black", edgecolor="white",
               linewidth=1.2, transform=ccrs.PlateCarree(), zorder=5, label=etiqueta_marca)
    ax.legend(loc="lower left", fontsize=9)
    ax.set_title(titulo, fontsize=12)

    fig.savefig(salida_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida_path}")


def generar_mapas_episodios():
    print(f"   → Cargando {MAR_INTERIOR_REP_NC} (REP 1993–2025)...")
    ds_rep = xr.open_dataset(MAR_INTERIOR_REP_NC)
    rep_celsius = ds_rep[VARIABLE] - 273.15

    print(f"   → Climatología diaria por celda (baseline {BASELINE_START}–{BASELINE_END})...")
    clim = climatologia_diaria_por_celda(rep_celsius, BASELINE_START, BASELINE_END)

    mapa_2016 = calcular_mapa_anomalia_periodo(rep_celsius, clim, "2016-02-01", "2016-03-31")
    mapa_2021 = calcular_mapa_anomalia_periodo(rep_celsius, clim, "2021-03-01", "2021-04-30")

    vmax = max(
        float(np.nanpercentile(np.abs(mapa_2016.values), 98)),
        float(np.nanpercentile(np.abs(mapa_2021.values), 98)),
        0.5,
    )
    vmax = round(vmax, 1)

    plot_mapa_anomalia(
        mapa_2016, vmax,
        "Anomalía SST feb–mar 2016 — Mar interior de Chiloé\n"
        "(El Niño fuerte + SAM+ → bloom de Pseudochattonella en Reloncaví)",
        RELONCAVI, "Seno de Reloncaví",
        FIGURES_NINO_DIR / "anom_mapa_2016.png",
    )
    plot_mapa_anomalia(
        mapa_2021, vmax,
        "Anomalía SST mar–abr 2021 — Mar interior de Chiloé\n"
        "(La Niña + SAM+ → bloom de Heterosigma en Comau)",
        COMAU, "Fiordo Comau",
        FIGURES_NINO_DIR / "anom_mapa_2021.png",
    )
    ds_rep.close()


# ---------------------------------------------------------------------------
# 5. Slides del carrusel (1080x1350)
# ---------------------------------------------------------------------------

def crear_slide(numero, titulo, cuerpo, archivo_salida, imagen=None,
                color_acento=COLOR_POS, pie=None, frac_imagen=0.58):
    fig = plt.figure(figsize=(SLIDE_W_IN, SLIDE_H_IN))

    if imagen is not None:
        ax_img = fig.add_axes([0.0, 1.0 - frac_imagen, 1.0, frac_imagen])
        img = mpimg.imread(imagen)
        ax_img.imshow(img, aspect="auto")
        ax_img.axis("off")
        ax_text = fig.add_axes([0.06, 0.03, 0.88, 0.97 - frac_imagen])
    else:
        ax_text = fig.add_axes([0.06, 0.04, 0.88, 0.92])

    ax_text.set_xlim(0, 1)
    ax_text.set_ylim(0, 1)
    ax_text.axis("off")

    # Barra de acento
    ax_text.add_patch(Rectangle((0, 0.97), 0.16, 0.025, transform=ax_text.transAxes,
                                color=color_acento, clip_on=False))
    ax_text.text(0, 0.90, titulo, transform=ax_text.transAxes, fontsize=16,
                 fontweight="bold", va="top", ha="left")
    ax_text.text(0, 0.78, cuerpo, transform=ax_text.transAxes, fontsize=10.5,
                 va="top", ha="left", linespacing=1.55)

    if pie:
        ax_text.text(0, 0.0, pie, transform=ax_text.transAxes, fontsize=7,
                     va="bottom", ha="left", color="#666666")

    fig.text(0.95, 0.985, f"{numero}/5", fontsize=11, ha="right", va="top",
            color="#999999", fontweight="bold")
    fig.text(0.05, 0.985, "El Niño 2026 y la salmonicultura de Chiloé",
            fontsize=8, ha="left", va="top", color="#999999")

    fig.savefig(archivo_salida, dpi=SLIDE_DPI)
    plt.close(fig)
    print(f"   ✓ {archivo_salida}")


CITA_DATOS = (
    "Datos: Copernicus Marine OSTIA 0.05° (REP+NRT) · NOAA CPC ONI · "
    "Baseline climatológico 1993–2020."
)
CITA_BIBLIO = (
    "Fuentes: León-Muñoz et al. 2018 (Sci Rep); Mardones et al. 2021/2022\n"
    "(Sci Total Environ / Harmful Algae); Díaz et al. 2023 (Sci Total Environ); Hobday et al. 2016/2018."
)


def crear_slides(df_mensual):
    FIGURES_NINO_DIR.mkdir(parents=True, exist_ok=True)

    ultimo = df_mensual.iloc[-1]
    fecha_ultimo = pd.Timestamp(ultimo["time"]).strftime("%B %Y")

    # --- Slide 1: Gancho -------------------------------------------------------
    crear_slide(
        1,
        "El Niño 2026:\nNOAA emitió Aviso el 11-jun",
        "• NOAA/CPC: \"El Niño conditions are present and\n"
        "  expected to strengthen into NH winter 2026-27\"\n\n"
        "• Niño-3.4 semanal: +0.7 °C (aún débil)\n\n"
        "• Pronóstico: 63% de probabilidad de evento\n"
        "  MUY FUERTE (RONI ≥ 2.0 °C) en nov-dic-ene\n"
        "  2026–27\n\n"
        "• Ese peak coincide con la ventana de floraciones\n"
        f"  algales nocivas (FAN) dic–abr en Chile\n\n"
        "  No es \"ya llegó\" — es \"viene fuerte y a\n"
        "  tiempo para la temporada de riesgo\".",
        FIGURES_NINO_DIR / "slide_01_gancho.png",
        imagen=FIGURES_NINO_DIR / "barra_oni_zoom.png",
        color_acento=COLOR_POS,
        pie=CITA_DATOS,
        frac_imagen=0.42,
    )

    # --- Slide 2: 2016 ----------------------------------------------------------
    crear_slide(
        2,
        "El antecedente: 2016",
        "Floración de Pseudochattonella cf. verruculosa\n"
        "(Reloncaví, feb–mar 2016)\n\n"
        "• >40.000 t perdidas (~12% de la producción\n"
        "  nacional del semestre)\n"
        "• >US$800 millones en pérdidas\n"
        "• Detonó la crisis social \"Mayo Chilote\"\n\n"
        "¿Qué lo gatilló?\n"
        "El Niño FUERTE + SAM positivo (combinación\n"
        "estadísticamente inusual) → verano cálido, seco,\n"
        "soleado y de baja escorrentía → se debilitó la\n"
        "capa superficial de agua dulce → entrada de agua\n"
        "salina rica en nutrientes + fuerte estratificación\n"
        "→ floración en capa fina que persistió semanas.",
        FIGURES_NINO_DIR / "slide_02_2016.png",
        imagen=FIGURES_NINO_DIR / "anom_mapa_2016.png",
        color_acento=COLOR_POS,
        pie=CITA_BIBLIO,
        frac_imagen=0.48,
    )

    # --- Slide 3: 2021 (La Niña) ------------------------------------------------
    crear_slide(
        3,
        "Pero ojo: 2021 fue La Niña",
        "Floración de Heterosigma akashiwo\n"
        "(Fiordo Comau, mar–abr 2021)\n\n"
        "• >6.000 t perdidas en 12 centros (~US$4,4M)\n"
        "• Ocurrió con ONI ≈ −0.9 °C (La Niña)\n\n"
        "¿Qué mandó? El SAM positivo (>1.2 hPa) superó\n"
        "la señal de La Niña: 2° verano más seco en 70\n"
        "años, sequía, alta retención del fiordo.\n\n"
        "Mensaje clave para la pieza:\n"
        "El Niño AUMENTA LA PROBABILIDAD de un verano\n"
        "cálido/seco/estratificado — no es sinónimo de\n"
        "mortandad, ni La Niña es \"zona segura\". Hay\n"
        "que vigilar SAM y caudal de ríos junto al ENSO.",
        FIGURES_NINO_DIR / "slide_03_2021.png",
        imagen=FIGURES_NINO_DIR / "anom_mapa_2021.png",
        color_acento=COLOR_NEG,
        pie=CITA_BIBLIO,
        frac_imagen=0.48,
    )

    # --- Slide 4: Centerpiece -----------------------------------------------------
    crear_slide(
        4,
        "33 años de anomalías SST,\nfases ENSO y eventos FAN",
        "Chiloé Chulín, 1993–2026 (climatología 1993–2020).\n\n"
        "• Barras rojas/azules: anomalía SST mensual\n"
        "• Línea negra: media móvil 12 meses\n"
        "• Sombreado rojo/azul: fases El Niño/La Niña (ONI)\n"
        "• Franjas naranjas: días en ola de calor marina\n"
        "  (MHW, Hobday et al. 2016)\n\n"
        "2016 y 2021 quedan marcados con su fase ENSO real\n"
        "y el mecanismo (SAM) que los gatilló.\n\n"
        "Versión animada: anomalia_2026_chiloe.gif — muestra\n"
        f"la evolución espacial de la anomalía SST 2026 hasta\n"
        f"{fecha_ultimo} en el mar interior de Chiloé.",
        FIGURES_NINO_DIR / "slide_04_centerpiece.png",
        imagen=FIGURES_NINO_DIR / "anomalia_enso_overlay.png",
        color_acento=COLOR_POS,
        pie=CITA_DATOS,
        frac_imagen=0.46,
    )

    # --- Slide 5: Qué esperar / qué hacer ---------------------------------------
    crear_slide(
        5,
        "¿Qué esperar y qué hacer\nahora?",
        "Invierno 2026 (ahora–sep): preparar\n"
        "• Levantar la línea base de tu(s) sitio(s):\n"
        "  anomalía SST + eventos MHW históricos (2016,\n"
        "  2021 como referencia)\n"
        "• Reforzar el monitoreo FAN (CREAN i-FAN)\n\n"
        "Primavera–verano 2026–27 (oct–abr): vigilar\n"
        "• Seguir CHONOS MOSA/PARTI-MOSA + i-FAN a diario\n"
        "• Señal de máximo riesgo: MHW categoría II+ EN\n"
        "  EL SITIO + SAM positivo + bajo caudal de ríos\n"
        "  (CHONOS FLOW) — la \"huella\" de 2016 y 2021\n\n"
        "Acciones a pre-posicionar\n"
        "• Oxigenación/aireación, lonas/skirts, plan de cosecha\n"
        "  de emergencia\n"
        "• Adelantar tratamientos de Caligus (ciclo: ~45 d\n"
        "  a 10 °C vs ~26 d a 15 °C — se acorta con calor)\n"
        "• Alinear vacunación/siembra SRS al calendario\n"
        "  térmico (eficacia de vacunas vivas es sensible\n"
        "  a temperatura)",
        FIGURES_NINO_DIR / "slide_05_acciones.png",
        imagen=FIGURES_NINO_DIR / "mhw_anual_chiloe_chulin.png",
        color_acento=COLOR_NEG,
        pie="Fuentes: IFOP-CHONOS (chonos.ifop.cl), CREAN-IFOP i-FAN, "
            "González & Carvajal 2003, Rozas-Serri 2022.\n" + CITA_DATOS,
        frac_imagen=0.38,
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("run_nino.py — 'El Niño 2026 y la salmonicultura de Chiloé'")
    print("=" * 72)

    FIGURES_NINO_DIR.mkdir(parents=True, exist_ok=True)
    DATA_NINO_DIR.mkdir(parents=True, exist_ok=True)

    print("\n1. Índice ONI (NOAA CPC)...")
    df_oni = descargar_oni()

    print("\n2. Cargando series de Chiloé Chulín...")
    if not SITE_MONTHLY_CSV.exists():
        sys.exit(f"❌ No existe {SITE_MONTHLY_CSV}. Ejecutar run_site.py primero.")
    df_mensual = pd.read_csv(SITE_MONTHLY_CSV, parse_dates=["time"])
    df_mhw = pd.read_csv(MHW_EVENTS_CSV, parse_dates=["inicio", "fin"])
    print(f"   ↪ Serie mensual: {df_mensual['time'].min():%Y-%m} → {df_mensual['time'].max():%Y-%m} "
          f"({len(df_mensual)} meses)")
    print(f"   ↪ Eventos MHW: {len(df_mhw)}")

    print("\n3. Figuras de barra ONI...")
    figura_barra_oni(
        df_oni, 1993, 2026, "barra_oni_completa.png",
        anotaciones=[
            {"time": pd.Timestamp("2016-02-01"), "y": df_oni.loc[df_oni["time"] == "2016-02-01", "anom"].values[0],
             "texto": "2016\nPseudochattonella", "xytext": (pd.Timestamp("2012-01-01"), 2.0), "ha": "center"},
            {"time": pd.Timestamp("2021-04-01"), "y": df_oni.loc[df_oni["time"] == "2021-04-01", "anom"].values[0],
             "texto": "2021\nHeterosigma (La Niña)", "xytext": (pd.Timestamp("2023-01-01"), -1.8), "ha": "center"},
        ],
    )
    figura_barra_oni(
        df_oni, 2012, 2027, "barra_oni_zoom.png",
        titulo="Índice ONI (NOAA CPC) — hacia el Aviso de El Niño de junio 2026",
        anotaciones=[
            {"time": pd.Timestamp("2026-04-01"), "y": df_oni.loc[df_oni["time"] == "2026-04-01", "anom"].values[0],
             "texto": "Aviso El Niño\n11-jun-2026:\n63% prob. evento\nMUY FUERTE en\nNDJ 2026–27",
             "xytext": (pd.Timestamp("2023-01-01"), 1.6), "ha": "center"},
        ],
    )

    print("\n4. Figura centerpiece (overlay anomalía SST + ENSO + FAN)...")
    figura_overlay_centerpiece(df_mensual, df_oni, df_mhw)

    print("\n5. Mapas de anomalía SST — episodios 2016 y 2021...")
    if not MAR_INTERIOR_REP_NC.exists():
        sys.exit(f"❌ No existe {MAR_INTERIOR_REP_NC}. Ejecutar run_chiloe_gif.py primero.")
    generar_mapas_episodios()

    print("\n6. Reutilizando GIF de anomalía 2026 (mar interior de Chiloé)...")
    if GIF_ORIGEN.exists():
        destino_gif = FIGURES_NINO_DIR / "anomalia_2026_chiloe.gif"
        shutil.copy(GIF_ORIGEN, destino_gif)
        print(f"   ✓ {destino_gif} (copiado de {GIF_ORIGEN}, ya vigente)")
    else:
        print(f"   ⚠️  No se encontró {GIF_ORIGEN}; ejecutar run_chiloe_gif.py primero.")
    if PNG_FINAL_ORIGEN.exists():
        destino_png = FIGURES_NINO_DIR / "anomalia_2026_chiloe_final.png"
        shutil.copy(PNG_FINAL_ORIGEN, destino_png)
        print(f"   ✓ {destino_png}")

    print("\n7. Copiando figura de soporte (MHW anual)...")
    mhw_anual_origen = Path(f"figures/sites/{SITE_NAME}/mhw_anual.png")
    if mhw_anual_origen.exists():
        shutil.copy(mhw_anual_origen, FIGURES_NINO_DIR / "mhw_anual_chiloe_chulin.png")
        print(f"   ✓ {FIGURES_NINO_DIR / 'mhw_anual_chiloe_chulin.png'}")
    else:
        print(f"   ⚠️  No se encontró {mhw_anual_origen}; el slide 5 quedará sin imagen de soporte.")

    print("\n8. Generando slides del carrusel...")
    crear_slides(df_mensual)

    print(f"\n✅ Listo. Figuras en {FIGURES_NINO_DIR}/")


if __name__ == "__main__":
    main()
