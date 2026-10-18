# Revisión técnica — Vivienda 8.00 × 23.00 m (2 plantas)

> Documento de trabajo. Los datos de la vivienda son **provisionales** (construidos a
> partir del programa de ambientes, sin imagen de referencia). Cada supuesto debe
> validarse antes de un anteproyecto definitivo.

## Datos base asumidos

- Lote **8.00 × 23.00 m** (184 m²). Frente y = 0 (calle), fondo y = 23.
- Jardín frontal y 0–4; vivienda y 4–21 (profundidad construida **17 m**); jardín
  posterior y 21–23.
- Entre piso 2.80 m → 16 alzadas × 0.175 m; escalera en U, ancho útil 0.90 m.
- Piso 1 al origen; Piso 2 desplazado X +16 **solo para dibujo** (verificar alineación
  vertical por superposición).

## 1. Correcciones críticas

1. **Ventanas laterales vs. tipo de lote.** El plano abre ventanas en x = 0 y x = 8 en
   casi todos los ambientes. En un lote de 8 m de ancho **entre medianeras** eso es
   imposible. Definir si el lote es aislado/esquinero (retiros laterales) o entre
   medianeras (eliminar ventanas laterales).
2. **Falta patio de luz central.** Con 17 m de profundidad y solo fachada frontal y
   posterior, hay ambientes sin luz ni ventilación (cocina, lavandería, SS.HH.1,
   pasillo, garaje, corredor). Añadir un patio de ~2.5–3.0 m en la zona media
   (junto a escalera/baños) que además sirva de ducto sanitario.
3. **Baños no apilados.** `SS.HH.1` (PB, x 0–1.5) y `SS.HH. NUEVO` (PA, x 4–6) no
   coinciden en vertical → dos montantes. Apilar baños para una sola bajante.
4. **Balcón posterior desalineado.** PA `BALCON POSTERIOR` (y 14.5–17.5) cae sobre PB
   `ESTAR` (interior), no sobre `TERRAZA` (y 17.5–21): voladizo de ~3 m. Alinear
   balcón sobre terraza (techo de terraza) o diseñar/apear el voladizo.
5. **SS.HH.1 = 2.25 m²** (bajo el mínimo de ~2.5 m² con WC + lavatorio). El `PASILLO`
   de 1.5 m es generoso: reducirlo a 1.0–1.2 m y ampliar el baño.

## 2. Estructura

- Definir **grilla estructural real**: columnas en ejes 0-3-5.5-8 (X) × A-B-C-D (Y);
  qué tabiques interiores (x = 3, 4, 6) bajan a cimentación.
- Faltan **planta de cimentación** (cimientos corridos/zapatas), **entrepiso** y
  **planta de techos**.
- Verificar **altura libre bajo escalera/descanso ≥ 2.10 m** en un corte.
- Escalera: fijar **huella explícita (0.25 m)** y chequear 2R + G ≈ 0.60–0.64.

## 3. Estándar de dibujo / juego de planos

Faltan para un juego de permiso: **cortes (2), elevaciones (4), planta de techos,
cimentación, instalaciones sanitaria y eléctrica, cajetín (title block), norte y cotas
de nivel (NPT ±0.00)**. Escala **1:100 en A3** para una planta completa (1:50 no entra).
Agregar sombreado/**poche** de muros (herramienta `create_hatch`) y cajetín.
Capas sugeridas: `A-CIMENT`, `A-CUBIERTA`, `A-INST-SAN`, `A-INST-ELE`, `A-ANOT`.

## 4. Recomendaciones técnicas del proyecto (MCP)

- **Láminas por planta:** el viewport propio de AutoCAD no se reencuadra por COM; lo
  más fiable es **un DWG por planta** (o XREF) con su lámina.
- **Cotas robustas:** `create_dimension` falla por `RPC_E_CALL_REJECTED`; conviene que
  `model_space()` y los `AddDim*` reintenten.
- **Precisión de cotas:** `SetVariable("DIMDEC")` no se adhiere al estilo en AutoCAD
  2026; la vía fiable es `set_dimension_precision` (DIMOVERRIDE).
- **Versionar los scripts** del dibujo dentro del repo y **guardar el DWG**.

## 5. Plan propuesto

- **Sprint A — Completar planta:** cortes + elevaciones + planta de techos + cajetín +
  norte + niveles.
- **Sprint B — Estructura:** cimentación + cuadro de columnas/vigas + grilla.
- **Sprint C — Instalaciones:** sanitaria y eléctrica (esquemáticos).
- **Sprint D — MCP:** herramienta de poche (`create_hatch`), cajetín, cotas con retry,
  smoke test de la vivienda.
- **Sprint E — Correcciones de diseño:** patio de luz, apilado de baños, alineación
  balcón/terraza, tamaño de SS.HH.1.
