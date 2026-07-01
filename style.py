"""
style.py — tema visual compartido para todas las figuras del pipeline SST.

Uso:
    from style import apply_style, add_credit, add_minmax, CREAM, LAND_CREAM
    from style import CMAP_SST, CMAP_ANOM, SST_VMIN, SST_VMAX, ANOM_ABS
    apply_style()          # llamar una vez en main()
    add_credit(fig)        # pie de figura con fuente
    add_minmax(fig, arr)   # anotación mín/máx (arrays de valores en °C)
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ── Paleta ────────────────────────────────────────────────────────────────────
CREAM      = "#F5F0E8"   # fondo figura y axes
LAND_CREAM = "#EDE8DF"   # tierra (ligeramente más oscura que el fondo)
INK        = "#2A2A2A"   # texto, ejes, spines

# ── Colormaps ─────────────────────────────────────────────────────────────────
# ponytail: constantes nombradas para cambiar paleta en un solo lugar si hace falta
CMAP_SST  = "RdYlBu_r"
CMAP_ANOM = LinearSegmentedColormap.from_list(
    "sst_anomaly",
    ["#1E4E99", "#4F8CC8", "#A9CBEA", "#F8F8F8", "#F6A58D", "#D53E2A", "#6A0000"],
)

# ── Escalas fijas (estándar oceanográfico: compartidas entre regiones y frames) ──
SST_VMIN, SST_VMAX = 8, 18   # °C — SST absoluta; extend='both' captura extremos
ANOM_ABS = 3                  # °C — anomalía simétrica ±3; extend='both'

# ── Crédito ───────────────────────────────────────────────────────────────────
CREDIT = "FUENTE: Copernicus Marine - OSTIA SST L4 - @agustinpina"
CREDIT_GCH2025 = (
    "Análogo a Copernicus Climate Change Service - Global Climate Highlights 2025 "
    "(Fig1/Fig7) · SST vs. ref. 1993-2020"
)


def apply_style():
    """Setea rcParams globales. Llamar una vez al inicio de main()."""
    plt.rcParams.update({
        # Fondos
        "figure.facecolor":   CREAM,
        "axes.facecolor":     CREAM,
        "savefig.facecolor":  CREAM,
        # Tipografía
        "font.family":        "Arial",
        "text.color":         INK,
        "axes.labelcolor":    INK,
        "xtick.color":        INK,
        "ytick.color":        INK,
        # Spines: solo bottom + left
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.edgecolor":     INK,
        # Título alineado a la izquierda, bold
        "axes.titlelocation": "left",
        "axes.titleweight":   "bold",
        "axes.titlesize":     13,
        # Grid tenue
        "axes.grid":          True,
        "grid.color":         INK,
        "grid.alpha":         0.12,
        "grid.linewidth":     0.6,
    })


def add_credit(fig, y=0.01, nota=None):
    """Añade una línea de crédito al pie izquierdo de la figura.

    Si se pasa `nota` (p.ej. CREDIT_GCH2025), se agrega como segunda línea
    debajo del crédito base.
    """
    texto = CREDIT if nota is None else f"{CREDIT}\n{nota}"
    fig.text(0.01, y, texto, ha="left", va="bottom",
             fontsize=7.5, color=INK, alpha=0.6)


def add_minmax(fig, arr, y=0.01):
    """Añade 'mín. X.XX °C · máx. Y.YY °C' al pie derecho de la figura.

    arr puede ser un ndarray de valores ya en °C (NaN ignorados).
    """
    vals = np.asarray(arr, dtype=float)
    vmin = np.nanmin(vals)
    vmax = np.nanmax(vals)
    txt = f"mín. {vmin:.2f} °C · máx. {vmax:.2f} °C"
    fig.text(0.99, y, txt, ha="right", va="bottom",
             fontsize=7.5, color=INK, alpha=0.6)
