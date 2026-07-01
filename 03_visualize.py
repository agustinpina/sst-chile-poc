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
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
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

# fig3/fig4/fig7 se exportan pensados para LinkedIn (post nativo multi-imagen,
# feed móvil): 4:5 portrait exacto en px = FIGSIZE_LI * DPI_LI = 1080×1350.
# bbox_inches="tight" queda descartado en esas tres figuras porque recalcula
# el tamaño de salida a partir del contenido dibujado — no garantiza el 4:5.
DPI_LI = 150
FIGSIZE_LI = (7.2, 9)
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

    # Formato 4:5 portrait para LinkedIn (feed móvil, ver DPI_LI/FIGSIZE_LI).
    fig, ax = plt.subplots(
        figsize=FIGSIZE_LI,
        subplot_kw={"projection": ccrs.PlateCarree()},
    )
    fig.subplots_adjust(top=0.92, bottom=0.08, left=0.14, right=0.92)
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
    gl.xlabel_style = {"fontsize": 10}
    gl.ylabel_style = {"fontsize": 10}

    # Colorbar horizontal: en portrait no hay ancho para una barra vertical.
    styled_colorbar(fig, im, ax, "SST (°C)", orientation="horizontal",
                    shrink=0.9, pad=0.06)

    ax.set_title(
        f"SST media {anio_inicio_datos}–{anio_fin_datos}\n{nombre.replace('_', ' ').title()}",
        fontsize=18,
    )
    ds.close()

    add_minmax(fig, sst_promedio.values, y=0.03)
    add_credit(fig, y=0.01)

    salida = FIGURES_DIR / f"fig3_mapa_{nombre}.png"
    fig.savefig(salida, dpi=DPI_LI)
    plt.close(fig)
    print(f"   ✓ {salida}")


def figura_mapas_por_region():
    for nombre, bbox in REGIONES.items():
        figura_mapa_region(nombre, bbox)


# Aviso de El Niño emitido por NOAA. VERIFICAR fecha/redacción exacta antes de
# publicar — es una afirmación factual, no derivada de los datos del pipeline.
AVISO_ELNINO = pd.Timestamp("2026-06-11")


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

    # Márgenes explícitos (no los defaults de matplotlib, que dejaban ~12%
    # de banda blanca a cada lado) — header, paneles y footer comparten LEFT.
    LEFT, RIGHT = 0.055, 0.985
    # sharey=True: misma escala de anomalía en los 3 paneles — con ejes
    # independientes la variación visual entre regiones queda distorsionada.
    fig, axes = plt.subplots(len(REGIONES), 1, figsize=(14, 11), sharex=True, sharey=True)
    for i, (ax, nombre) in enumerate(zip(axes, REGIONES)):
        df = dfs.get(nombre)
        if df is None or df.empty:
            ax.set_visible(False)
            continue
        colores_bar = np.where(df["anomaly"] >= 0, "#d62728", "#1f77b4")
        ax.bar(df["time"], df["anomaly"], width=1, color=colores_bar, alpha=0.55)
        rolling = df["anomaly"].rolling(ROLLING_DIAS, min_periods=1, center=True).mean()
        ax.plot(df["time"], rolling, color="#2ca02c", lw=2)
        ax.axhline(0, color="black", lw=0.8)
        ax.axvline(AVISO_ELNINO, color=COLOR_NINO, ls="--", lw=1.1, zorder=1)
        ax.set_ylabel("Anomalía (°C)")
        ultimo = df.dropna(subset=["anomaly"]).iloc[-1]
        ax.set_title(
            f"{nombre.replace('_', ' ').title()}  —  "
            f"último dato: {pd.Timestamp(ultimo['time']).strftime('%d %b %Y')} "
            f"({ultimo['anomaly']:+.2f} °C)",
            pad=8,
        )
        ax.grid(alpha=0.3)
        if i == 0:
            ax.text(AVISO_ELNINO, ax.get_ylim()[1], " Aviso El Niño - NOAA 11 jun",
                    ha="left", va="top", fontsize=7.5, color=COLOR_NINO)

    # Header de 2 niveles vía fig.text() (en vez de un suptitle): título
    # autoexplicativo + subtítulo con el detalle técnico (baseline y zonas).
    # Ambos anclados a LEFT, igual que los títulos por-panel (axes.titlelocation
    # "left" en style.py) y que el footer.
    fig.text(LEFT, 0.965, "Evolución de las anomalías térmicas en el sur de Chile durante 2026",
              ha="left", va="top", fontsize=19, fontweight="bold")
    fig.text(LEFT, 0.928,
              f"Anomalía vs. climatología {BASELINE_START}-{BASELINE_END}  —  "
              "zonas salmonicultoras: Los Lagos, Aysén, Magallanes",
              ha="left", va="top", fontsize=11.5)

    # Leyenda a la derecha, sobre la misma línea de base que el subtítulo
    # (no en fila propia) — no compite con el título ni con el título del
    # primer panel, y no le resta altura a los paneles.
    leyenda = [
        Line2D([0], [0], color="#2ca02c", lw=2, label="Media móvil 7 días"),
        mpatches.Patch(color="#d62728", alpha=0.55, label="Anomalía + (más cálido)"),
        mpatches.Patch(color="#1f77b4", alpha=0.55, label="Anomalía − (más frío)"),
    ]
    fig.legend(handles=leyenda, loc="upper right", bbox_to_anchor=(RIGHT, 0.928),
               ncol=3, frameon=False, fontsize=9)

    fig.autofmt_xdate()
    # autofmt_xdate() reserva su propio margen inferior (más grande de lo
    # necesario) para las fechas rotadas — se reafirma después junto con el
    # resto de márgenes para que no quede una franja vacía entre el último
    # panel y el footer, ni entre el header y el primer panel. El título de
    # cada panel se dibuja *por encima* de "top" (pad + su propio alto de
    # fuente) — top deja ese espacio libre para no solaparse con el header.
    fig.subplots_adjust(top=0.865, bottom=0.11, left=LEFT, right=RIGHT, hspace=0.30)
    add_credit(fig, y=0.02, x=LEFT)
    salida = FIGURES_DIR / "fig4_anomalia_2026.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight", pad_inches=0.15)
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
        f"Anomalía mensual SST vs. ref. {BASELINE_START}-{BASELINE_END} - "
        f"{nombre.replace('_', ' ').title()}"
    )
    ax.grid(alpha=0.3)
    add_credit(fig, nota=CREDIT_GCH2025)

    salida = FIGURES_DIR / f"fig6_anom_mensual_{nombre}.png"
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


