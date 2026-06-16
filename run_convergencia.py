"""
run_convergencia.py — Síntesis de factores de riesgo FAN por verano (dic-abr).

Para cada verano FAN entre 1993-94 y 2026-27 construye una tabla con:
  - Anomalía SST media del área (Chiloé interior o la zona indicada)
  - Categoría máx MHW durante el verano (Hobday I-IV; 0 = sin evento)
  - Índice ENSO/ONI promedio del verano
  - Índice SAM/AAO promedio del verano
  - Caudal Río Puelo (si disponible)

El "semáforo de convergencia" cuenta cuántos factores superan umbrales de riesgo.
No es un modelo predictivo de FAN — es lo que el post ya afirma: señal de
condiciones favorables. Subir a modelo requiere datos de blooms para entrenar.

# ponytail: umbrales de riesgo calibrados sobre 2016 y 2021 (los dos únicos
# eventos FAN documentados con impacto económico registrado en este repo).
# Con solo 2 casos positivos no se puede ajustar un clasificador — el semáforo
# es heurístico, no estadístico.

Salida:
  data/convergencia_fan.csv
  figures/nino_2026/convergencia_fan.png

Uso:
  python run_convergencia.py [--zona chiloe_interior] [--baseline-start 1993 --baseline-end 2020]
"""
import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from run_point import DPI

# ---------------------------------------------------------------------------
# Umbrales de riesgo (heurísticos, calibrados sobre 2016 y 2021)
# ---------------------------------------------------------------------------
UMBRAL_ANOM_SST = 0.0       # anomalía > 0 °C = verano más cálido que climatología
UMBRAL_MHW_CAT = 2          # MHW categoría II+ durante el verano
UMBRAL_ONI = 0.5            # El Niño (ONI ≥ 0.5 °C)
UMBRAL_SAM = 0.5            # SAM positivo (AAO ≥ 0.5)

# Meses que definen la ventana FAN (verano austral)
MESES_FAN = [12, 1, 2, 3, 4]

EVENTOS_FAN_CONOCIDOS = {
    2016: {"especie": "Pseudochattonella", "zona": "Reloncaví", "perdidas_t": 40000},
    2021: {"especie": "Heterosigma",       "zona": "Comau",      "perdidas_t": 6000},
}

DATA_DIR = Path("data")
FIGURES_DIR = Path("figures/nino_2026")


def parsear_args():
    p = argparse.ArgumentParser()
    p.add_argument("--zona", default="chiloe_interior",
                   help="Nombre del sitio en data/sites/ (default: chiloe_interior).")
    p.add_argument("--baseline-start", type=int, default=1993)
    p.add_argument("--baseline-end", type=int, default=2020)
    return p.parse_args()


def cargar_sst_mensual(zona):
    path = DATA_DIR / "sites" / zona / f"site_monthly_{zona}.csv"
    if not path.exists():
        sys.exit(f"❌ No existe {path}. Correr primero:\n"
                 f"   python run_site.py --name {zona} --modo area ...")
    return pd.read_csv(path, parse_dates=["time"])


def cargar_mhw_eventos(zona):
    path = DATA_DIR / "sites" / zona / f"mhw_eventos_{zona}.csv"
    if not path.exists():
        print(f"   ⚠️  No se encontró {path}. MHW = sin datos.")
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["inicio", "fin"])
    if "categoria_max" not in df.columns:
        print("   ⚠️  mhw_eventos no tiene columna 'categoria_max' (run_site.py viejo). "
              "Regener con run_site.py actualizado.")
        df["categoria_max"] = 1
        df["dias_cat2plus"] = 0
    return df


def cargar_oni():
    path = DATA_DIR / "nino" / "oni.csv"
    if not path.exists():
        print("   ⚠️  No hay data/nino/oni.csv. Correr primero: python run_nino.py")
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["time"])


def cargar_sam():
    path = DATA_DIR / "sam" / "sam.csv"
    if not path.exists():
        print("   ⚠️  No hay data/sam/sam.csv. Correr primero: python run_sam.py")
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["time"])


def cargar_caudal():
    path = DATA_DIR / "caudal" / "puelo.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["time"])


def ventana_fan(anio_fin):
    """Devuelve (inicio, fin) de la ventana FAN dic(año-1) → abr(año_fin)."""
    return pd.Timestamp(anio_fin - 1, 12, 1), pd.Timestamp(anio_fin, 4, 30)


