"""Construye el Golden Gate Bridge en 3D dentro de AutoCAD y guarda el DWG.

Uso:
    python scripts/bridge/build_golden_gate.py            # modelo completo
    python scripts/bridge/build_golden_gate.py --smoke    # puente viga-losa pequeno

Requiere AutoCAD abierto (el script crea un dibujo nuevo). Dimensiones reales:
2737 m de longitud, luz principal 1280 m, vanos laterales 343 m, torres 227 m,
calado 67 m, tablero 27.4 m, cables 0.92 m.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pythoncom
from win32com.client import VARIANT

from autocad_mcp.service import AutoCADService

OUT_DIR = Path(
    os.environ.get("GOLDEN_GATE_OUT", Path.home() / "Documents" / "BlancaNieves" / "salida")
)


def _fmt(value: float) -> str:
    return f"{value:,.2f} m".replace(",", " ")


def _plot_pdf(doc: Any, pdf: Path) -> Path:
    """Traza el modelo a PDF con el comando -PLOT (PlotToFile falla por COM).

    Devuelve el archivo realmente escrito: si el destino esta abierto en un
    visor (Windows lo bloquea), se guarda una copia ``*-3D.pdf``.
    """
    layout = doc.ActiveLayout
    try:
        media = list(layout.GetCanonicalMediaNames())
    except Exception:  # noqa: BLE001
        media = []
    sheet = next(
        (m for m in media if m.startswith("ISO_A0")),
        next((m for m in media if m.startswith("ANSI_E")), None),
    )
    if sheet is None:
        sheet = "ISO_A1_(841.00_x_594.00_MM)"

    doc.SetVariable("FILEDIA", 0)
    doc.SetVariable("CMDDIA", 0)
    doc.SetVariable("BACKGROUNDPLOT", 0)

    if pdf.exists():
        candidates = [
            pdf,
            pdf.with_name(f"{pdf.stem}-3D{pdf.suffix}"),
            pdf.with_name(
                f"{pdf.stem}-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}{pdf.suffix}"
            ),
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    continue
            pdf = candidate
            break

    script = "\n".join(
        [
            "_.-PLOT",
            "_Y",
            "_Model",
            "",
            "DWG To PDF.pc3",
            sheet,
            "_M",
            "_L",
            "_N",
            "_E",
            "_F",
            "_C",
            "_Y",
            "monochrome.ctb",
            "_Y",
            "_N",
            "_N",
            "_N",
            "_Y",
            str(pdf),
            "_N",
            "_Y",
            "",
        ]
    )
    doc.SendCommand(script)
    for _ in range(60):
        if pdf.exists() and pdf.stat().st_size > 0:
            return pdf
        time.sleep(1.0)
    raise RuntimeError(f"el PDF no se genero en {pdf}")


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "ok": bool(ok), "detail": detail}


def _save_as(doc: Any, path: Path, attempts: int = 6) -> None:
    """Guarda el DWG reintentando si AutoCAD esta ocupado."""
    for attempt in range(attempts):
        try:
            doc.SaveAs(str(path))
            return
        except Exception:  # noqa: BLE001 - COM rechaza llamadas mientras esta ocupado
            if attempt == attempts - 1:
                raise
            time.sleep(1.0 * (attempt + 1))


def _verify_golden_gate(service: AutoCADService, result: dict[str, Any]) -> dict[str, Any]:
    """Comprueba cotas, torres, cables y materiales leyendo el modelo real."""
    report = service.solids.get_solid_info(include_entities=True)
    rows = report.get("entities") or []
    towers = [row for row in rows if row.get("layer") == "S-TORRES"]
    cables = [row for row in rows if row.get("layer") == "S-CABLES"]
    suspenders = [
        row
        for row in cables
        if row.get("bbox")
        and row["bbox"][1][0] - row["bbox"][0][0] < 2.0
        and row["bbox"][1][1] - row["bbox"][0][1] < 2.5
        and row["bbox"][1][2] - row["bbox"][0][2] > 2.0
    ]
    tower_top = max((row["bbox"][1][2] for row in towers if row.get("bbox")), default=0.0)
    extents = result.get("extents") or {}
    size = extents.get("size") or [0.0, 0.0, 0.0]
    materials = result.get("materials") or {}
    by_layer = result.get("by_layer") or {}
    plates = int((by_layer.get("S-PLACAS") or {}).get("count") or 0)
    stiffeners = int((by_layer.get("S-RIGIDIZADORES") or {}).get("count") or 0)
    fasteners = int(result.get("fasteners") or 0)

    checks = [
        _check("solidos >= 2000", int(report.get("count") or 0) >= 2000, str(report.get("count"))),
        _check("volumen > 0", float(report.get("total_volume") or 0) > 0, str(report.get("total_volume"))),
        _check(
            "longitud 2737 m",
            abs(float(size[0]) - 2737.0) <= 2.0,
            f"{float(size[0]):.2f} m",
        ),
        _check("ancho 44 m (con fenders)", abs(float(size[1]) - 44.0) <= 5.0, f"{float(size[1]):.2f} m"),
        _check("altura 244.6 m", abs(float(size[2]) - 244.6) <= 5.0, f"{float(size[2]):.2f} m"),
        _check("torres a 227 m", abs(tower_top - 229.6) <= 4.0, f"{tower_top:.2f} m"),
        _check("cables presentes", len(cables) > 400, str(len(cables))),
        _check("suspensores dobles", len(suspenders) >= 400, str(len(suspenders))),
        _check(
            "materiales completos",
            {"hormigon", "acero", "asfalto"}.issubset(materials),
            ", ".join(sorted(materials)),
        ),
        _check("placas de acero", plates >= 300, str(plates)),
        _check("rigidizadores", stiffeners >= 100, str(stiffeners)),
        _check("pernos/rivets", fasteners >= 100, str(fasteners)),
    ]
    return {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "tower_top": round(float(tower_top), 2),
        "suspenders": len(suspenders),
    }


def _write_report(
    out_dir: Path,
    summary: dict[str, Any],
    result: dict[str, Any],
    verification: dict[str, Any] | None,
    elapsed: float,
    plotted: Path | None,
) -> Path:
    """Informe legible en Markdown con dimensiones, materiales y verificacion."""
    spec = result.get("spec") or {}
    material_rows = "\n".join(
        f"| {name} | {data['volume_m3']:,.2f} | {data['mass_t']:,.2f} | "
        f"{data['density_kg_m3']:,.0f} | {', '.join(data['layers'])} |"
        for name, data in (result.get("materials") or {}).items()
    )
    layer_rows = "\n".join(
        f"| {layer} | {int(info['count'])} | {info['volume']:,.2f} |"
        for layer, info in (result.get("by_layer") or {}).items()
    )
    check_rows = (
        "\n".join(
            f"| {item['check']} | {'OK' if item['ok'] else 'FALLO'} | {item['detail']} |"
            for item in (verification or {}).get("checks", [])
        )
        or "| Verificacion | OMITIDA | -- |"
    )
    files = [f"- DWG: `{summary['dwg']}`"]
    if plotted:
        files.append(f"- PDF: `{plotted}` ({plotted.stat().st_size:,} bytes)")
    files.append(f"- JSON: `{out_dir / 'Puente-Golden-Gate.json'}`")

    text = f"""# {result.get('bridge', 'Puente')} - modelo 3D

