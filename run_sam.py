"""
run_sam.py — Descarga y cachea el índice AAO/SAM mensual de NOAA CPC.

El Antarctic Oscillation (AAO) de NOAA CPC es la misma señal del Modo Anular
del Sur (SAM/AAO) que la literatura salmonicultura chilena cita para 2016 y 2021.
Fuente: https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/aao/
Período: 1979-01 → presente (archivo ASCII mensual actualizado ~mensualmente).

# ponytail: AAO de CPC (base 1979-2000) en vez del SAM de Marshall/BAS
# (observacional, base 1979-1992). Misma señal, URL más estable.
# Cambiar a Marshall solo si la prensa exige la serie clásica:
# https://legacy.bas.ac.uk/met/gjma/sam.html

Salida: data/sam/sam.csv (cols: time, aao, fase)
Uso:    python run_sam.py
"""
import sys
import urllib.request
from pathlib import Path

import pandas as pd

SAM_DIR = Path("data/sam")
SAM_CACHE = SAM_DIR / "sam.csv"
SAM_URL = (
    "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/"
    "daily_ao_index/aao/monthly.aao.index.b79.current.ascii"
)


def clasificar_fase_sam(aao):
    if aao >= 0.5:
        return "positivo"
    if aao <= -0.5:
        return "negativo"
    return "neutral"


def descargar_sam(forzar=False):
    """Descarga (o reutiliza caché de) el índice AAO/SAM mensual de NOAA CPC."""
    if SAM_CACHE.exists() and not forzar:
        print(f"   ↪ Ya existe {SAM_CACHE}, se reutiliza.")
        return pd.read_csv(SAM_CACHE, parse_dates=["time"])

    print(f"→ Descargando índice SAM/AAO desde NOAA CPC ({SAM_URL})...")
    try:
        with urllib.request.urlopen(SAM_URL, timeout=30) as resp:
            texto = resp.read().decode("utf-8")
    except Exception as exc:
        sys.exit(f"❌ No se pudo descargar el índice SAM ({exc}) y no hay caché en {SAM_CACHE}.")

    # Formato: año mes valor (una fila por mes)
    filas = []
    for linea in texto.strip().splitlines():
        partes = linea.split()
        if len(partes) != 3:
            continue
        try:
            anio, mes, aao = int(partes[0]), int(partes[1]), float(partes[2])
        except ValueError:
            continue
        if aao == -999.0:
            continue
        filas.append({"time": pd.Timestamp(year=anio, month=mes, day=1), "aao": aao})

    df = pd.DataFrame(filas).sort_values("time").reset_index(drop=True)
    df["fase"] = df["aao"].apply(clasificar_fase_sam)

    SAM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAM_CACHE, index=False)
    print(f"   ✓ {SAM_CACHE} ({len(df)} filas, "
          f"{df['time'].min():%Y-%m} → {df['time'].max():%Y-%m})")
    return df


if __name__ == "__main__":
    df = descargar_sam()
    print(df.tail(12).to_string(index=False))

    # Informativo: SAM en veranos FAN conocidos.
    # 2016: literatura cita SAM positivo (El Niño fuerte + SAM+ excepcional).
    # 2021: literatura cita SAM >1.2 hPa (promedio DJF dic-feb, no solo mar).
    #        El AAO de CPC puede diferir del SAM de Marshall/BAS ~0.3-0.5 hPa.
    assert not df.empty, "Serie SAM vacía"
    for año, meses, etiqueta in [
        (2016, [1, 2, 3],    "verano 2015-16 (JFM)"),
        (2021, [12, 1, 2, 3], "verano 2020-21 (DJFM)"),
    ]:
        if etiqueta.startswith("verano 2020-21"):
            sub = df[((df["time"].dt.year == 2020) & (df["time"].dt.month == 12)) |
                     ((df["time"].dt.year == 2021) & df["time"].dt.month.isin([1, 2, 3]))]
        else:
            sub = df[(df["time"].dt.year == año) & df["time"].dt.month.isin(meses)]
        if not sub.empty:
            media = sub["aao"].mean()
            print(f"  {etiqueta}: AAO medio={media:+.2f} "
                  f"({'positivo' if media >= 0.5 else 'neutral/negativo'})")
    print("✅ Self-check SAM ok")