def max_cat_mhw_en_ventana(df_mhw, inicio, fin):
    """Categoría máxima de evento MHW con algún solapamiento con la ventana."""
    if df_mhw.empty:
        return 0
    solapan = df_mhw[(df_mhw["inicio"] <= fin) & (df_mhw["fin"] >= inicio)]
    return int(solapan["categoria_max"].max()) if not solapan.empty else 0


def media_en_ventana(df, col_time, col_val, inicio, fin):
    """Media de col_val en el intervalo [inicio, fin]."""
    mask = (df[col_time] >= inicio) & (df[col_time] <= fin)
    sub = df.loc[mask, col_val]
    return round(float(sub.mean()), 3) if not sub.empty else np.nan


def construir_tabla(df_sst, df_mhw, df_oni, df_sam, df_caudal):
    """Una fila por verano FAN desde 1994-95 hasta el que tenga datos."""
    # Años disponibles: el verano X termina en abr del año X
    primer_anio = df_sst["time"].dt.year.min() + 1  # necesita dic del año anterior
    ultimo_anio = df_sst["time"].dt.year.max()       # hasta donde llegue la serie SST

    filas = []
    for anio_fin in range(primer_anio, ultimo_anio + 1):
        ini, fin = ventana_fan(anio_fin)
        anom = media_en_ventana(df_sst, "time", "anomaly", ini, fin)
        cat_mhw = max_cat_mhw_en_ventana(df_mhw, ini, fin)
        oni = media_en_ventana(df_oni, "time", "anom", ini, fin) if not df_oni.empty else np.nan
        sam = media_en_ventana(df_sam, "time", "aao",  ini, fin) if not df_sam.empty else np.nan
        caudal = media_en_ventana(df_caudal, "time", "caudal_m3s", ini, fin) if not df_caudal.empty else np.nan

        # Semáforo: contar factores en zona de riesgo
        factores = 0
        if not np.isnan(anom) and anom > UMBRAL_ANOM_SST:
            factores += 1
        if cat_mhw >= UMBRAL_MHW_CAT:
            factores += 1
        if not np.isnan(oni) and oni >= UMBRAL_ONI:
            factores += 1
        if not np.isnan(sam) and sam >= UMBRAL_SAM:
            factores += 1
        # caudal: si hay datos, bajo caudal suma (se compara con mediana histórica abajo)

        filas.append({
            "verano_fin": anio_fin,
            "label": f"{anio_fin-1}-{str(anio_fin)[2:]}",
            "anom_sst_c": anom,
            "cat_mhw_max": cat_mhw,
            "oni_medio": oni,
            "sam_medio": sam,
            "caudal_m3s": caudal,
            "factores_riesgo": factores,
            "fan_conocido": anio_fin in EVENTOS_FAN_CONOCIDOS,
        })

    df = pd.DataFrame(filas)

    # Ajustar factores: bajo caudal relativo a la mediana histórica
    if not df["caudal_m3s"].isna().all():
        mediana_caudal = df["caudal_m3s"].median()
        bajo_caudal = df["caudal_m3s"] < mediana_caudal * 0.8
        df.loc[bajo_caudal & df["caudal_m3s"].notna(), "factores_riesgo"] += 1

    return df


