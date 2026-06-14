"""
mapviz.py — helpers de ploteo compartidos entre los scripts de mapas SST.

Centraliza el dibujo de la costa para que todos los mapas (regionales,
de sitio y de Chiloé mar interior) usen el mismo recurso de alta resolución.

Natural Earth a 10m (el usado anteriormente vía `ax.coastlines(resolution="10m")`
y `cfeature.LAND`) es demasiado grueso para la geografía fragmentada de Chiloé:
las islas del mar interior (Quinchao, Lemuy, Chelín, Mechuque, Quenac…) y los
canales quedan como una mancha gris sin forma.

GSHHG (Global Self-consistent, Hierarchical, High-resolution Geography), vía
`cartopy.feature.GSHHSFeature`, resuelve islas de pocos cientos de metros en su
escala "full" — sin agregar dependencias nuevas (cartopy la trae integrada).

NOTA sobre la descarga: la URL por defecto de cartopy para GSHHG
(`ngdc.noaa.gov/mgg/shorelines/...`) devuelve 404 — NOAA reestructuró ese sitio
y cartopy 0.25 todavía apunta a las rutas viejas. Por eso registramos un
downloader alternativo que apunta al mirror oficial de Paul Wessel
(soest.hawaii.edu), manteniendo el mismo directorio de caché de cartopy
(`~/.local/share/cartopy/shapefiles/gshhs/`). La primera vez descarga ~150 MB
(todas las escalas/niveles de GSHHG); las siguientes usan la copia en caché.
"""
import cartopy.feature as cfeature
from cartopy import config
from cartopy.io.shapereader import GSHHSShpDownloader

LAND_FACECOLOR = "#c8c8c8"
COAST_EDGECOLOR = "#333333"

_GSHHS_MIRROR_URL = "https://www.soest.hawaii.edu/pwessel/gshhg/gshhg-shp-2.3.7.zip"


def _registrar_mirror_gshhg():
    """Reemplaza el downloader GSHHG de cartopy (URL de NOAA rota, 404)
    por el mirror de soest.hawaii.edu, manteniendo las mismas rutas de
    destino/caché que cartopy usa por defecto."""
    key = ("shapefiles", "gshhs")
    actual = config["downloaders"].get(key)
    if isinstance(actual, GSHHSShpDownloader) and actual.url_template == _GSHHS_MIRROR_URL:
        return  # ya registrado
    default = GSHHSShpDownloader.default_downloader()
    config["downloaders"][key] = GSHHSShpDownloader(
        url_template=_GSHHS_MIRROR_URL,
        target_path_template=default.target_path_template,
        pre_downloaded_path_template=default.pre_downloaded_path_template,
    )


_registrar_mirror_gshhg()


def add_coastline(ax, scale="full", land_facecolor=LAND_FACECOLOR,
                   coast_color=COAST_EDGECOLOR, coast_lw=0.8, zorder=3):
    """Dibuja tierra rellena + línea de costa de alta resolución (GSHHG).

    Reemplaza en un solo feature al par `cfeature.LAND` + `ax.coastlines()`.

    Parámetros
    ----------
    ax : GeoAxes
    scale : {"full", "high", "intermediate", "low", "coarse"}
        Resolución GSHHG. "full" para áreas pequeñas con muchas islas
        (ej. mar interior de Chiloé); "high" para regiones extensas
        (Aysén, Magallanes) donde "full" sería muy lento/pesado.
    land_facecolor, coast_color, coast_lw : estilo del relleno y del borde.
    zorder : por defecto 3, para quedar por encima de un pcolormesh/contourf
        de SST dibujado con zorder menor.
    """
    land = cfeature.GSHHSFeature(
        scale=scale, levels=[1],
        facecolor=land_facecolor, edgecolor=coast_color, linewidth=coast_lw,
    )
    ax.add_feature(land, zorder=zorder)
    return land