# Eventos climáticos para anotar fig7 (años verificados vía ONI/NOAA y prensa especializada
# en floraciones algales nocivas — ver docs/agents o el plan de esta feature). Se combinan
# eventos del mismo año para no chocar en el eje. El Niño→derecha/rojo, La Niña→izquierda/azul.
EVENTOS_CLIMA = [
    (1998, "right", "1997-98\nEl Niño muy fuerte"),
    (1999, "left",  "1998-2000\nLa Niña fuerte"),
    (2007, "right", "2006-07\nEl Niño fuerte"),
    (2008, "left",  "2007-08\nLa Niña fuerte"),
    (2009, "right", "2009\nEl Niño moderado - FAN"),
    (2011, "left",  "2010-11\nLa Niña fuerte"),
    (2016, "right", "2015-16 El Niño muy fuerte\n+ marea roja (~39.000 t)"),
    (2021, "left",  "2020-22 La Niña (triple)\n+ FAN 2021 (Comau/Aysén)"),
    (2024, "right", "2023-24\nEl Niño fuerte - FAN"),
]
FAN_YEARS = {2009, 2016, 2021, 2023, 2024}  # floraciones algales nocivas con mortalidad de salmón
COLOR_NINO = "#B5321F"  # rojo — mismo tono que la flecha "más cálido"
COLOR_NINA = "#1E4E99"  # azul — mismo tono que la flecha "más frío"
COLOR_FAN = "#E67E22"   # naranja, distinto de la paleta de anomalía (evita confusión de color)


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

    ANOM_LIM = 2.0   # rango real de datos (~-1.5 a +1.9°C) cabe holgado en ±2
    grilla = np.linspace(-ANOM_LIM, ANOM_LIM, 400)
    gnorm = plt.Normalize(vmin=-ANOM_LIM, vmax=ANOM_LIM)  # color = magnitud de la anomalía
    paso = 1.0       # separación vertical entre baselines
    altura = 5.5      # solapado tipo llama (estilo GCH2025 Fig1): pico ~5.5x la separación

    # Formato 4:5 portrait fijo para LinkedIn (antes escalaba con el nº de años;
    # con canvas fijo los ~33 años quedan algo más comprimidos verticalmente,
    # compensado abajo con fuentes más grandes en ejes/leyenda/callouts).
    fig, ax = plt.subplots(figsize=FIGSIZE_LI)
    fig.subplots_adjust(top=0.86, bottom=0.14, left=0.14, right=0.94)
    n = len(anios)
    bases = {}  # año → altura Y de su baseline, para ubicar los callouts de eventos
    for i, anio in enumerate(anios):
        valores = df.loc[df["anio"] == anio, "anomaly"].to_numpy()
        if len(valores) < 5:
            continue
        # 1993 arriba, año más reciente abajo; zorder creciente hacia abajo
        # para que cada ridge tape parcialmente al de arriba (oclusión joyplot).
        base = (n - 1 - i) * paso
        bases[anio] = base
        densidad = stats.gaussian_kde(valores)(grilla)
        densidad = densidad / densidad.max() * paso * altura

        im = ax.imshow(
            grilla.reshape(1, -1), extent=[grilla[0], grilla[-1], base, base + densidad.max()],
            aspect="auto", origin="lower", cmap=CMAP_ANOM, norm=gnorm, zorder=i,
        )
        verts = np.column_stack([
            np.r_[grilla, grilla[::-1]],
            np.r_[base + densidad, np.full_like(grilla, base)],
        ])
        clip = mpatches.PathPatch(mpath.Path(verts), transform=ax.transData, fc="none", lw=0)
        ax.add_patch(clip)
        im.set_clip_path(clip)
        ax.plot(grilla, base + densidad, color="black", lw=0.4, alpha=0.5, zorder=i)

    ax.axvline(0, color="black", lw=0.8, zorder=n)
    ax.set_xlim(-ANOM_LIM, ANOM_LIM)
    ax.set_ylim(0, (n - 1) * paso + paso * altura)
    paso_etiqueta = 3 if n > 15 else 1  # años más espaciados: menos ruido con curvas altas
    ax.set_yticks([(n - 1 - i) * paso for i in range(n) if anios[i] % paso_etiqueta == 0])
    ax.set_yticklabels([str(a) for a in anios if a % paso_etiqueta == 0], fontsize=9)
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=9)
    ax.set_xlabel(f"Anomalía SST (°C) - ref. {BASELINE_START}-{BASELINE_END}", fontsize=11)
    ax.text(0.0, 1.02, "← más frío que el promedio", transform=ax.transAxes,
            ha="left", va="bottom", fontsize=10, color="#1E4E99", style="italic")
    ax.text(1.0, 1.02, "más cálido que el promedio →", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=10, color="#B5321F", style="italic")
    ax.set_title(
        f"Distribución diaria de anomalías SST\n{nombre.replace('_', ' ').title()}",
        pad=20, fontsize=16,
    )

    # Callouts de eventos climáticos (El Niño / La Niña) — texto dentro del
    # canvas (pegado al borde, donde la densidad ya cayó a ~0), no fuera de
    # los ejes: en 4:5 fijo no hay margen de figura para texto extra-axes.
    for anio, lado, texto in EVENTOS_CLIMA:
        if anio not in bases:      # la región puede no cubrir ese año
            continue
        base = bases[anio]
        color = COLOR_NINO if lado == "right" else COLOR_NINA
        if lado == "right":
            x, ha = ANOM_LIM - 0.05, "right"
        else:
            x, ha = -ANOM_LIM + 0.05, "left"
        ax.text(x, base, texto, ha=ha, va="center", fontsize=6.8,
                color=color, zorder=n + 1,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))

    # Marcador FAN (floración algal nociva con mortalidad de salmón) sobre la línea cero.
    for anio in sorted(FAN_YEARS):
        if anio in bases:
            ax.plot(0, bases[anio], marker="D", ms=5, color=COLOR_FAN,
                    mec="white", mew=0.6, zorder=n + 2)

    leyenda = [
        Line2D([0], [0], color=COLOR_NINO, lw=1.2, label="El Niño"),
        Line2D([0], [0], color=COLOR_NINA, lw=1.2, label="La Niña"),
        Line2D([0], [0], marker="D", color="none", mec="white", mfc=COLOR_FAN, ms=6,
               label="Floración algal nociva (FAN)"),
    ]
    ax.legend(handles=leyenda, loc="lower center", bbox_to_anchor=(0.5, -0.1),
              ncol=3, frameon=False, fontsize=7.2)

    add_credit(fig, y=0.005, nota=CREDIT_GCH2025)

    salida = FIGURES_DIR / f"fig7_distribucion_{nombre}.png"
    fig.savefig(salida, dpi=DPI_LI)
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
            f"Anomalía SST 2026 - {nombre.replace('_', ' ').title()}\n"
            f"(media móvil {ROLLING_DIAS} días - ref. {BASELINE_START}-{BASELINE_END})"
        )
        fecha_txt.set_text(times[i].strftime("%Y-%m-%d"))
        return im, titulo, fecha_txt

    ntimes = len(times)
    print(f"   → Renderizando {ntimes} frames ({ntimes / GIF_FPS:.0f} s a {GIF_FPS} fps)…")
    ani = animation.FuncAnimation(
        fig, update, frames=ntimes, interval=1000 / GIF_FPS, blit=False
    )
    salida = FIGURES_DIR / f"fig5_anomalia_{nombre}.gif"
    ani.save(str(salida), writer="pillow", fps=GIF_FPS, dpi=DPI_GIF)
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
