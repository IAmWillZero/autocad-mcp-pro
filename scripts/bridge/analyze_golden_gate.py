"""Analiza el Golden Gate como modelo de barras 2D y exporta el archivo FTOOL.

No necesita AutoCAD: resuelve el modelo con el solver interno (rigidez directa,
P-Delta y traccion-solo) y escribe en ``salida`` el ``.ftl`` listo para abrir en
FTOOL, un JSON con todos los resultados y un informe Markdown.

Uso:
    python scripts/bridge/analyze_golden_gate.py
    python scripts/bridge/analyze_golden_gate.py --load 2000 --x 320
    python scripts/bridge/analyze_golden_gate.py --sweep 0 320 640 960
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from autocad_mcp.features.ftool import (
    FTOOL_FORMAT,
    FTOOL_MANUAL,
    FrameModel,
    _set_point_load,
    analyze_point_load,
    build_suspension_model,
    model_to_ftl,
    verify_ftl,
)

OUT_DIR = Path(
    os.environ.get("GOLDEN_GATE_OUT", Path.home() / "Documents" / "BlancaNieves" / "salida")
)


def _num(value: float, digits: int = 2) -> str:
    """Numero con separador de miles y sin ``-0.00``."""
    if abs(value) < 0.5 * 10.0**-digits:
        value = 0.0
    return f"{value:,.{digits}f}".replace(",", " ")


def _case_row(x: float, analysis: dict[str, Any]) -> str:
    live = analysis["point_load"]
    return (
        f"| {_num(x, 0)} | {_num(live['max_deck_deflection'], 3)} | "
        f"{_num(abs(live['load']['deflection_at_load']), 3)} | "
        f"{_num(live['cable_tension_max'], 0)} | "
        f"{_num(live['hanger_tension_max'], 1)} | "
        f"{live['slack_hangers']} |"
    )


def _reaction_rows(analysis: dict[str, Any]) -> str:
    dead = analysis["dead_load"]["reactions"]
    live = analysis["point_load"]["reactions"]
    combined = analysis["combined"]["reactions"]
    rows = []
    for tag in sorted(dead):
        rows.append(
            f"| {tag} | {_num(dead[tag]['fy'], 0)} | {_num(live.get(tag, {}).get('fy', 0.0), 0)} | "
            f"{_num(combined.get(tag, {}).get('fy', 0.0), 0)} | "
            f"{int(dead[tag]['count'])} |"
        )
    return "\n".join(rows)


def _write_report(
    path: Path,
    model: FrameModel,
    analysis: dict[str, Any],
    cases: list[tuple[float, dict[str, Any]]],
    ftl: dict[str, Any],
    elapsed: float,
) -> Path:
    info = analysis["model"]
    meta = info["meta"]
    dead = analysis["dead_load"]
    live = analysis["point_load"]
    combined = analysis["combined"]
    equilibrium = live["equilibrium"]
    case_rows = "\n".join(_case_row(x, item) for x, item in cases)

    text = f"""# Golden Gate - analisis estructural 2D

Generado: {time.strftime('%Y-%m-%d %H:%M:%S')} en {elapsed:.1f} s

Modelo de barras en el plano longitudinal X-Y (unidades kN y m, carga vertical
positiva hacia abajo). No requiere AutoCAD; el ``.ftl`` se abre en FTOOL.

## Modelo

| Dato | Valor |
|---|---|
| Nudos | {info['nodes']} |
| Barras | {info['members']} |
| Cables | {info['members_by_group'].get('cable', 0)} |
| Suspensores | {info['members_by_group'].get('hanger', 0)} |
| Tablero | {info['members_by_group'].get('deck', 0)} |
| Torres | {info['members_by_group'].get('tower', 0)} |
| Material | {info['material']} (E = 2.0e8 kN/m2, rho = 78.5 kN/m3) |
| Secciones | {', '.join(info['sections'])} |
| Luz principal | {_num(meta.get('main_span', 0), 0)} m |
| Vanos laterales | {_num(meta.get('side_span', 0), 0)} m |
| Altura de torres | {_num(meta.get('tower_y', 0), 0)} m |
| Calado del tablero | {_num(meta.get('deck_y', 0), 0)} m |
| Flecha del cable | {_num(meta.get('sag', 0), 0)} m |
| Flecha del vano lateral | {_num(meta.get('side_sag', 0), 3)} m |
| Separacion de suspensores | {_num(meta.get('hanger_spacing', 0), 3)} m |
| Anclajes | x = +/-{_num(meta.get('pier_x', 0), 0)} m, al nivel del tablero y {_num(meta.get('anchor_offset', 0) * 1000, 0)} mm fuera del apoyo |
| Aproximaciones | {meta.get('approach_piers', 0)} pilas cada {_num(meta.get('approach_spacing', 0), 1)} m hasta los estribos |

## Estado de peso propio (referencia)

