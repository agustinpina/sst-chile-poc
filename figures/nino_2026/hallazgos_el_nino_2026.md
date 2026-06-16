# Hallazgos: El Niño 2026 y la salmonicultura de Chiloé

> Resumen de los datos detrás del carrusel + GIF de `figures/nino_2026/`, pensado
> como base para crear contenido (LinkedIn, newsletters, charlas internas).
> Generado con `run_nino.py`. Fuentes y limitaciones al final.

---

## 1. El dato que dispara todo: Aviso de El Niño (NOAA, 11-jun-2026)

- NOAA/CPC emitió un **Aviso de El Niño el 11 de junio de 2026**: *"El Niño
  conditions are present and expected to strengthen into the Northern
  Hemisphere winter 2026-27"*.
- **Niño-3.4 semanal: +0.7 °C** (aún débil — territorio de El Niño apenas
  incipiente).
- **Pronóstico CPC: 63% de probabilidad de evento MUY FUERTE (RONI ≥ 2.0 °C)**
  en nov-dic-ene 2026–27, y ~88% de que sea al menos "fuerte" (≥1.5 °C).
- Ese peak pronosticado **coincide con la ventana de floraciones algales
  nocivas (FAN) dic-abr** en el sur de Chile.

**Framing correcto para contenido (no negociable):**
> No es "El Niño ya llegó y viene la mortandad". Es **"se emitió un Aviso; el
> pronóstico apunta a un evento fuerte-a-muy-fuerte que alcanzaría su máximo
> justo al inicio de la temporada de riesgo FAN"**. El dato actual (+0.7 °C)
> todavía es modesto — el mensaje es de **anticipación**, no de alarma inmediata.

**Nota técnica ONI vs RONI:** nuestra serie usa el **ONI clásico** de NOAA CPC
(`oni.ascii.txt`), con **MAM 2026 = +0.48 °C** (recién entrando en territorio
El Niño). NOAA adoptó **RONI** como índice oficial desde feb-2026 (el
documento fuente estima RONI MAM 2026 ≈ -0.1 a +0.4 °C); ONI y RONI pueden
diferir ~0.1–0.5 °C — no son intercambiables, pero ambos muestran la misma
transición La Niña → El Niño en 2025–2026.

---

## 2. Qué dice la serie local (Chiloé Chulín, 1993–2026)

Datos: Copernicus Marine OSTIA 0.05° (REP+NRT), climatología 1993–2020,
centroide Chiloé Chulín (mar interior).

- Serie mensual cubre **ene-1993 → jun-2026** (402 meses).
- **Anomalía jun-2026 = +0.78 °C** — uno de los valores más altos de la serie
  para ese mes (máximo histórico de toda la serie: **+1.00 °C en jul-1998**,
  el otro gran El Niño).
- Justo antes (ene-abr 2026) la anomalía era **negativa** (-0.38 a -0.02 °C),
  reflejando la cola de La Niña 2025. El salto a +0.78 °C en junio es el
  primer mes claramente positivo del año — consistente con el giro hacia
  El Niño que reporta el Aviso.

### Eventos de ola de calor marina (MHW, Hobday et al. 2016) recientes

| Inicio | Fin | Duración | Intensidad media | Intensidad máx |
|---|---|---|---|---|
| 2025-08-17 | 2025-08-21 | 5 d | 0.61 °C | 0.72 °C |
| 2025-10-27 | 2025-11-03 | 8 d | 0.87 °C | 1.11 °C |
| 2025-11-21 | 2025-12-04 | **14 d** | **1.62 °C** | **2.56 °C** |
| 2026-06-02 | 2026-06-08 | 7 d | 0.74 °C | 1.13 °C |

El MHW de **nov-dic 2025** (14 días, hasta +2.56 °C sobre climatología) es el
más intenso desde 2016–2018 — y ocurrió **durante La Niña débil** (ONI OND/NDJ
2025 ≈ -0.55 °C). Otro recordatorio de que las anomalías locales no siguen el
ENSO de forma lineal: el verano 2025–26 ya venía caliente *antes* del Aviso de
El Niño.

---

## 3. Los dos casos de estudio (la columna vertebral del relato)

### 2016 — *Pseudochattonella* (Seno de Reloncaví, feb-mar 2016)

- **>40.000 t perdidas** (≈ rango >39M peces), **~12% de la producción
  nacional del semestre**, **>US$800 millones** en pérdidas. Detonó la crisis
  social "Mayo Chilote".
- Disparador: **El Niño fuerte + SAM positivo** (combinación
  estadísticamente inusual) → verano cálido, seco, soleado, baja
  escorrentía → se debilita la capa superficial de agua dulce → entra agua
  salina rica en nutrientes + fuerte estratificación → floración en capa
  fina que persiste semanas.
- Anomalía SST local en feb-2016: **solo +0.35 °C** — un valor moderado. La
  severidad vino del *mecanismo* (estratificación + retención), no de un
  calor extremo puntual.

### 2021 — *Heterosigma akashiwo* (Fiordo Comau, mar-abr 2021)

- **>6.000 t perdidas en 12 centros (~US$4,4M)**.
- Ocurrió con **ONI ≈ -0.9 °C → La Niña**. Lo que mandó fue el **SAM positivo
  (>1.2 hPa)**, que superó la señal de La Niña: 2° verano más seco en 70 años,
  sequía, alta retención del fiordo.