Generado: {time.strftime('%Y-%m-%d %H:%M:%S')} en {elapsed:.1f} s

## Dimensiones

| Dato | Valor |
|---|---|
| Longitud total | {spec.get('total_length', 0):,.2f} m |
| Luz principal | {spec.get('main_span', 0):,.2f} m |
| Vanos laterales | {spec.get('side_span', 0):,.2f} m |
| Altura de torres | {spec.get('tower_height', 0):,.2f} m |
| Calado | {spec.get('clearance', 0):,.2f} m |
| Ancho de tablero | {spec.get('deck_width', 0):,.2f} m |
| Canto de tablero | {spec.get('deck_depth', 0):,.2f} m |
| Flecha de cable | {spec.get('cable_sag', 0):,.2f} m |
| Diametro de cable | {spec.get('cable_diameter', 0):,.2f} m |
| Detalle metalico | {result.get('detail', 'none')} |
| Pernos/rivets | {result.get('fasteners', 0):,} |

## Resultado

- Solidos: **{result.get('solids', 0)}**
- Volumen modelado: **{result.get('volume', 0):,.2f} m3**
- Masa estimada: **{result.get('mass', 0):,.2f} t**
- Extents: {result.get('extents')}

## Materiales

| Material | Volumen (m3) | Masa (t) | Densidad (kg/m3) | Capas |
|---|---:|---:|---:|---|
{material_rows}

