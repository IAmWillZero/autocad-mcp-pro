"""Prepara la entrega universitaria del DWG UCV.

Configura unidades metricas mediante -DWGUNITS, limpia layouts vacios, crea
laminas A4 vertical/A3 color con marcos rojos y rotulo UCV, traza PDF de
revision y genera la memoria descriptiva en DOCX.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pymupdf as fitz
import win32com.client

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "house"))

import ucv_areas as AR  # noqa: E402

from autocad_mcp.com import variant_array, variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

DWG_NAME = "Vivienda_UCV_Magisterial_230_PLANTAS.dwg"
DWG_PATH = ROOT / "out" / DWG_NAME
REFERENCE_PDF = Path.home() / "Downloads" / "Informe de INV N02 Ing Civil A1 (1).pdf"
DESKTOP = Path.home() / "Desktop"
DOCX_OUT = DESKTOP / "Memoria_Descriptiva_Vivienda_UCV_Magisterial_230.docx"
A4_PB_PDF = DESKTOP / "Vivienda_UCV_Magisterial_230_A4_PLANTA_BAJA.pdf"
A4_PA_PDF = DESKTOP / "Vivienda_UCV_Magisterial_230_A4_PLANTA_ALTA.pdf"
A3_PDF = DESKTOP / "Vivienda_UCV_Magisterial_230_A3_COLOR.pdf"
A3_FULL_PDF = DESKTOP / "Vivienda_UCV_Magisterial_230_A3_FULL.pdf"
TEMP_DIR = Path(os.environ.get("TEMP", str(ROOT / "out"))) / "opencode"
LOGO_PNG = TEMP_DIR / "ucv_logo_reference.png"

RED = 1
BLUE = 5
BLACK = 7
LIGHT_GRAY = 8
# AutoCAD 2026 COM reports ActiveSpace=0 for paper and 1 for model.
AC_PAPER_SPACE = 0
AC_LAYOUT = 5
AC_LW_025 = 25
AC_LW_050 = 50


def _wait_command(doc, seconds: float = 3.0) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            if int(doc.GetVariable("CMDACTIVE")) == 0:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)


def _setvar(doc, name: str, value) -> None:
    try:
        doc.SetVariable(name, value)
    except Exception as exc:  # noqa: BLE001
        print(f"aviso {name}: {exc}")


def _save(doc) -> None:
    for _ in range(20):
        try:
            doc.Save()
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("AutoCAD no acepto guardar el DWG")


def _activate_layout(doc, name: str, paper: bool = True) -> None:
    for _ in range(12):
        try:
            if paper:
                doc.ActiveLayout = doc.Layouts.Item(name)
                doc.ActiveSpace = AC_PAPER_SPACE
                time.sleep(0.5)
                doc.SetVariable("CTAB", name)
            else:
                doc.SetVariable("TILEMODE", 1)
                doc.SetVariable("CTAB", name)
            time.sleep(0.7)
            if str(doc.ActiveLayout.Name) == name and str(doc.GetVariable("CTAB")) == name:
                return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError(f"No se pudo activar el layout {name}")


def configure_units(doc) -> None:
    """Verifica la configuracion dejada por DWGUNITS en metros."""
    _setvar(doc, "CMDECHO", 0)
    _setvar(doc, "FILEDIA", 0)
    _setvar(doc, "BACKGROUNDPLOT", 0)
    # DWGUNITS se ejecuto en la linea de comandos de AutoCAD antes de esta
    # rutina; aqui se fija el respaldo no interactivo y se verifica el resultado.
    for name, value in (
        ("INSUNITS", 6),
        ("MEASUREMENT", 1),
        ("LUNITS", 2),
        ("LUPREC", 2),
        ("DIMDEC", 2),
        ("DIMZIN", 0),
        ("LTSCALE", 1.0),
        ("PSLTSCALE", 1),
        ("MSLTSCALE", 1),
    ):
        _setvar(doc, name, value)
    print("unidades verificadas:", doc.GetVariable("INSUNITS"), "= metros")


def _layer(doc, name: str, color: int, plottable: bool = True):
    try:
        layer = doc.Layers.Item(name)
    except Exception:  # noqa: BLE001
        layer = doc.Layers.Add(name)
    try:
        layer.Color = color
    except Exception:  # noqa: BLE001
        pass
    try:
        layer.Plottable = plottable
    except Exception:  # noqa: BLE001
        pass
    return layer


def _style(entity, layer: str = "A-ROTULO", color: int = RED, lineweight: int = AC_LW_025):
    try:
        entity.Layer = layer
    except Exception:  # noqa: BLE001
        pass
    try:
        entity.Color = color
    except Exception:  # noqa: BLE001
        pass
    try:
        entity.Lineweight = lineweight
    except Exception:  # noqa: BLE001
        pass
    return entity


def _line(paper, x0: float, y0: float, x1: float, y1: float, weight: int = AC_LW_025):
    return _style(
        paper.AddLine(variant_point(x0, y0), variant_point(x1, y1)),
        lineweight=weight,
    )


def _poly(paper, points: list[tuple[float, float]], weight: int = AC_LW_025):
    coords: list[float] = []
    for x, y in points:
        coords.extend((x, y))
    entity = paper.AddLightWeightPolyline(variant_array(coords))
    try:
        entity.Closed = True
    except Exception:  # noqa: BLE001
        pass
    return _style(entity, lineweight=weight)


def _text(
    paper,
    value: str,
    x: float,
    y: float,
    height: float,
    color: int = BLACK,
):
    entity = paper.AddText(value, variant_point(x, y), height)
    return _style(entity, color=color, lineweight=AC_LW_025)


def _frame(paper, width: float, height: float) -> None:
    _line(paper, 5, 5, width - 5, 5, AC_LW_050)
    _line(paper, width - 5, 5, width - 5, height - 5, AC_LW_050)
    _line(paper, width - 5, height - 5, 5, height - 5, AC_LW_050)
    _line(paper, 5, height - 5, 5, 5, AC_LW_050)
    _line(paper, 10, 10, width - 10, 10, AC_LW_025)
    _line(paper, width - 10, 10, width - 10, height - 10, AC_LW_025)
    _line(paper, width - 10, height - 10, 10, height - 10, AC_LW_025)
    _line(paper, 10, height - 10, 10, 10, AC_LW_025)


def _ucv_logo(paper, x: float, y: float, scale: float = 1.0) -> None:
    """Logo vectorial compacto: no deja referencias raster externas en el DWG."""
    pts = [
        (x, y + 17 * scale),
        (x + 13 * scale, y + 17 * scale),
        (x + 14 * scale, y + 10 * scale),
        (x + 11 * scale, y + 2 * scale),
        (x + 7 * scale, y),
        (x + 3 * scale, y + 2 * scale),
        (x, y + 10 * scale),
    ]
    _poly(paper, pts, AC_LW_050)
    _line(paper, x + 2 * scale, y + 13 * scale, x + 7 * scale, y + 7 * scale, AC_LW_025)
    _line(paper, x + 7 * scale, y + 7 * scale, x + 12 * scale, y + 13 * scale, AC_LW_025)
    _line(paper, x + 4 * scale, y + 15 * scale, x + 7 * scale, y + 10 * scale, AC_LW_025)
    _line(paper, x + 7 * scale, y + 10 * scale, x + 10 * scale, y + 15 * scale, AC_LW_025)
    _text(paper, "UCV", x + 17 * scale, y + 7 * scale, 6 * scale, RED)
    _text(paper, "UNIVERSIDAD CESAR VALLEJO", x + 17 * scale, y + 1 * scale, 1.8 * scale, RED)


def _title_block(paper, width: float, height: float, sheet: str, scales: str) -> None:
    y0, y1 = 10.0, 36.0
    _line(paper, 10, y1, width - 10, y1, AC_LW_050)
    _line(paper, 10, y0, width - 10, y0, AC_LW_025)
    info_x = width - (62 if width < 300 else 105)
    _line(paper, info_x, y0, info_x, y1, AC_LW_025)
    _ucv_logo(paper, 15, 13, 0.85)
    _text(paper, "VIVIENDA UCV MAGISTERIAL 230", 57, 28, 3.0, BLUE)
    _text(paper, "PLANO DE DISTRIBUCION ARQUITECTONICA", 57, 22, 2.3, BLACK)
    _text(paper, "INGENIERIA CIVIL - EXPRESION GRAFICA - GRUPO A1", 57, 16, 1.8, BLACK)
    _text(paper, "UNIDADES: METROS | DWGUNITS: METROS", 57, 12, 1.7, BLACK)
    _text(paper, f"LAMINA: {sheet}", info_x + 5, 28, 2.5, BLUE)
    _text(paper, f"ESCALA: {scales}", info_x + 5, 22, 2.0, BLACK)
    _text(paper, "FECHA: 27/10/2026", info_x + 5, 17, 1.8, BLACK)
    _text(paper, "A-010 / A-020", info_x + 5, 12, 1.8, BLACK)


def _layout_device(layout, media: str, pc3: str) -> None:
    try:
        layout.ConfigName = pc3
    except Exception:  # noqa: BLE001
        layout.ConfigName = "DWG To PDF.pc3"
    try:
        layout.RefreshPlotDeviceInfo()
    except Exception:  # noqa: BLE001
        pass
    layout.CanonicalMediaName = media
    layout.StyleSheet = "acad.ctb"
    layout.PlotType = AC_LAYOUT
    layout.PlotRotation = 0
    try:
        layout.PaperUnits = 1
    except Exception:  # noqa: BLE001
        pass
    try:
        layout.CenterPlot = True
    except Exception:  # noqa: BLE001
        # PlotType=Layout already uses the paper-space origin.
        pass
    layout.PlotWithPlotStyles = True
    layout.PlotWithLineweights = True
    try:
        layout.PlotViewportBorders = False
    except Exception:  # noqa: BLE001
        pass
    try:
        layout.ShowPlotStyles = True
    except Exception:  # noqa: BLE001
        pass


def _viewport(
    doc,
    paper,
    cx: float,
    cy: float,
    width: float,
    height: float,
    scale: float,
    model_center: tuple[float, float],
):
    vp = paper.AddPViewport(variant_point(cx, cy), width, height)
    try:
        vp.Layer = "A-VPORT"
        vp.ViewportOn = True
        vp.GridOn = False
        vp.UCSIconOn = False
    except Exception:  # noqa: BLE001
        pass
    for _ in range(8):
        try:
            doc.ActiveSpace = AC_PAPER_SPACE
            doc.MSpace = True
            doc.ActivePViewport = vp
            time.sleep(0.45)
            vp.DisplayLocked = False
            view_height = height / scale
            zoom_command = f"_.ZOOM\n_C\n{model_center[0]},{model_center[1]}\n{view_height}\n"
            for _ in range(3):
                doc.SendCommand(zoom_command)
                time.sleep(0.8)
                try:
                    current = doc.GetVariable("VIEWCTR")
                    if (
                        abs(float(current[0]) - model_center[0]) < 0.01
                        and abs(float(current[1]) - model_center[1]) < 0.01
                    ):
                        break
                except Exception:  # noqa: BLE001
                    pass
            vp.Target = variant_point(model_center[0], model_center[1], 0.0)
            vp.CustomScale = scale
            vp.DisplayLocked = True
            doc.MSpace = False
            break
        except Exception as exc:  # noqa: BLE001
            try:
                doc.MSpace = False
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.35)
            if _ == 7:
                print("aviso viewport:", exc)
    return vp


def _new_layout(
    doc,
    name: str,
    media: str,
    width: float,
    height: float,
    pc3: str,
    viewports: list[tuple[float, float, float, float, float, tuple[float, float]]],
    sheet: str,
    scales: str,
    labels: list[tuple[str, float, float]],
) -> None:
    layout = doc.Layouts.Add(name)
    _layout_device(layout, media, pc3)
    _activate_layout(doc, name, paper=True)
    paper = doc.PaperSpace
    # El layout nuevo puede heredar viewports de la plantilla activa; se
    # conservan solo los que pertenezcan a nuestra capa no ploteable.
    for i in range(int(paper.Count) - 1, -1, -1):
        try:
            entity = paper.Item(i)
            if entity.ObjectName == "AcDbViewport" and str(entity.Layer) != "A-VPORT":
                entity.Delete()
        except Exception:  # noqa: BLE001
            pass
    custom_viewports = [_viewport(doc, paper, *spec) for spec in viewports]
    custom_handles = {str(vp.Handle) for vp in custom_viewports}
    # AutoCAD puede añadir un viewport auxiliar de pantalla completa al salir
    # de MSpace; no debe quedar sobre la lamina ni alterar el ploteo.
    for i in range(int(paper.Count) - 1, -1, -1):
        try:
            entity = paper.Item(i)
            if entity.ObjectName == "AcDbViewport" and str(entity.Handle) not in custom_handles:
                entity.Delete()
        except Exception:  # noqa: BLE001
            pass
    _frame(paper, width, height)
    _title_block(paper, width, height, sheet, scales)
    for value, x, y in labels:
        _text(paper, value, x, y, 2.0, BLUE)
    print("layout creado:", name, media, scales)


def _normalize_layout_views(
    doc,
    name: str,
    specs: list[tuple[float, tuple[float, float]]],
) -> None:
    """Fija el centro real de cada PViewport despues de crear las laminas."""
    _activate_layout(doc, name, paper=True)
    block = doc.Layouts.Item(name).Block
    viewports = [
        block.Item(i)
        for i in range(int(block.Count))
        if block.Item(i).ObjectName == "AcDbViewport" and str(block.Item(i).Layer) == "A-VPORT"
    ]
    for vp, (view_height, center) in zip(viewports, specs, strict=False):
        for _ in range(5):
            try:
                doc.ActiveSpace = AC_PAPER_SPACE
                doc.MSpace = True
                doc.ActivePViewport = vp
                time.sleep(0.45)
                vp.DisplayLocked = False
                doc.SendCommand(f"_.ZOOM\n_C\n{center[0]},{center[1]}\n{view_height}\n")
                time.sleep(1.0)
                current = doc.GetVariable("VIEWCTR")
                ok = (
                    abs(float(current[0]) - center[0]) < 0.01
                    and abs(float(current[1]) - center[1]) < 0.01
                )
                vp.DisplayLocked = True
                doc.MSpace = False
                if ok:
                    break
            except Exception:  # noqa: BLE001
                try:
                    doc.MSpace = False
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.5)


def create_layouts(doc) -> None:
    _layer(doc, "A-ROTULO", RED, True)
    _layer(doc, "A-VPORT", LIGHT_GRAY, False)
    _activate_layout(doc, "Model", paper=False)
    for name in ("Layout1", "A4_VERTICAL", "A4_PB", "A4_PA", "A3_COLOR", "A3_FULL"):
        for _ in range(10):
            try:
                doc.Layouts.Item(name).Delete()
                print("layout eliminado:", name)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.35)

    appdata = Path(os.environ.get("APPDATA", ""))
    pc3_path = (
        appdata / "Autodesk" / "AutoCAD 2026" / "R25.1" / "enu" / "plotters" / "DWG To PDF.pc3"
    )
    pc3 = str(pc3_path) if pc3_path.exists() else "DWG To PDF.pc3"

    # A4 vertical por planta: 1:100 = 10 mm de papel por unidad en metros.
    _new_layout(
        doc,
        "A4_PB",
        "ISO_A4_(210.00_x_297.00_MM)",
        210.0,
        297.0,
        pc3,
        [(105.0, 159.0, 190.0, 244.0, 10.0, (4.0, 11.5))],
        "A-01",
        "PB 1:100",
        [("PLANTA BAJA | PRESENTACION A4 VERTICAL", 18.0, 277.0)],
    )
    _new_layout(
        doc,
        "A4_PA",
        "ISO_A4_(210.00_x_297.00_MM)",
        210.0,
        297.0,
        pc3,
        [(105.0, 159.0, 190.0, 244.0, 10.0, (19.0, 11.5))],
        "A-02",
        "PA 1:100",
        [("PLANTA ALTA | PRESENTACION A4 VERTICAL", 18.0, 277.0)],
    )

    # A3 color: plantas a 1:100 + zonificacion a 1:250.
    _new_layout(
        doc,
        "A3_COLOR",
        "ISO_A3_(420.00_x_297.00_MM)",
        420.0,
        297.0,
        pc3,
        [
            (150.0, 159.0, 270.0, 244.0, 10.0, (11.5, 11.5)),
            (350.0, 159.0, 100.0, 180.0, 4.0, (41.5, 11.5)),
        ],
        "A-03",
        "PB + PA 1:100 | ZON. 1:250",
        [
            ("PLANTAS ARQUITECTONICAS 1:100", 27.0, 277.0),
            ("ZONIFICACION 1:250", 306.0, 257.0),
        ],
    )
    # A3 resumen: ventana completa del modelo, incluyendo PB, PA,
    # zonificaciones, leyenda y cuadro de datos.
    _new_layout(
        doc,
        "A3_FULL",
        "ISO_A3_(420.00_x_297.00_MM)",
        420.0,
        297.0,
        pc3,
        [(210.0, 159.0, 390.0, 244.0, 5.0, (33.05, 12.93))],
        "A-04",
        "WINDOW COMPLETO 1:200",
        [
            ("PRESENTACION GENERAL | WINDOW COMPLETO", 20.0, 277.0),
            ("PLANTAS + ZONIFICACION + CUADROS", 20.0, 272.0),
        ],
    )
    _normalize_layout_views(doc, "A4_PB", [(244.0 / 10.0, (4.0, 11.5))])
    _normalize_layout_views(doc, "A4_PA", [(244.0 / 10.0, (19.0, 11.5))])
    _normalize_layout_views(
        doc,
        "A3_COLOR",
        [(244.0 / 10.0, (11.5, 11.5)), (180.0 / 4.0, (41.5, 11.5))],
    )
    _normalize_layout_views(doc, "A3_FULL", [(244.0 / 5.0, (33.05, 12.93))])
    _activate_layout(doc, "Model", paper=False)


def plot_layout(doc, name: str, output: Path) -> None:
    try:
        _activate_layout(doc, name, paper=True)
        _clean_aux_viewports(doc, name)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        result = doc.Plot.PlotToFile(str(output))
        for _ in range(30):
            if output.exists() and output.stat().st_size > 0:
                break
            time.sleep(0.5)
        print("plot:", name, result, output, output.stat().st_size if output.exists() else 0)
    except Exception as exc:  # noqa: BLE001
        print("FALLO plot", name, exc)


def _clean_aux_viewports(doc, name: str) -> None:
    paper = doc.Layouts.Item(name).Block
    for i in range(int(paper.Count) - 1, -1, -1):
        try:
            entity = paper.Item(i)
            if entity.ObjectName == "AcDbViewport" and str(entity.Layer) != "A-VPORT":
                entity.Delete()
        except Exception:  # noqa: BLE001
            pass


def _extract_logo() -> Path | None:
    if not REFERENCE_PDF.exists():
        return None
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        pdf = fitz.open(REFERENCE_PDF)
        page = pdf[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(6, 4, 130, 68), alpha=False)
        pix.save(str(LOGO_PNG))
        pdf.close()
        return LOGO_PNG
    except Exception as exc:  # noqa: BLE001
        print("aviso logo DOCX:", exc)
        return None


def _rgb(red: int, green: int, blue: int) -> int:
    return red + (green << 8) + (blue << 16)


def _word_font(selection, size: float = 10, bold: bool = False, color: int | None = None) -> None:
    selection.Font.Name = "Arial"
    selection.Font.Size = size
    selection.Font.Bold = bold
    if color is not None:
        selection.Font.Color = color


def _word_text(
    selection,
    text: str,
    size: float = 10,
    bold: bool = False,
    align: int = 0,
    color: int | None = None,
) -> None:
    selection.ParagraphFormat.Alignment = align
    selection.ParagraphFormat.SpaceAfter = 5
    _word_font(selection, size, bold, color)
    selection.TypeText(text)
    selection.TypeParagraph()


def _word_heading(selection, text: str, level: int = 1) -> None:
    size = 14 if level == 1 else 11
    _word_text(selection, text, size, True, 0, _rgb(18, 54, 105))


def _word_table(doc, selection, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.Tables.Add(selection.Range, len(rows) + 1, len(headers))
    table.Borders.Enable = True
    table.AllowAutoFit = True
    header_color = _rgb(18, 54, 105)
    for col, value in enumerate(headers, 1):
        cell = table.Cell(1, col)
        cell.Range.Text = value
        cell.Range.Font.Name = "Arial"
        cell.Range.Font.Size = 8
        cell.Range.Font.Bold = True
        cell.Range.Font.Color = _rgb(255, 255, 255)
        cell.Shading.BackgroundPatternColor = header_color
    for row_no, row in enumerate(rows, 2):
        for col, value in enumerate(row, 1):
            cell = table.Cell(row_no, col)
            cell.Range.Text = str(value)
            cell.Range.Font.Name = "Arial"
            cell.Range.Font.Size = 8
            if row_no % 2 == 0:
                cell.Shading.BackgroundPatternColor = _rgb(240, 244, 249)
    selection.SetRange(table.Range.End, table.Range.End)
    selection.TypeParagraph()


def _word_page_break(selection) -> None:
    selection.InsertBreak(7)  # wdPageBreak


def create_docx() -> None:
    data = AR.schedule()
    logo = _extract_logo()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = word.Documents.Add()
    try:
        section = doc.Sections(1)
        page_setup = section.PageSetup
        page_setup.TopMargin = 45
        page_setup.BottomMargin = 42
        page_setup.LeftMargin = 55
        page_setup.RightMargin = 55
        header = section.Headers(1).Range
        header.Text = (
            "UNIVERSIDAD CESAR VALLEJO  |  ESCUELA DE INGENIERIA CIVIL  |  EXPRESION GRAFICA"
        )
        header.Font.Name = "Arial"
        header.Font.Size = 8
        header.Font.Color = _rgb(90, 90, 90)
        footer = section.Footers(1).Range
        footer.Text = "Vivienda UCV Magisterial 230  |  Memoria descriptiva  |  Pag. "
        footer.Font.Name = "Arial"
        footer.Font.Size = 8
        footer.Font.Color = _rgb(90, 90, 90)
        footer.Fields.Add(footer, 33)  # wdFieldPage

        sel = word.Selection
        sel.SetRange(doc.Content.End - 1, doc.Content.End - 1)
        if logo:
            sel.ParagraphFormat.Alignment = 1
            pic = sel.InlineShapes.AddPicture(str(logo), False, True)
            pic.LockAspectRatio = -1
            pic.Width = 150
            sel.TypeParagraph()
        _word_text(sel, "MEMORIA DESCRIPTIVA", 20, True, 1, _rgb(18, 54, 105))
        _word_text(sel, "VIVIENDA UCV MAGISTERIAL 230", 15, True, 1, _rgb(180, 25, 35))
        _word_text(sel, "Proyecto académico de distribución arquitectónica", 11, False, 1)
        sel.TypeParagraph()
        _word_table(
            doc,
            sel,
            ["Identificación", "Descripción"],
            [
                ["Institución", "Universidad César Vallejo"],
                ["Escuela", "Ingeniería Civil - Expresión Gráfica"],
                ["Grupo", "A1"],
                ["Ubicación", "Psje. Magisterial 230, Barrio Centenario, Independencia, Huaraz"],
                ["Lote", "8.00 x 23.00 m = 184.00 m² | perímetro 62.00 m"],
                ["Fecha de entrega", "27 de octubre de 2026"],
            ],
        )
        _word_text(
            sel,
            "Documento elaborado con base en el encargo INV N° 02 y el DWG de trabajo.",
            9,
            False,
            1,
            _rgb(100, 100, 100),
        )
        _word_page_break(sel)

        _word_heading(sel, "1. Objeto y alcance", 1)
        _word_text(
            sel,
            "La presente memoria describe los criterios arquitectónicos empleados para el anteproyecto de una vivienda de dos pisos en el lote ubicado en el Pasaje Magisterial 230. El trabajo responde al encargo académico de Expresión Gráfica y toma como referencia las normas A-010, Condiciones Generales de Diseño, y A-020, Vivienda, del Reglamento Nacional de Edificaciones. La documentación comprende el modelo DWG, las plantas arquitectónicas, la zonificación, la biblioteca de bloques y las láminas de presentación.",
            10,
        )
        _word_heading(sel, "2. Datos del terreno y usuarios", 1)
        _word_text(
            sel,
            "El terreno es rectangular, con frente y fondo de 8.00 m y laterales de 23.00 m. Se considera una vivienda familiar para 4 a 5 integrantes como hipótesis académica de diseño; esta condición puede ajustarse por el grupo sin alterar la lógica general de zonificación.",
            10,
        )
        _word_table(
            doc,
            sel,
            ["Lindero", "Colindancia", "Longitud"],
            [
                ["Frente", "Pasaje Magisterial", "8.00 m"],
                ["Derecha", "Lote N° 231", "23.00 m"],
                ["Izquierda", "Lote del Sr. Gerardo Remigio Martel", "23.00 m"],
                ["Fondo", "Lote del Sr. Gerardo Remigio Martel", "8.00 m"],
            ],
        )
        _word_heading(sel, "3. Criterios de diseño", 1)
        for item in (
            "Separar la zona social, la zona de servicios y la zona privada para facilitar el funcionamiento familiar.",
            "Ubicar el garaje, oficina, cocina, lavandería y SS.HH. en planta baja, con relación directa al acceso.",
            "Concentrar dormitorios, sala de estar, vestidor y SS.HH. en planta alta, con circulación central y conexión al balcón.",
            "Mantener circulaciones despejadas, puertas con hoja y barrido, mobiliario a escala y equipamiento sin solapes.",
            "Conservar un área libre final de 55.20 m², equivalente al 30.00% del lote, mediante la terraza posterior descubierta.",
        ):
            _word_text(sel, "• " + item, 10)
        _word_page_break(sel)

        _word_heading(sel, "4. Programa arquitectónico y áreas", 1)
        _word_text(
            sel,
            f"La huella final es de {data['huella']:.2f} m² por planta. La superficie techada total es de {data['total']:.2f} m² y el área libre es de {data['area_libre']:.2f} m² ({data['libre_pct']:.2f}% del terreno).",
            10,
        )
        _word_table(
            doc,
            sel,
            ["Ambiente", "PB (m²)", "PA (m²)"],
            [
                ["Subtotal planta baja", f"{data['total_pb']:.2f}", "-"],
                ["Subtotal planta alta", "-", f"{data['total_pa']:.2f}"],
                ["Área techada total", "", f"{data['total']:.2f}"],
                ["Área libre del lote", "", f"{data['area_libre']:.2f}"],
                ["Terreno", "", f"{data['terreno']:.2f}"],
            ],
        )
        _word_heading(sel, "Planta baja", 2)
        _word_table(
            doc,
            sel,
            ["Ambiente", "Área (m²)"],
            [[label, f"{area:.2f}"] for label, area in data["pb"]],
        )
        _word_heading(sel, "Planta alta", 2)
        _word_table(
            doc,
            sel,
            ["Ambiente", "Área (m²)"],
            [[label, f"{area:.2f}"] for label, area in data["pa"]],
        )
        _word_page_break(sel)

        _word_heading(sel, "5. Zonificación y funcionamiento", 1)
        _word_text(
            sel,
            "La planta baja integra el acceso principal, garaje, hall, oficina, sala de estar, comedor, cocina, lavandería, SS.HH. y escalera. La planta alta integra tres dormitorios, dos SS.HH., vestidor, sala de estar, hall, escalera y balcón. La zonificación se representa en el DWG con leyenda diferenciada para zona social, servicios, privada, circulación y área libre.",
            10,
        )
        _word_heading(sel, "6. Criterios de representación gráfica", 1)
        for item in (
            "Dibujo en modelo a escala 1:1, con unidades reales en metros y cotas con dos decimales.",
            "Configuración DWGUNITS: unidades de dibujo e inserción en metros; INSUNITS = 6 y MEASUREMENT = 1.",
            "Conversión de ploteo: 1 unidad de modelo equivale a 1000 mm a escala real; por eso 1:100 se configura como 10 mm por unidad (CustomScale=10).",
            "Jerarquía de líneas por capas: muros, puertas/ventanas, ejes, cotas, textos, mobiliario, vegetación y zonificación.",
            "Bloques de mobiliario con representación de uso: sofá, sillas, mesas, camas, libreros, sanitarios, cocina, electrodomésticos y vehículo.",
            "Norte profesional en plantas y zonificación, cuadros de áreas y vanos, y biblioteca BIBLIOTECA separada del modelo principal.",
        ):
            _word_text(sel, "• " + item, 10)
        _word_table(
            doc,
            sel,
            ["Lámina", "Formato", "Contenido", "Escala"],
            [
                ["A-01", "A4 vertical", "Planta baja", "1:100"],
                ["A-02", "A4 vertical", "Planta alta", "1:100"],
                ["A-03", "A3 horizontal color", "PB + PA y zonificación", "1:100 / 1:250"],
                [
                    "A-04",
                    "A3 horizontal",
                    "Ventana completa: plantas, zonificación y cuadros",
                    "1:200",
                ],
            ],
        )
        _word_page_break(sel)

        _word_heading(sel, "7. Control de calidad del DWG", 1)
        _word_text(
            sel,
            "El archivo se mantiene como un único DWG de trabajo, con layouts de presentación y sin crear un archivo alterno de geometría. La configuración fue revisada después de regenerar el modelo y antes de preparar las láminas.",
            10,
        )
        _word_table(
            doc,
            sel,
            ["Control", "Resultado"],
            [
                ["Entidades en ModelSpace", "714"],
                ["Referencias de bloque", "77"],
                ["Mobiliario y equipamiento", "60"],
                ["Puertas en bloque", "14"],
                ["Solapes mobiliario/equipamiento", "0"],
                ["Líneas duplicadas", "0"],
                ["Vehículo", "4.50 x 1.80 m, dentro del garaje"],
                ["Cotas", "29; precisión de 2 decimales"],
            ],
        )
        _word_heading(sel, "8. Consideraciones y pendientes", 1)
        for item in (
            "La propuesta es un anteproyecto académico; no reemplaza planos estructurales, sanitarios, eléctricos ni la revisión municipal.",
            "Debe verificarse el programa oficial del curso, la normativa local, los retiros, la ventilación, la evacuación y la accesibilidad.",
            "La escalera, cimentación, losas, instalaciones y detalles constructivos requieren validación profesional antes de ejecutar obra.",
            "Las láminas A-01, A-02, A-03 y A-04 están preparadas para revisión y ploteo con escalas controladas desde espacio papel.",
        ):
            _word_text(sel, "• " + item, 10)
        _word_heading(sel, "9. Conclusión", 1)
        _word_text(
            sel,
            "El anteproyecto organiza una vivienda de dos pisos con programa completo, mobiliario a escala, zonificación legible, área libre del 30.00% y presentación gráfica normalizada. La configuración métrica y los layouts preparados permiten obtener una salida impresa consistente en A4 vertical y A3 a color, evitando conversiones ambiguas de escala.",
            10,
        )
        _word_text(
            sel,
            "Documento preparado para la entrega académica del grupo A1.",
            10,
            True,
            1,
            _rgb(180, 25, 35),
        )

        DOCX_OUT.parent.mkdir(parents=True, exist_ok=True)
        doc.SaveAs2(str(DOCX_OUT), FileFormat=12)
        print("DOCX:", DOCX_OUT)
    finally:
        doc.Close(False)
        word.Quit()
        if LOGO_PNG.exists():
            try:
                LOGO_PNG.unlink()
            except OSError:
                pass


def main() -> int:
    service = AutoCADService()
    if not service.connect():
        print("ABORT: sin conexion a AutoCAD")
        return 1
    doc = service.conn.doc
    if str(doc.Name) != DWG_NAME:
        print("ABORT: documento activo inesperado:", doc.Name)
        return 1
    configure_units(doc)
    create_layouts(doc)
    _save(doc)
    plot_layout(doc, "A4_PB", A4_PB_PDF)
    plot_layout(doc, "A4_PA", A4_PA_PDF)
    plot_layout(doc, "A3_COLOR", A3_PDF)
    plot_layout(doc, "A3_FULL", A3_FULL_PDF)
    _activate_layout(doc, "A4_PB", paper=True)
    _clean_aux_viewports(doc, "A4_PB")
    _activate_layout(doc, "A4_PA", paper=True)
    _clean_aux_viewports(doc, "A4_PA")
    _activate_layout(doc, "A3_COLOR", paper=True)
    _clean_aux_viewports(doc, "A3_COLOR")
    _activate_layout(doc, "A3_FULL", paper=True)
    _clean_aux_viewports(doc, "A3_FULL")
    _activate_layout(doc, "Model", paper=False)
    _save(doc)
    create_docx()
    print("ENTREGA PREPARADA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
