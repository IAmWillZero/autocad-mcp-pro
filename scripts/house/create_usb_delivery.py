"""Crea una copia final para USB con papel metrico y marcos a escala real.

El modelo permanece en metros. Para cada lamina se copia al espacio papel
solo el area del modelo que se quiere mostrar, escalada al factor de la
escala grafica. El Page Setup usa 1000 mm = 1 unidad (ploteo 1:1 en papel
metrico) y los bordes del marco coinciden con las dimensiones de la hoja
(A4 o A3 full bleed).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pythoncom
import win32com.client

from autocad_mcp.com import as_dynamic, variant_array, variant_objects, variant_point

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "out" / "Vivienda_UCV_Magisterial_230_PLANTAS.dwg"
USB = Path("D:/UCV_MAGISTERIAL_230_ENTREGA")
DWG = USB / "Vivienda_UCV_Magisterial_230_ENTREGA.dwg"
DESKTOP = Path.home() / "Desktop"
PDFS = {
    "A4_PB": USB / "Vivienda_UCV_Magisterial_230_A4_PLANTA_BAJA.pdf",
    "A4_PA": USB / "Vivienda_UCV_Magisterial_230_A4_PLANTA_ALTA.pdf",
    "A3_COLOR": USB / "Vivienda_UCV_Magisterial_230_A3_COLOR.pdf",
    "A3_FULL": USB / "Vivienda_UCV_Magisterial_230_A3_FULL.pdf",
}

RED = 1
BLUE = 5
BLACK = 7
WHITE = 7
PAPER = 0

LOGO_POLYS = [
    [229.222346075916, -47.401379218187, 268.478965085991, -49.012225331199,
     268.478965085991, -53.368825654130, 229.222346075916, -47.401379218187],
    [229.222346075912, -47.401379218182, 268.432726176950, -57.307440275650,
     268.432726176950, -77.176825260045, 263.346370946074, -85.872835455622,
     263.346370946078, -60.433182871121, 229.222346075912, -47.401379218182],
    [229.222346075912, -47.401379218182, 258.807402759940, -63.354031642844,
     258.807402759940, -88.666439703912, 253.578259830000, -93.317433149806,
     253.578259830000, -65.934055057211, 229.222346075858, -47.401379218142],
]


def _layer(doc, name: str, color: int, plottable: bool = True) -> None:
    try:
        layer = doc.Layers.Item(name)
    except Exception:  # noqa: BLE001
        layer = doc.Layers.Add(name)
    layer.Color = color
    try:
        layer.Plottable = plottable
    except Exception:  # noqa: BLE001
        pass
    try:
        layer.LayerOn = True
    except Exception:  # noqa: BLE001
        pass
    try:
        layer.Freeze = False
    except Exception:  # noqa: BLE001
        pass


def _activate(doc, name: str) -> None:
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item(name)
            doc.ActiveSpace = PAPER
            time.sleep(0.6)
            doc.SetVariable("CTAB", name)
            time.sleep(0.6)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.6)
    raise RuntimeError(f"No se pudo activar el layout {name}")


def _line(block, x0: float, y0: float, x1: float, y1: float, color: int = RED):
    e = block.AddLine(variant_point(x0, y0), variant_point(x1, y1))
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _text(block, value: str, x: float, y: float, height: float,
          color: int = BLACK):
    e = block.AddText(value, variant_point(x, y), height)
    e.Layer = "A-ROTULO"
    e.Color = color
    return e


def _poly(block, points: list[tuple[float, float]]):
    coords: list[float] = []
    for x, y in points:
        coords.extend((x, y))
    e = block.AddLightWeightPolyline(variant_array(coords))
    e.Closed = False
    e.Layer = "A-ROTULO"
    e.Color = RED
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _draw_sheet(block, width: float, height: float, sheet: str,
                scale_text: str, subtitle: str) -> None:
    """Marco y cajete UCV con bordes del tamanio exacto de la hoja."""
    for a in (
        (0.005, 0.005, width - 0.005, 0.005),
        (width - 0.005, 0.005, width - 0.005, height - 0.005),
        (width - 0.005, height - 0.005, 0.005, height - 0.005),
        (0.005, height - 0.005, 0.005, 0.005),
        (0.010, 0.010, width - 0.010, 0.010),
        (width - 0.010, 0.010, width - 0.010, height - 0.010),
        (width - 0.010, height - 0.010, 0.010, height - 0.010),
        (0.010, height - 0.010, 0.010, 0.010),
        (0.010, 0.036, width - 0.010, 0.036),
        (width - 0.105, 0.010, width - 0.105, 0.036),
    ):
        _line(block, *a)

    s = 0.00030
    tx = 0.015 - s * 229.2223460759
    ty = 0.013 - s * (-93.3174331498)
    for flat in LOGO_POLYS:
        _poly(block, [(tx + s * flat[i], ty + s * flat[i + 1])
                      for i in range(0, len(flat), 2)])
    _text(block, "UNIVERSIDAD CESAR VALLEJO", 0.02945, 0.01385, 0.0018, RED)
    _text(block, "VIVIENDA UCV MAGISTERIAL 230", 0.057, 0.028, 0.0030, BLUE)
    _text(block, "PLANO DE DISTRIBUCION ARQUITECTONICA", 0.057, 0.022,
          0.0023)
    _text(block, "INGENIERIA CIVIL - EXPRESION GRAFICA - GRUPO A1",
          0.057, 0.016, 0.0018)
    _text(block, "UNIDADES: METROS | DWGUNITS: METROS", 0.057, 0.012, 0.0017)
    ix = width - 0.100
    _text(block, f"LAMINA: {sheet}", ix + 0.005, 0.028, 0.0025, BLUE)
    _text(block, f"ESCALA: {scale_text}", ix + 0.005, 0.022, 0.0020)
    _text(block, "FECHA: 27/10/2026", ix + 0.005, 0.017, 0.0018)
    _text(block, "A-010 / A-020", ix + 0.005, 0.012, 0.0018)
    _text(block, subtitle, 0.020, height - 0.020, 0.0020, BLUE)


def _page_setup(doc, layout, width: float, height: float, media: str) -> None:
    pc3 = str(
        Path.home() / "AppData" / "Roaming" / "Autodesk" / "AutoCAD 2026"
        / "R25.1" / "enu" / "plotters" / "DWG To PDF.pc3"
    )
    layout.ConfigName = pc3
    try:
        layout.RefreshPlotDeviceInfo()
    except Exception:  # noqa: BLE001
        pass
    layout.CanonicalMediaName = media
    layout.StyleSheet = "acad.ctb"
    layout.PlotType = 5  # Layout: plotea el espacio papel con todo su contenido
    layout.UseStandardScale = False
    layout.SetCustomScale(1000.0, 1.0)
    layout.PlotRotation = 0
    layout.PaperUnits = 1
    layout.PlotWithPlotStyles = True
    layout.PlotWithLineweights = True
    layout.ScaleLineweights = False
    try:
        layout.PlotViewportBorders = False
        layout.CenterPlot = False
    except Exception:  # noqa: BLE001
        pass


def _clean_viewports(block) -> None:
    for i in range(int(block.Count) - 1, -1, -1):
        try:
            if block.Item(i).ObjectName == "AcDbViewport":
                block.Item(i).Delete()
        except Exception:  # noqa: BLE001
            pass


def _copy_model_area(doc, block, x0: float, y0: float, x1: float, y1: float,
                     scale: float, dx: float, dy: float) -> None:
    """Copia al espacio papel los objetos del modelo dentro del area dada,
    escalados y desplazados a la posicion (dx, dy) del papel."""
    sources = []
    for i in range(int(doc.ModelSpace.Count)):
        e = doc.ModelSpace.Item(i)
        try:
            mn, mx = e.GetBoundingBox()
            ex0, ey0 = float(mn[0]), float(mn[1])
            ex1, ey1 = float(mx[0]), float(mx[1])
            if ex1 < x0 or ex0 > x1 or ey1 < y0 or ey0 > y1:
                continue
        except Exception:  # noqa: BLE001
            continue
        sources.append(e)

    if not sources:
        return
    result = doc.CopyObjects(variant_objects(sources), block)
    copies = result[0] if isinstance(result, tuple) else result
    for raw in copies:
        ent = as_dynamic(raw)
        try:
            ent.ScaleEntity(variant_point(0, 0, 0), scale)
            ent.Move(variant_point(0, 0, 0), variant_point(dx, dy, 0))
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    USB.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    shutil.copy2(SOURCE, DWG)

    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    docs = app.Documents
    copy_doc = None
    for _ in range(15):
        try:
            for i in range(int(docs.Count)):
                d = docs.Item(i)
                if str(d.Name) == "Vivienda_UCV_Magisterial_230_ENTREGA.dwg":
                    copy_doc = d
                    break
            if copy_doc is not None:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    if copy_doc is None:
        copy_doc = docs.Open(str(DWG), False)
    copy_doc.Activate()
    copy_doc.SetVariable("INSUNITS", 6)
    copy_doc.SetVariable("MEASUREMENT", 1)
    copy_doc.SetVariable("LUNITS", 2)
    copy_doc.SetVariable("LUPREC", 2)
    copy_doc.SetVariable("DIMDEC", 2)
    copy_doc.SetVariable("DIMZIN", 0)
    copy_doc.SetVariable("BACKGROUNDPLOT", 0)

    for name, color in {
        "A-TEXTOS": 7,
        "A-COTAS": 1,
        "A-EJES": 1,
        "A-ELECTRO": 5,
        "A-MUROS-CARGA": 5,
        "A-MUROS-TABIQ": 7,
        "A-PUER-VENT": 4,
        "A-MOBILIARIO": 8,
        "A-SANITARIO": 4,
        "A-VEGETACION": 3,
        "A-ROTULO": 1,
        "Z-SOCIAL": 6,
        "Z-SERVICIOS": 5,
        "Z-PRIVADA": 3,
        "Z-CIRCULACION": 30,
        "Z-AREA-LIBRE": 3,
    }.items():
        _layer(copy_doc, name, color, True)
    _layer(copy_doc, "A-VPORT", 8, False)

    for name in ("Layout1", "A4_PB", "A4_PA", "A3_COLOR", "A3_FULL", "A4_VERTICAL"):
        try:
            copy_doc.Layouts.Item(name).Delete()
        except Exception:  # noqa: BLE001
            pass

    # (nombre, media, ancho_m, alto_m, (x0, y0, x1, y1) area del modelo,
    #  scale, centro_papel_x, centro_papel_y, sheet, escala_texto, subtitulo)
    sheets = (
        ("A4_PB", "ISO_full_bleed_A4_(210.00_x_297.00_MM)", 0.210, 0.297,
         (-0.5, 0.0, 8.5, 23.0), 0.010, 0.105, 0.159, "A-01", "PB 1:100",
         "PLANTA BAJA | A4 VERTICAL"),
        ("A4_PA", "ISO_full_bleed_A4_(210.00_x_297.00_MM)", 0.210, 0.297,
         (14.5, 0.0, 23.5, 23.0), 0.010, 0.105, 0.159, "A-02", "PA 1:100",
         "PLANTA ALTA | A4 VERTICAL"),
        ("A3_COLOR", "ISO_full_bleed_A3_(420.00_x_297.00_MM)", 0.420, 0.297,
         (-0.5, 0.0, 23.5, 23.0), 0.010, 0.150, 0.159, "A-03",
         "PB+PA 1:100 / ZON. 1:250", "PLANTAS + ZONIFICACION | A3 COLOR"),
        ("A3_FULL", "ISO_full_bleed_A3_(420.00_x_297.00_MM)", 0.420, 0.297,
         (-4.5, 0.0, 70.5, 26.0), 0.005, 0.210, 0.159, "A-04",
         "WINDOW COMPLETO 1:200",
         "PLANTAS + ZONIFICACION + CUADROS | A3 FULL"),
    )
    for name, media, w, h, model_area, scale, cx, cy, sheet, scale_text, subtitle in sheets:
        layout = copy_doc.Layouts.Add(name)
        _activate(copy_doc, name)
        _page_setup(copy_doc, layout, w, h, media)
        block = layout.Block
        _clean_viewports(block)
        _draw_sheet(block, w, h, sheet, scale_text, subtitle)

        mx0, my0, mx1, my1 = model_area
        model_w = mx1 - mx0
        model_h = my1 - my0
        paper_w = w - 0.020
        paper_h = h - 0.056
        fit_scale = min(paper_w / model_w, paper_h / model_h)
        final_scale = min(scale, fit_scale)
        dx = cx - (mx0 + mx1) / 2 * final_scale
        dy = cy - (my0 + my1) / 2 * final_scale

        _copy_model_area(copy_doc, block, mx0, my0, mx1, my1,
                         final_scale, dx, dy)

    copy_doc.ActiveLayout = copy_doc.Layouts.Item("Model")
    copy_doc.SetVariable("CTAB", "Model")
    copy_doc.Save()

    for name, out in PDFS.items():
        _activate(copy_doc, name)
        if out.exists():
            out.unlink()
        copy_doc.Plot.PlotToFile(str(out))
        for _ in range(40):
            if out.exists() and out.stat().st_size > 0:
                break
            time.sleep(0.5)
        print(name, out.stat().st_size if out.exists() else 0)

    copy_doc.ActiveLayout = copy_doc.Layouts.Item("Model")
    copy_doc.SetVariable("CTAB", "Model")
    copy_doc.Save()

    for source in (
        DESKTOP / "Memoria_Descriptiva_Vivienda_UCV_Magisterial_230.docx",
        DESKTOP / "Informe_Vivienda_UCV_Magisterial_230.pdf",
    ):
        if source.exists():
            shutil.copy2(source, USB / source.name)
    (USB / "README_ENTREGA.txt").write_text(
        "VIVIENDA UCV MAGISTERIAL 230 - ENTREGA\n"
        "DWGUNITS / INSUNITS: metros (1 unidad = 1 m)\n"
        "Page Setup: 1000 mm = 1 unidad; escalas graficas 1:100, 1:250 y 1:200.\n"
        "Laminas: A-01 PB, A-02 PA, A-03 color, A-04 full.\n",
        encoding="utf-8",
    )
    print("USB:", USB)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