## Capas

| Capa | Solidos | Volumen (m3) |
|---|---:|---:|
{layer_rows}

## Verificacion automatica

| Comprobacion | Estado | Valor |
|---|---|---|
{check_rows}

## Archivos

{chr(10).join(files)}
"""
    path = out_dir / "Puente-Golden-Gate.md"
    path.write_text(text, encoding="utf-8")
    return path


def run(
    smoke: bool = False,
    out_dir: Path | None = None,
    plot: bool = True,
    verify: bool = True,
    detail: str = "bolted",
    max_fasteners: int = 1200,
) -> int:
    service = AutoCADService()
    print("conectando a AutoCAD...", flush=True)
    if not service.connect():
        print("ERROR: no se pudo conectar a AutoCAD", flush=True)
        return 1

    target_dir = Path(out_dir) if out_dir is not None else OUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Reconstruccion idempotente: cierra la version anterior si esta abierta.
    try:
        docs = service.conn.app.Documents
        previous_names = [str(item.Name) for item in docs]
        for name in previous_names:
            if name.lower().startswith("puente-golden-gate"):
                docs.Item(name).Close(False)
                print(f"cerrado dibujo anterior: {name}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: no se pudo cerrar el dibujo anterior ({exc})", flush=True)

    if not service.conn.new_document():
        print("ERROR: no se pudo crear un dibujo nuevo", flush=True)
        return 1
    print(f"documento: {service.conn.document_name()}", flush=True)

    service.standards.apply_standard()
    report = service.info.get_drawing_info()
    print(f"unidades/layers listos: {report.get('entity_count', 0)} entidades", flush=True)

    started = time.perf_counter()
    if smoke:
        result = service.bridges.create_bridge(
            kind="girder",
            name="SMOKE",
            total_length=120.0,
            deck_width=10.0,
            deck_depth=1.2,
            clearance=10.0,
            spans=3,
            detail="members",
        )
    else:
        result = service.bridges.create_bridge(
            preset="golden_gate",
            name="GOLDEN GATE",
            detail=detail,
            max_fasteners=max_fasteners,
        )
    elapsed = time.perf_counter() - started

    if not result.get("success"):
        print(f"ERROR al crear el puente: {result.get('error')}", flush=True)
        return 2

    print(f"OK  solidos={result['solids']}  {elapsed:.1f} s", flush=True)
    print(f"volumen: {_fmt(result['volume'])}  masa: {result.get('mass', 0):,.2f} t", flush=True)
    extents = result.get("extents") or {}
    if extents:
        print(f"extents: {extents['size']}", flush=True)
    for layer, info in (result.get("by_layer") or {}).items():
        print(f"  {layer:<14} n={int(info['count']):>4}  vol={info['volume']:>12,.2f}", flush=True)

    if smoke:
        verification = None
    elif verify:
        verification = _verify_golden_gate(service, result)
        state = "OK" if verification["ok"] else "FALLO"
        print(f"verificacion automatica: {state}", flush=True)
        for item in verification["checks"]:
            print(
                f"  [{'OK' if item['ok'] else 'FALLO'}] {item['check']}: {item['detail']}",
                flush=True,
            )
    else:
        verification = None

    if smoke:
        service.conn.doc.Close(False)
        return 0

    # Rotulos y cuadro de datos reales.
    service.geometry.create_text(
        [-1300, -60, 0], "GOLDEN GATE BRIDGE - MODELO 3D", 26.0, "bylayer"
    )
    service.geometry.create_text(
        [-1300, -95, 0],
        "Luz principal 1280 m - Torres 227 m - Calado 67 m - Longitud 2737 m",
        12.0,
        "bylayer",
    )
    service.tables.create_table(
        [
            ["GOLDEN GATE BRIDGE", "VALOR"],
            ["Longitud total", "2737 m"],
            ["Luz principal", "1280 m"],
            ["Vanos laterales", "343 m"],
            ["Altura de torres", "227 m"],
            ["Calado sobre el agua", "67 m"],
            ["Ancho de tablero", "27.4 m"],
            ["Cables principales", "2 x 0.92 m"],
            ["Suspensores", "15.24 m"],
        ],
        # Bajo el extremo izquierdo: ocupa el hueco que deja el encuadre
        # isometrico para que el trazado quede centrado en el A0.
        [-1360, -250],
        row_height=14.0,
        col_width=170.0,
        title="GOLDEN GATE - DATOS",
        layer="A-TEXTOS",
        text_height=3.5,
    )

    dwg = target_dir / "Puente-Golden-Gate.dwg"
    _save_as(service.conn.doc, dwg)
    print(f"DWG guardado en {dwg}", flush=True)

    # Vista isometrica y encuadre antes de trazar. VPOINT abre un dialogo, asi
    # que se fija la direccion del viewport por COM.
    try:
        doc = service.conn.doc
        viewport = doc.ActiveViewport
        viewport.Direction = VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8, [1.0, -1.0, 0.8]
        )
        doc.ActiveViewport = viewport
        doc.Regen(1)
        service.conn.app.ZoomExtents()
        doc.Save()
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: no se pudo fijar la vista ({exc})", flush=True)

    plotted: Path | None = None
    if plot:
        pdf = target_dir / "Puente-Golden-Gate.pdf"
        try:
            plotted = _plot_pdf(service.conn.doc, pdf)
            print(f"PDF guardado en {plotted}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"aviso: no se pudo trazar el PDF ({exc})", flush=True)

    summary = {
        "bridge": result.get("bridge"),
        "kind": result.get("kind"),
        "solids": result.get("solids"),
        "volume_m3": result.get("volume"),
        "mass_t": result.get("mass"),
        "detail": result.get("detail"),
        "fasteners": result.get("fasteners"),
        "materials": result.get("materials"),
        "extents": result.get("extents"),
        "by_layer": result.get("by_layer"),
        "spec": result.get("spec"),
        "verification": verification,
        "seconds": round(elapsed, 2),
        "dwg": str(dwg),
        "pdf": str(plotted) if plotted else None,
        "report": str(target_dir / "Puente-Golden-Gate.md"),
    }
    (target_dir / "Puente-Golden-Gate.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report_path = _write_report(target_dir, summary, result, verification, elapsed, plotted)
    print(f"informe guardado en {report_path}", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)

    if verification is not None and not verification["ok"]:
        print("ERROR: la verificacion automatica detecto fallos", flush=True)
        return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="prueba rapida viga-losa")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"carpeta de salida (por defecto {OUT_DIR})",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="no trazar el PDF (util si el archivo esta abierto en un visor)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="omitir la verificacion automatica del modelo",
    )
    parser.add_argument(
        "--detail",
        choices=("none", "members", "bolted"),
        default="bolted",
        help="nivel de detalle metalico (por defecto bolted)",
    )
    parser.add_argument(
        "--max-fasteners",
        type=int,
        default=1200,
        help="tope de pernos/rivets con --detail bolted (por defecto 1200)",
    )
    args = parser.parse_args()
    return run(
        smoke=args.smoke,
        out_dir=args.out,
        plot=not args.no_plot,
        verify=not args.no_verify,
        detail=args.detail,
        max_fasteners=args.max_fasteners,
    )


if __name__ == "__main__":
    sys.exit(main())