| Magnitud | Valor |
|---|---:|
| Flecha maxima del tablero | {_num(dead['max_deck_deflection'], 3)} m |
| Axil maximo de cable | {_num(dead['cable_tension_max'], 0)} kN |
| Axil minimo de cable | {_num(dead['cable_tension_min'], 0)} kN |
| Axil maximo de suspensor | {_num(dead['hanger_tension_max'], 0)} kN |
| Suspensores destensados | {dead['slack_hangers']} de {dead['hangers']} |
| Deriva maxima de torre | {_num(dead['tower_drift_max'], 4)} m |
| Momento en base de torre | {_num(dead['tower_base_moment_max'], 0)} kN*m |
| Error relativo de equilibrio (fy) | {dead['equilibrium']['relative_error_fy']:.2e} |
| Error relativo de equilibrio (mz) | {dead['equilibrium']['relative_error_mz']:.2e} |

El peso propio se resuelve como estado de referencia: los axiles iniciales de
cables y suspensores entran como cargas nodales equivalentes, de modo que la
solucion es el incremento respecto de ese estado.

## Carga puntual en el centro del vano principal

Carga aplicada: **{_num(live['load']['magnitude'], 0)} kN** en x = {_num(live['load']['x'], 2)} m
(nudo {live['load']['node']}).

| Magnitud | Incremento | Total (peso propio + carga) |
|---|---:|---:|
| Flecha maxima del tablero | {_num(live['max_deck_deflection'], 3)} m | {_num(dead['max_deck_deflection'] + live['max_deck_deflection'], 3)} m |
| Axil maximo de cable | {_num(live['cable_tension_max'], 0)} kN | {_num(combined['cable_tension_max'], 0)} kN |
| Axil maximo de suspensor | {_num(live['hanger_tension_max'], 0)} kN | {_num(combined['hanger_tension_max'], 0)} kN |
| Momento maximo positivo del tablero | {_num(live['deck_moment_max_sagging'], 0)} kN*m | {_num(combined['deck_moment_max_sagging'], 0)} kN*m |
| Momento maximo negativo del tablero | {_num(live['deck_moment_max_hogging'], 0)} kN*m | {_num(combined['deck_moment_max_hogging'], 0)} kN*m |
| Deriva de torre | {_num(live['tower_drift_max'], 4)} m | - |
| Suspensores destensados | {live['slack_hangers']} | - |

Equilibrio global del caso puntual: reaccion vertical total
**{_num(live['equilibrium']['reactions'][1], 0)} kN** frente a
**{_num(-live['equilibrium']['applied'][1], 0)} kN** aplicados; error relativo
fy = {equilibrium['relative_error_fy']:.2e}, mz = {equilibrium['relative_error_mz']:.2e}.

## Reacciones verticales por apoyo (kN)

| Apoyo | Peso propio | Carga puntual | Total | Nudos |
|---|---:|---:|---:|---:|
{_reaction_rows(analysis)}

## Influencia de la posicion de la carga

| x (m) | Flecha max. (m) | Flecha bajo la carga (m) | dN cable max. (kN) | dN suspensor max. (kN) | Destensados |
|---:|---:|---:|---:|---:|---:|
{case_rows}

La respuesta no es simetrica respecto del centro del vano principal porque la
carga se aplica sobre un nudo del tablero y los suspensores transmiten el axil
por la cadena de cables hasta los anclajes y las torres. En ``x = 640 m`` la
carga coincide con el apoyo de la torre, que descarga directamente a la base:
por eso la flecha del tablero y el incremento de axil en el cable son nulos. El
valor maximo de flecha se alcanza entre el centro y los cuartos del vano.

## Exportacion a FTOOL

- Archivo: `{ftl['path']}`
- Formato: FTL 4.01
- Ida y vuelta verificada: {'OK' if ftl['verified']['ok'] else 'FALLO'}
- Nudos/barras reimportados: {ftl['verified']['nodes']} / {ftl['verified']['members']}
- Lineas: {ftl['lines']}

FTOOL no guarda resultados en el ``.ftl``: hay que abrirlo y ejecutar ``Solve``.
La edicion estandar admite un solo caso de carga, por eso el archivo se exporta
con la carga puntual incluida (o solo peso propio si ``load_kN = 0``).

Limitaciones conocidas:

- FTOOL resuelve elasticidad lineal sin rigidez geometrica: las flechas diferiran
  de las del solver interno, que si incluye P-Delta y traccion-solo.
- Los cables y suspensores se exportan como barras articuladas (``truss``); las
  torres y el tablero, como porticos.
- La comparacion de reacciones entre ambos programas debe hacerse con el mismo
  caso de carga.

Referencias: {FTOOL_FORMAT} - {FTOOL_MANUAL}

## Archivos