def figura_convergencia(df, salida):
    """Heatmap de factores de riesgo por verano. Marca 2016 y 2021."""
    FACTORES = ["anom_sst_c", "cat_mhw_max", "oni_medio", "sam_medio"]
    ETIQUETAS = ["Anomalía SST", "Cat MHW máx", "ONI (ENSO)", "SAM/AAO"]
    UMBRAL_FACTOR = [UMBRAL_ANOM_SST, UMBRAL_MHW_CAT, UMBRAL_ONI, UMBRAL_SAM]

    n_años = len(df)
    n_fact = len(FACTORES)

    # Matriz 0/1: ¿está el factor en zona de riesgo?
    mat = np.zeros((n_fact, n_años))
    for i, (col, umb) in enumerate(zip(FACTORES, UMBRAL_FACTOR)):
        vals = pd.to_numeric(df[col], errors="coerce")
        mat[i] = (vals >= umb).astype(float)
        # NaN → -1 (gris)
        mat[i, vals.isna()] = -1.0

    fig, ax = plt.subplots(figsize=(max(14, n_años * 0.35), 5))
    cmap = plt.cm.RdYlGn
    cmap.set_under("lightgray")  # NaN/sin datos

    im = ax.imshow(mat, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                   interpolation="nearest")

    ax.set_yticks(range(n_fact))
    ax.set_yticklabels(ETIQUETAS, fontsize=10)
    ax.set_xticks(range(n_años))
    ax.set_xticklabels(df["label"], rotation=90, fontsize=7)

    # Marcar años FAN conocidos
    for i_año, row in df.reset_index(drop=True).iterrows():
        if row["fan_conocido"]:
            año_fin = int(row["verano_fin"])
            especie = EVENTOS_FAN_CONOCIDOS[año_fin]["especie"]
            ax.axvline(i_año, color="red", lw=2.5, alpha=0.7)
            ax.text(i_año, -0.7, especie.split("(")[0].strip(),
                    ha="center", va="top", fontsize=7, color="red",
                    rotation=90, transform=ax.get_xaxis_transform())

    # Leyenda
    patches = [
        mpatches.Patch(color=cmap(1.0), label="Factor en zona de riesgo"),
        mpatches.Patch(color=cmap(0.0), label="Factor bajo umbral"),
        mpatches.Patch(color="lightgray", label="Sin datos"),
        mpatches.Patch(color="red", label="Evento FAN documentado"),
    ]
    ax.legend(handles=patches, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=9)

    ax.set_title("Semáforo de convergencia de factores de riesgo FAN — veranos 1994–2027\n"
                 "(verde = bajo umbral, rojo = en zona de riesgo, línea roja = FAN documentado)",
                 fontsize=11)
    fig.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"   ✓ {salida}")


def main():
    args = parsear_args()

    print(f"→ Cargando datos para zona '{args.zona}'...")
    df_sst    = cargar_sst_mensual(args.zona)
    df_mhw    = cargar_mhw_eventos(args.zona)
    df_oni    = cargar_oni()
    df_sam    = cargar_sam()
    df_caudal = cargar_caudal()

    print("→ Construyendo tabla de convergencia por verano FAN...")
    df = construir_tabla(df_sst, df_mhw, df_oni, df_sam, df_caudal)

    salida_csv = DATA_DIR / "convergencia_fan.csv"
    df.to_csv(salida_csv, index=False)
    print(f"   ✓ {salida_csv} ({len(df)} veranos)")

    # Self-check: 2016 debe tener ≥2 factores (El Niño + SAM + SST + MHW cat II).
    # 2021 es el caso edge: solo SAM+ documentado; el segundo factor (bajo caudal)
    # no está cuantificado sin datos DGA. Se imprime informativo, no aserción.
    fila_2016 = df[df["verano_fin"] == 2016]
    assert not fila_2016.empty, "Verano 2016 no está en la tabla"
    nf_2016 = int(fila_2016.iloc[0]["factores_riesgo"])
    assert nf_2016 >= 2, f"2016 tiene solo {nf_2016} factores — esperado ≥2."
    print(f"   ✓ 2016: {nf_2016} factores de riesgo (FAN documentado)")

    fila_2021 = df[df["verano_fin"] == 2021]
    if not fila_2021.empty:
        nf_2021 = int(fila_2021.iloc[0]["factores_riesgo"])
        # ponytail: 2021 tiene 1 factor (SAM+); el segundo (bajo caudal) requiere
        # datos DGA que la API no devolvió. El caso 2021 muestra el límite del
        # semáforo sin caudal cuantitativo.
        nota = " ⚠️  (bajo caudal no cuantificado — correr run_caudal.py con DGA)" if nf_2021 < 2 else ""
        print(f"   ℹ️  2021: {nf_2021} factor(es) de riesgo (FAN documentado){nota}")

    print("\n→ Generando figura semáforo...")
    figura_convergencia(df, FIGURES_DIR / "convergencia_fan.png")

    # Resumen de los últimos 3 veranos + próximo
    print("\n📋 Últimos veranos:")
    cols_print = ["label", "anom_sst_c", "cat_mhw_max", "oni_medio", "sam_medio", "factores_riesgo", "fan_conocido"]
    print(df[cols_print].tail(5).to_string(index=False))

    print(f"\n✅ Listo. Tabla en {salida_csv}")


if __name__ == "__main__":
    main()