- Anomalía SST local en abr-2021: **-0.20 °C** (¡negativa!). Confirma que
  **El Niño no es sinónimo de mortandad, ni La Niña es "zona segura"** — hay
  que vigilar SAM y caudal de ríos junto al ENSO.

---

## 4. Qué esperar (invierno 2026 → verano 2026-27)

- **Ahora–sep 2026 (preparación):** levantar línea base de anomalía SST +
  MHW históricos por sitio (2016 y 2021 como referencia); reforzar monitoreo
  FAN (CREAN i-FAN).
- **Oct 2026–abr 2027 (ventana de riesgo):** seguir CHONOS MOSA/PARTI-MOSA +
  i-FAN a diario. **Señal de máximo riesgo = MHW categoría II+ en el sitio +
  SAM positivo + bajo caudal de ríos (CHONOS FLOW)** — esa es la "huella"
  compartida de 2016 y 2021.
- **Acciones a pre-posicionar:** oxigenación/aireación, lonas/skirts, plan de
  cosecha de emergencia; adelantar tratamientos de *Caligus* (ciclo ~45 d a
  10 °C vs ~26 d a 15 °C — se acorta con calor); alinear vacunación/siembra
  SRS al calendario térmico (eficacia de vacunas vivas es sensible a
  temperatura).

---

## 5. El material gráfico generado (`figures/nino_2026/`)

| Archivo | Qué muestra | Uso sugerido |
|---|---|---|
| `slide_01_gancho.png` | Aviso NOAA 11-jun + barra ONI 2012-2027 | Portada del carrusel |
| `slide_02_2016.png` | Mapa de anomalía feb-mar 2016 + ficha *Pseudochattonella* | Carrusel, slide 2 |
| `slide_03_2021.png` | Mapa de anomalía mar-abr 2021 + ficha *Heterosigma* (La Niña) | Carrusel, slide 3 |
| `slide_04_centerpiece.png` | Overlay 33 años: anomalía + fases ENSO + MHW + eventos FAN | Carrusel, slide 4 (la pieza más densa) |
| `slide_05_acciones.png` | Días en MHW por año + qué hacer ahora | Cierre del carrusel (CTA) |
| `anomalia_2026_chiloe.gif` | **Animación**: anomalía SST 2026 evolucionando en el mar interior de Chiloé hasta el 13-jun-2026 | **Post individual / video corto** |
| `anomalia_2026_chiloe_final.png` | Último frame del GIF (mapa estático del 13-jun-2026) | Thumbnail/portada del post del GIF |
| `barra_oni_completa.png`, `barra_oni_zoom.png`, `anom_mapa_2016.png`, `anom_mapa_2021.png`, `mhw_anual_chiloe_chulin.png` | Figuras fuente de los slides | Reutilizar sueltas si se necesita un gráfico específico |

### Sobre el GIF para LinkedIn

`anomalia_2026_chiloe.gif` es el activo más "shareable": muestra visualmente
cómo se calienta/enfría el mar interior de Chiloé semana a semana durante 2026
respecto a su climatología 1993–2020, hasta el 13-jun-2026 (el frame final,
`anomalia_2026_chiloe_final.png`, ya muestra el giro hacia anomalías cálidas
en el sector noreste — coherente con el dato +0.78 °C de junio).

**Ángulo de copy sugerido para ese post:**
1. Gancho: "¿Cómo se ve un giro hacia El Niño desde el agua? Esto." + GIF.
2. 1-2 líneas de contexto: Aviso NOAA 11-jun-2026, 63% prob. evento muy fuerte
   hacia fin de año, justo antes de la temporada FAN.
3. Cierre con el mensaje de los slides 3/5: "El Niño no es garantía de
   mortandad — pero sí es señal para adelantar el monitoreo y la
   preparación". Link/referencia al carrusel completo para quien quiera el
   contexto 2016/2021.
4. Cita de datos al pie (igual que en los slides): *Datos: Copernicus Marine
   OSTIA 0.05° (REP+NRT) · Baseline climatológico 1993–2020*.

---

## 6. Fuentes y limitaciones

- **Datos SST:** Copernicus Marine `METOFFICE-GLO-SST-L4` (OSTIA 0.05°), REP
  1993→2025-12-18 + NRT 2025-12-01→presente.
- **Índice ENSO:** NOAA CPC ONI (`oni.ascii.txt`), ERSSTv5, base 1991-2020.
  RONI es el índice oficial desde feb-2026 y puede diferir ~0.1-0.5 °C del ONI.
- **MHW:** Hobday et al. (2016), p90 sobre climatología 1993-2020, ≥5 días,
  gaps ≤2 días.
- **Bibliografía de eventos:** León-Muñoz et al. 2018 (*Sci Rep*); Mardones
  et al. 2021/2022 (*Sci Total Environ* / *Harmful Algae*); Díaz et al. 2023
  (*Sci Total Environ*); González & Carvajal 2003; Rozas-Serri 2022.
- **Limitación clave:** la fase ENSO **no implica causalidad directa** con los
  eventos FAN — SAM, escorrentía y retención del fiordo son co-determinantes
  (ver caso 2021). Las cifras de 2016 varían por fuente y se presentan como
  rango (>39M peces ≈ >40.000 t; 12–15% de la producción; ~US$800M).
- **Baseline:** 1993-2020 (estándar de este repo). El dataset Copernicus
  arranca en 1993, por lo que no es posible usar el baseline WMO 1991-2020
  completo — se declara honestamente en cada figura.