- FTL: `{ftl['path']}`
- JSON: `{path.with_suffix('.json')}`
- Informe: `{path}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run(
    out_dir: Path,
    *,
    preset: str = "golden_gate",
    magnitude: float = 1000.0,
    x: float = 0.0,
    sweep: list[float] | None = None,
    geometric: bool = True,
    tension_only: bool = True,
) -> int:
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)

    model = build_suspension_model(preset)
    print(
        f"modelo: {len(model.nodes)} nudos, {len(model.members)} barras "
        f"(preset {preset})",
        flush=True,
    )

    analysis = analyze_point_load(
        model,
        x=x,
        magnitude=magnitude,
        geometric=geometric,
        tension_only=tension_only,
    )
    dead = analysis["dead_load"]
    live = analysis["point_load"]
    print(
        f"peso propio: flecha {dead['max_deck_deflection']:.3f} m, "
        f"cable max {dead['cable_tension_max']:,.0f} kN",
        flush=True,
    )
    print(
        f"carga {magnitude:,.0f} kN en x={live['load']['x']:.2f}: "
        f"flecha {live['max_deck_deflection']:.3f} m, "
        f"dN cable {live['cable_tension_max']:,.0f} kN, "
        f"dN suspensor {live['hanger_tension_max']:,.0f} kN",
        flush=True,
    )
    print(
        f"equilibrio: fy error {live['equilibrium']['relative_error_fy']:.2e}, "
        f"mz error {live['equilibrium']['relative_error_mz']:.2e}",
        flush=True,
    )

    positions = sweep or [0.0]
    cases: list[tuple[float, dict[str, Any]]] = []
    for position in positions:
        item = (
            analysis
            if abs(position - x) < 1e-9
            else analyze_point_load(
                model,
                x=position,
                magnitude=magnitude,
                geometric=geometric,
                tension_only=tension_only,
            )
        )
        cases.append((position, item))
        if abs(position - x) >= 1e-9:
            live_item = item["point_load"]
            print(
                f"  x={position:>7.0f} m: flecha {live_item['max_deck_deflection']:.3f} m, "
                f"dN cable {live_item['cable_tension_max']:,.0f} kN",
                flush=True,
            )

    # El .ftl lleva el caso de carga puntual para poder verlo directamente.
    ftl_model = build_suspension_model(preset)
    _set_point_load(ftl_model, x, magnitude)
    ftl_path = out_dir / "Golden-Gate-modelo-2D.ftl"
    ftl_path.write_text(model_to_ftl(ftl_model), encoding="utf-8", newline="\n")
    verification = verify_ftl(ftl_model)
    print(f"FTL: {ftl_path} ({ftl_path.stat().st_size:,} bytes) verificacion {verification['ok']}", flush=True)

    elapsed = time.perf_counter() - started
    report_path = out_dir / "Golden-Gate-Analisis.md"
    payload = {
        "preset": preset,
        "seconds": round(elapsed, 2),
        "solver": analysis["solver"],
        "model": analysis["model"],
        "dead_load": dead,
        "point_load": live,
        "combined": analysis["combined"],
        "influence": [
            {
                "x": case_x,
                "max_deck_deflection": item["point_load"]["max_deck_deflection"],
                "cable_tension_max": item["point_load"]["cable_tension_max"],
                "hanger_tension_max": item["point_load"]["hanger_tension_max"],
                "slack_hangers": item["point_load"]["slack_hangers"],
            }
            for case_x, item in cases
        ],
        "ftl": {
            "path": str(ftl_path),
            "bytes": ftl_path.stat().st_size,
            "lines": len(ftl_path.read_text(encoding="utf-8").splitlines()),
            "verified": verification,
            "format": FTOOL_FORMAT,
            "manual": FTOOL_MANUAL,
        },
        "report": str(report_path),
    }
    (out_dir / "Golden-Gate-Analisis.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_report(report_path, model, analysis, cases, payload["ftl"], elapsed)
    print(f"JSON: {out_dir / 'Golden-Gate-Analisis.json'}", flush=True)
    print(f"informe: {report_path}", flush=True)

    return 0 if verification["ok"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help=f"carpeta (por defecto {OUT_DIR})")
    parser.add_argument("--preset", default="golden_gate")
    parser.add_argument("--load", type=float, default=1000.0, help="carga puntual en kN")
    parser.add_argument("--x", type=float, default=0.0, help="posicion de la carga en m")
    parser.add_argument(
        "--sweep",
        type=float,
        nargs="*",
        default=None,
        help="posiciones adicionales para el barrido de influencia",
    )
    parser.add_argument("--no-geometric", action="store_true", help="sin rigidez geometrica")
    parser.add_argument("--no-tension-only", action="store_true", help="sin traccion-solo")
    args = parser.parse_args()

    return run(
        Path(args.out) if args.out else OUT_DIR,
        preset=args.preset,
        magnitude=args.load,
        x=args.x,
        sweep=args.sweep,
        geometric=not args.no_geometric,
        tension_only=not args.no_tension_only,
    )


if __name__ == "__main__":
    sys.exit(main())
