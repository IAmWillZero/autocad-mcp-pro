"""Genera la biblioteca de detalles metalicos y su lamina A1 en un DWG nuevo.

Uso:
    python scripts/bridge/build_detail_sheet.py
    python scripts/bridge/build_detail_sheet.py --no-pdf

Requiere AutoCAD abierto. Crea un dibujo nuevo (no toca los dibujos abiertos),
define los 12 bloques de detalle, compone la lamina DETALLES-ACERO, guarda el
DWG y traza un PDF A1 con ``PlotToFile``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from autocad_mcp.features.detail_sheet import (
    DETAIL_LIBRARY,
    _com_retry,
    paper_size,
)
from autocad_mcp.layers import DETAIL_LAYERS
from autocad_mcp.service import AutoCADService

OUT_DIR = Path(
    os.environ.get("DETAIL_SHEET_OUT", Path.home() / "Documents" / "BlancaNieves" / "salida")
)
DWG_NAME = "Biblioteca-Detalles-Metalicos.dwg"
PDF_NAME = "Biblioteca-Detalles-Metalicos.pdf"
LAYOUT_NAME = "DETALLES-ACERO"
EXPECTED_MEDIA = "ISO_A1"
_SCRATCH_PATTERN = re.compile(r"^drawing\d+$", re.IGNORECASE)


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _save_as(doc: Any, path: Path, attempts: int = 6) -> None:
    for attempt in range(attempts):
        try:
            doc.SaveAs(str(path))
            return
        except Exception:  # noqa: BLE001 - COM rechaza llamadas mientras esta ocupado
            if attempt == attempts - 1:
                raise
            time.sleep(1.0 * (attempt + 1))


def _close_documents(service: AutoCADService, predicate: Any) -> int:
    """Cierra los dibujos que cumplen ``predicate(name)``, re-resolviendolos.

    Los objetos ``Document`` quedan obsoletos si AutoCAD rechaza una llamada:
    hay que volver a pedirlos por nombre en cada intento.
    """
    closed = 0
    try:
        names = _com_retry(
            lambda: [
                str(service.conn.app.Documents.Item(i).Name)
                for i in range(int(service.conn.app.Documents.Count))
            ]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: no se pudieron listar los dibujos ({exc})", flush=True)
        return 0
    for name in names:
        if not predicate(name):
            continue

        def close(target: str = name) -> None:
            doc = service.conn.app.Documents.Item(target)
            doc.Close(False)

        try:
            _com_retry(close, attempts=10)
            closed += 1
            print(f"cerrado dibujo: {name}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"aviso: no se pudo cerrar {name} ({exc})", flush=True)
    return closed


def _close_previous(service: AutoCADService, name: str) -> int:
    """Cierra una version anterior del DWG para poder sobrescribirlo."""
    return _close_documents(service, lambda doc_name: doc_name.lower() == name.lower())


def _is_detail_scratch(service: AutoCADService, name: str) -> bool:
    """True si el dibujo es un ``DrawingNN.dwg`` sin guardar creado por este script.

    Una corrida fallida a mitad de composicion deja un dibujo sin ruta cuyas
    entidades solo viven en capas ``0`` o ``D-*``. Es la firma segura para
    cerrarlo sin tocar los dibujos del usuario.
    """
    if not (_SCRATCH_PATTERN.match(name) and name.lower().endswith(".dwg")):
        return False

    def probe() -> bool:
        doc = service.conn.app.Documents.Item(name)
        if str(doc.FullName):
            return False
        space = doc.ModelSpace
        for index in range(int(space.Count)):
            layer = str(space.Item(index).Layer).upper()
            if layer not in ("0", "DEFPOINTS") and not layer.startswith("D-"):
                return False
        return True

    try:
        return bool(_com_retry(probe, attempts=5))
    except Exception:  # noqa: BLE001 - no se pudo inspeccionar
        return False


def _close_stray_drawings(service: AutoCADService) -> int:
    """Cierra los ``DrawingNN.dwg`` de detalle que quedaron de corridas fallidas."""
    try:
        names = _com_retry(
            lambda: [
                str(service.conn.app.Documents.Item(i).Name)
                for i in range(int(service.conn.app.Documents.Count))
            ]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: no se pudieron listar los dibujos ({exc})", flush=True)
        return 0
    strays = [name for name in names if _is_detail_scratch(service, name)]
    return _close_documents(service, lambda doc_name: doc_name in strays)


def _verify_sheet(service: AutoCADService, result: dict[str, Any]) -> dict[str, Any]:
    """Comprueba bloques, lamina, papel y viewport leyendo el dibujo real."""
    doc = service.conn.doc
    rows: list[dict[str, Any]] = []

    block_names = {str(spec.name) for spec in DETAIL_LIBRARY}
    try:
        existing = {str(doc.Blocks.Item(index).Name) for index in range(int(doc.Blocks.Count))}
    except Exception:  # noqa: BLE001
        existing = set()
    missing = sorted(block_names - existing)
    rows.append(
        _check(
            "bloques",
            not missing,
            f"{len(block_names) - len(missing)}/{len(block_names)}"
            + (f" faltan {missing}" if missing else ""),
        )
    )

    block_sizes = {block["name"]: block["size_mm"] for block in result["blocks"]}
    empty = [name for name, size in block_sizes.items() if min(size) <= 0]
    rows.append(_check("bloques con geometria", not empty, f"vacios: {empty or 'ninguno'}"))

    try:
        layout = doc.Layouts.Item(LAYOUT_NAME)
        layout_name = str(layout.Name)
    except Exception:  # noqa: BLE001
        layout = None
        layout_name = ""
    rows.append(_check("lamina", layout is not None, layout_name or "no existe"))
    if layout is None:
        return {
            "checks": rows,
            "checks_passed": sum(1 for row in rows if row["ok"]),
            "checks_total": len(rows),
            "media": "",
            "device": "",
            "paper_size": [],
        }

    media = str(layout.CanonicalMediaName)
    device = str(layout.ConfigName)
    rows.append(_check("papel A1", media.upper().startswith(EXPECTED_MEDIA), media))
    rows.append(_check("trazador PDF", device.lower().startswith("dwg to pdf"), device))

    sheet_mm = paper_size(media)
    paper_mm = [float(sheet_mm[0]), float(sheet_mm[1])]
    rows.append(
        _check(
            "papel apaisado",
            abs(paper_mm[0] - 841.0) < 1.0 and abs(paper_mm[1] - 594.0) < 1.0,
            f"{paper_mm[0]:.0f} x {paper_mm[1]:.0f} mm (según medio)",
        )
    )
    rows.append(
        _check(
            "escala 1:1",
            int(getattr(layout, "StandardScale", -1)) == 16,
            f"StandardScale={getattr(layout, 'StandardScale', '?')}",
        )
    )

    paper = doc.PaperSpace
    viewports = []
    for index in range(int(paper.Count)):
        entity = paper.Item(index)
        if str(entity.ObjectName) == "AcDbViewport":
            viewports.append(entity)
    rows.append(_check("un viewport", len(viewports) == 1, f"{len(viewports)} viewport(s)"))
    if viewports:
        viewport = viewports[0]
        scale = float(viewport.CustomScale)
        rows.append(
            _check(
                "viewport 1:1 encendido",
                bool(viewport.ViewportOn) and abs(scale - 1.0) < 1e-6,
                f"escala {scale:.4f}",
            )
        )
        rows.append(
            _check(
                "viewport cubre la retícula",
                abs(float(viewport.Width) - 811.0) <= 1.0
                and abs(float(viewport.Height) - 514.0) <= 1.0,
                f"{viewport.Width:.0f} x {viewport.Height:.0f} mm (esperado 811 x 514)",
            )
        )

    references = 0
    frames = 0
    dimensions = 0
    model = doc.ModelSpace
    for index in range(int(model.Count)):
        entity = model.Item(index)
        name = str(entity.ObjectName)
        layer = str(entity.Layer)
        if name == "AcDbBlockReference" and layer == "D-VISTA":
            references += 1
        elif layer == "D-MARCOS":
            frames += 1
        elif name in ("AcDbRotatedDimension", "AcDbAlignedDimension", "AcDbDiametricDimension"):
            dimensions += 1
    rows.append(
        _check(
            "12 referencias",
            references == len(DETAIL_LIBRARY),
            f"{references}/{len(DETAIL_LIBRARY)}",
        )
    )
    rows.append(_check("12 marcos", frames == len(DETAIL_LIBRARY), f"{frames}"))
    rows.append(_check("cotas", dimensions >= 24, f"{dimensions} cotas"))

    layer_names = {str(doc.Layers.Item(i).Name) for i in range(int(doc.Layers.Count))}
    missing_layers = sorted({str(spec["name"]) for spec in DETAIL_LAYERS.values()} - layer_names)
    rows.append(_check("capas D-", not missing_layers, f"faltan {missing_layers or 'ninguna'}"))

    return {
        "checks": rows,
        "checks_passed": sum(1 for row in rows if row["ok"]),
        "checks_total": len(rows),
        "media": media,
        "device": device,
        "paper_size": paper_mm,
    }


def _pdf_page_mm(pdf: Path) -> list[float]:
    """Lee el /MediaBox del PDF y lo devuelve en milimetros."""
    import re

    data = pdf.read_bytes()
    match = re.search(rb"/MediaBox\s*\[\s*([\d.\- ]+)\]", data)
    if match is None:
        return []
    values = [float(part) for part in match.group(1).split()]
    if len(values) != 4:
        return []
    return [round(values[2] / 72.0 * 25.4, 1), round(values[3] / 72.0 * 25.4, 1)]


def _write_report(payload: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    json_path = out_dir / "Biblioteca-Detalles-Metalicos.json"
    md_path = out_dir / "Biblioteca-Detalles-Metalicos.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    checks = payload.get("checks") or []
    lines = [
        "# Biblioteca de detalles metalicos",
        "",
        f"- Lamina: **{payload['layout']}** ({payload['paper_size'][0]:.0f} x "
        f"{payload['paper_size'][1]:.0f} mm)",
        f"- Trazador: {payload['device']} / {payload['media']}",
        f"- Bloques: **{payload['block_count']}**",
        f"- Referencias en la lamina: {payload['references']}",
        f"- Origen de la retícula (mm): {payload['origin']}",
        f"- Fecha: {payload['date']}",
        f"- Verificacion: **{payload['checks_passed']}/{payload['checks_total']} OK**",
        f"- DWG: `{payload['dwg']}`",
    ]
    if payload.get("pdf"):
        lines.append(f"- PDF: `{payload['pdf']}` ({payload.get('pdf_page_mm')} mm)")
    lines += ["", "## Verificacion", "", "| Comprobacion | OK | Detalle |", "|---|---|---|"]
    for row in checks:
        lines.append(f"| {row['check']} | {'si' if row['ok'] else 'no'} | {row['detail']} |")
    lines += [
        "",
        "## Bloques",
        "",
        "| Codigo | Bloque | Detalle | Escala | Entidades |",
        "|---|---|---|---|---|",
    ]
    for block in payload["blocks"]:
        lines.append(
            f"| {block['code']} | `{block['name']}` | {block['title']} | "
            f"{block['scale']} | {block['entities']} |"
        )
    lines += ["", "## Capas de detalle", ""]
    for layer in payload["layers"]:
        lines.append(f"- `{layer}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run(plot: bool = True) -> int:
    service = AutoCADService()
    print("conectando a AutoCAD...", flush=True)
    if not service.connect():
        print("ERROR: no se pudo conectar a AutoCAD", flush=True)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dwg_path = OUT_DIR / DWG_NAME
    _close_previous(service, DWG_NAME)
    if _close_stray_drawings(service):
        print("limpiados dibujos de detalle sin guardar", flush=True)
    if not service.conn.new_document():
        print("ERROR: no se pudo crear un dibujo nuevo", flush=True)
        return 1
    print(f"documento: {service.conn.document_name()}", flush=True)
    # Se guarda con el nombre definitivo de inmediato: asi una corrida fallida no
    # deja un DrawingNN.dwg suelto (el siguiente run lo cierra por nombre).
    _save_as(service.conn.doc, dwg_path)
    print(f"documento guardado: {dwg_path.name}", flush=True)

    service.standards.apply_standard()
    started = time.perf_counter()
    result = service.detail_sheet.create_detail_sheet(layout_name=LAYOUT_NAME)
    elapsed = time.perf_counter() - started

    if not result.get("success"):
        print(f"ERROR al crear la lamina: {result.get('error')}", flush=True)
        return 2

    # Activar la lamina hace que AutoCAD recree su viewport principal: se quita
    # antes de guardar para que el DWG quede con un unico viewport 1:1.
    service.layouts.set_active_layout(LAYOUT_NAME)
    try:
        service.conn.app.ZoomExtents()
    except Exception:  # noqa: BLE001
        pass
    pruned = service.detail_sheet.prune_extra_viewports(LAYOUT_NAME)
    if pruned.get("success"):
        print(f"viewports en la lamina: {pruned['viewports']} (quitados {pruned['removed']})")

    _save_as(service.conn.doc, dwg_path)
    print(f"OK  bloques={result['block_count']}  entidades={result['entities']}  {elapsed:.1f} s")
    print(f"DWG: {dwg_path}")
    for block in result["blocks"]:
        print(
            f"  {block['code']} {block['name']:<24} {block['scale']:<5} "
            f"{block['entities']:>3} ent  {block['size_mm']} mm"
        )

    pdf_path: Path | None = None
    if plot:
        plotted = service.detail_sheet.plot_to_pdf(str(OUT_DIR / PDF_NAME), LAYOUT_NAME)
        if plotted.get("success"):
            pdf_path = Path(str(plotted["pdf"]))
            print(f"PDF: {pdf_path}  ({pdf_path.stat().st_size:,} bytes)")
        else:
            print(f"AVISO: no se pudo trazar el PDF ({plotted.get('error')})", flush=True)

    verification = _verify_sheet(service, result)
    if pdf_path is not None:
        page_mm = _pdf_page_mm(pdf_path)
        ok = len(page_mm) == 2 and abs(page_mm[0] - 841.0) < 5.0 and abs(page_mm[1] - 594.0) < 5.0
        verification["checks"].append(
            _check(
                "PDF A1 apaisado",
                ok,
                f"{page_mm[0]:.0f} x {page_mm[1]:.0f} mm" if len(page_mm) == 2 else str(page_mm),
            )
        )
        verification["checks_passed"] = sum(1 for row in verification["checks"] if row["ok"])
        verification["checks_total"] = len(verification["checks"])

    passed = int(verification["checks_passed"])
    total = int(verification["checks_total"])
    for row in verification["checks"]:
        print(f"  [{'OK ' if row['ok'] else 'FALLA'}] {row['check']:<28} {row['detail']}")
    print(f"VERIFICACION: {passed}/{total}")

    service.layouts.set_active_layout(LAYOUT_NAME)
    try:
        service.conn.app.ZoomExtents()
    except Exception:  # noqa: BLE001
        pass
    # Trazar reactiva la lamina y AutoCAD puede recrear el viewport principal.
    service.detail_sheet.prune_extra_viewports(LAYOUT_NAME)

    payload: dict[str, Any] = {
        "date": date.today().isoformat(),
        "layout": result["layout"],
        "paper_size": result["paper_size"],
        "media": verification["media"],
        "device": verification["device"],
        "grid": result["grid"],
        "cell": result["cell"],
        "origin": result["origin"],
        "block_count": result["block_count"],
        "blocks": result["blocks"],
        "details": result["details"],
        "references": len(result["details"]),
        "entities": result["entities"],
        "viewports": result["viewports"],
        "layers": result["layers"],
        "checks": verification["checks"],
        "checks_passed": passed,
        "checks_total": total,
        "dwg": str(dwg_path),
        "pdf": str(pdf_path) if pdf_path else "",
        "pdf_page_mm": _pdf_page_mm(pdf_path) if pdf_path else [],
    }
    json_path, md_path = _write_report(payload, OUT_DIR)
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")
    return 0 if passed == total else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-pdf", action="store_true", help="no trazar el PDF")
    args = parser.parse_args()
    return run(plot=not args.no_pdf)


if __name__ == "__main__":
    sys.exit(main())
