# Revisión técnica — Vivienda 8.00 × 23.00 m (2 plantas) · v2

> Documento de trabajo. Datos **provisionales** (construidos desde el programa de
> ambientes). Cada supuesto debe validarse antes de un anteproyecto definitivo.

## Datos base (v2 · revisión aplicada)

- Lote **8.00 × 23.00 m** (184 m²). Frente y = 0 (calle), fondo y = 23.
- **Retiro lateral 1.00 m por lado → ancho construible 6.00 m** (x 1.00–7.00).
- Lote **aislado**: las ventanas laterales (x = 1 y x = 7) son **válidas** (dan a los
  retiros). Ya no hay supuesto pendiente sobre ventanas laterales.
- Jardín frontal y 0–4; vivienda y 4–21 (profundidad 17 m); jardín posterior y 21–23.
- Entre piso 2.80 m → 16 alzadas × 0.175 m; escalera en U, ancho útil 0.90 m.
- Piso 1 al origen; Piso 2 desplazado X+16 **solo para dibujo**.

## Correcciones aplicadas en esta revisión

1. **Ventanas laterales** → resuelto: lote **aislado con retiros laterales**, por lo que
   las aberturas en x = 1 y x = 7 son correctas.
2. **Patio de luz central** → `PATIO DE LUZ` (x 2.50–4.00, y 13.00–15.50, 3.75 m²),
   interior, entre baño, lavandería, estar y escalera; sirve además de ducto.
3. **Baños apilados** → `SS.HH.1` (PB) y `SS.HH. NUEVO` (PA) coinciden en planta
   (x 1.00–2.50, y 13.00–15.50) → **una sola bajante**.
4. **Balcón alineado sobre la terraza** → `BALCON POSTERIOR` (PA) pasa a estar sobre
   `TERRAZA` (PB), mismo paño (x 1.00–7.00, y 18.00–21.00). Se elimina el voladizo
   sobre el estar.
5. **SS.HH.1 ≥ 2.5 m²** → 1.50 × 2.50 = **3.75 m²** (WC + lavatorio). El pasillo de
   servicio se ajustó a 1.20 m.

Además: **grillas alineadas entre plantas** (los muros principales coinciden en las
plantas Bajas y Alta, salvo el tabique del corredor en x = 5.00).

## Pendiente para un juego de permiso

- **Estructura:** grilla de columnas, planta de cimentación, entrepiso y planta de
  techos; verificar altura libre bajo escalera/descanso ≥ 2.10 m en un corte; fijar
  huella (0.25 m) y chequear 2R + G ≈ 0.60–0.64.
- **Láminas:** cortes (2), elevaciones (4), planta de techos, cajetín (title block),
  cotas de nivel (NPT ±0.00). Escala **1:100 en A3**.
- **Instalaciones:** sanitaria y eléctrica (esquemáticos).
- **Capas sugeridas** (aún no creadas): `A-CIMENT`, `A-CUBIERTA`, `A-INST-SAN`,
  `A-INST-ELE`, `A-ANOT`.

## Notas de la herramienta MCP

- **Láminas por planta:** el viewport propio de AutoCAD no se reencuadra por COM; lo
  más fiable es **un DWG por planta** (o XREF) con su lámina.
- **Cotas robustas:** `create_dimension` / `model_space()` conviene que reintenten ante
  `RPC_E_CALL_REJECTED`.
- **Precisión de cotas:** `SetVariable("DIMDEC")` no se adhiere al estilo en AutoCAD
  2026; la vía fiable es `set_dimension_precision` (DIMOVERRIDE).
- **Poche de muros:** herramienta `create_hatch` (SOLID sobre contornos cerrados).
- **Scripts del dibujo versionados** en `scripts/house/` (DWG en `out/CASA.dwg`).
