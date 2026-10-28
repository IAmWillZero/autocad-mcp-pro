"""Genera la biblioteca de detalles metalicos y su lamina A1 en un DWG nuevo.

Uso:
    python scripts/bridge/build_detail_sheet.py
    python scripts/bridge/build_detail_sheet.py --no-pdf

Requiere AutoCAD abierto. Crea un dibujo nuevo (no toca los dibujos abiertos),
define los 12 bloques de detalle, compone la lamina DETALLES-ACERO, guarda el
DWG y traza un PDF A1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from autocad_mcp.service import AutoCADService

OUT_DIR = Path(
    os.environ.get("DETAIL_SHEET_OUT", Path.home() / "Documents" / "BlancaNieves" / "salida")
)
DWG_NAME = "Biblioteca-Detalles-Metalicos.dwg"
PDF_NAME = "Biblioteca-Detalles-Metalicos.pdf"
LAYOUT_NAME = "DETALLES-ACERO"


def _plot_layout(doc: Any, layout_name: str, media: str, pdf: Path) -> Path:
    """Traza un layout a PDF con -PLOT y devuelve el archivo escrito."""
    doc.SetVariable("FILEDIA", 0)
    doc.SetVariable("CMDDIA", 0)
    doc.SetVariable("BACKGROUNDPLOT", 0)

    target = pdf
    if target.exists():
        for candidate in (target, target.with_name(f"{target.stem}-1{target.suffix}")):
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    continue
            target = candidate
            break

    script = "\n".join(
        [
            "_.-PLOT",
            "_Y",
            layout_name,
            "DWG To PDF.pc3",
            media,
            "_M",
            "_L",
            "_N",
            "",
            "",
            "_C",
            "_Y",
            "monochrome.ctb",
            "_Y",
            "_N",
            "_N",
            "_N",
            "_Y",
            str(target),
            "_N",
            "_Y",
            "",
        ]
    )
    doc.SendCommand(script)
    for _ in range(60):
        if target.exists() and target.stat().st_size > 0:
            return target
        time.sleep(1.0)
    raise RuntimeError(f"el PDF no se genero en {target}")


def _save_as(doc: Any, path: Path, attempts: int = 6) -> None:
    for attempt in range(attempts):
        try:
            doc.SaveAs(str(path))
            return
        except Exception:  # noqa: BLE001 - COM rechaza llamadas mientras esta ocupado
            if attempt == attempts - 1:
                raise
            time.sleep(1.0 * (attempt + 1))


def _write_report(payload: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    json_path = out_dir / "Biblioteca-Detalles-Metalicos.json"
    md_path = out_dir / "Biblioteca-Detalles-Metalicos.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Biblioteca de detalles metalicos",
        "",
        f"- Lamina: **{payload['layout']}** ({payload['paper_size'][0]:.0f} x "
        f"{payload['paper_size'][1]:.0f} mm)",
        f"- Bloques: **{payload['block_count']}**",
        f"- Origen de la retícula (mm): {payload['origin']}",
        f"- Fecha: {payload['date']}",
        f"- DWG: `{payload['dwg']}`",
    ]
    if payload.get("pdf"):
        lines.append(f"- PDF: `{payload['pdf']}`")
    lines += ["", "## Bloques", "", "| Codigo | Bloque | Detalle | Escala | Entidades |", "|---|---|---|---|---|"]
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
    if not service.conn.new_document():
        print("ERROR: no se pudo crear un dibujo nuevo", flush=True)
        return 1
    print(f"documento: {service.conn.document_name()}", flush=True)

    service.standards.apply_standard()
    started = time.perf_counter()
    result = service.detail_sheet.create_detail_sheet(layout_name=LAYOUT_NAME)
    elapsed = time.perf_counter() - started

    if not result.get("success"):
        print(f"ERROR al crear la lamina: {result.get('error')}", flush=True)
        return 2

    dwg_path = OUT_DIR / DWG_NAME
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
        try:
            service.layouts.set_active_layout(LAYOUT_NAME)
            media = service.detail_sheet._pick_media(service.conn.doc.ActiveLayout)
            pdf_path = _plot_layout(service.conn.doc, LAYOUT_NAME, media, OUT_DIR / PDF_NAME)
            print(f"PDF: {pdf_path}")
        except Exception as exc:  # noqa: BLE001 - el DWG ya esta guardado
            print(f"AVISO: no se pudo trazar el PDF ({exc})", flush=True)

    service.layouts.set_active_layout(LAYOUT_NAME)
    try:
        service.conn.app.ZoomExtents()
    except Exception:  # noqa: BLE001
        pass

    payload: dict[str, Any] = {
        "date": date.today().isoformat(),
        "layout": result["layout"],
        "paper_size": result["paper_size"],
        "origin": result["origin"],
        "grid": result["grid"],
        "cell": result["cell"],
        "block_count": result["block_count"],
        "blocks": result["blocks"],
        "details": result["details"],
        "entities": result["entities"],
        "layers": result["layers"],
        "dwg": str(dwg_path),
        "pdf": str(pdf_path) if pdf_path else "",
    }
    json_path, md_path = _write_report(payload, OUT_DIR)
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-pdf", action="store_true", help="no trazar el PDF")
    args = parser.parse_args()
    return run(plot=not args.no_pdf)


if __name__ == "__main__":
    sys.exit(main())
