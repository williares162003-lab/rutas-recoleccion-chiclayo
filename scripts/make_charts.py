"""Generate the README charts (SVG) from the saved results. Standard library only."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
GREEN, GREY, INK, MUTED, GRID = "#0b7a63", "#9aa5ad", "#1d2a33", "#5b6770", "#e3e7ea"
FONT = "font-family='Segoe UI, Helvetica, Arial, sans-serif'"


def svg(width, height, body):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
            f"viewBox='0 0 {width} {height}' {FONT}>"
            f"<rect width='100%' height='100%' fill='#ffffff'/>{body}</svg>\n")


def convergence():
    with (ROOT / "resultados" / "convergencia_semilla_42.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    gens = [int(r["generacion"]) for r in rows]
    best = [float(r["mejor_km"]) for r in rows]
    avg = [float(r["promedio_km"]) for r in rows]
    W, H, L, R, T, B = 760, 360, 64, 24, 56, 52
    lo, hi = 280, 320
    x = lambda g: L + (W - L - R) * g / max(gens)
    y = lambda v: T + (H - T - B) * (hi - v) / (hi - lo)
    parts = [f"<text x='{L}' y='26' font-size='16' font-weight='600' fill='{INK}'>"
             f"GA convergence (seed 42)</text>",
             f"<text x='{L}' y='44' font-size='12' fill='{MUTED}'>Route distance (km) per generation</text>"]
    for v in range(lo, hi + 1, 10):
        parts.append(f"<line x1='{L}' x2='{W - R}' y1='{y(v):.1f}' y2='{y(v):.1f}' stroke='{GRID}'/>")
        parts.append(f"<text x='{L - 8}' y='{y(v) + 4:.1f}' font-size='11' fill='{MUTED}' text-anchor='end'>{v}</text>")
    for g in range(0, max(gens) + 1, 25):
        parts.append(f"<text x='{x(g):.1f}' y='{H - B + 18}' font-size='11' fill='{MUTED}' text-anchor='middle'>{g}</text>")
    parts.append(f"<text x='{(L + W - R) / 2}' y='{H - 12}' font-size='11' fill='{MUTED}' text-anchor='middle'>Generation</text>")
    for series, color, width in ((avg, GREY, 1.5), (best, GREEN, 2.5)):
        pts = " ".join(f"{x(g):.1f},{y(v):.1f}" for g, v in zip(gens, series))
        parts.append(f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='{width}'/>")
    parts.append(f"<text x='{x(gens[-1]) - 4:.1f}' y='{y(best[-1]) + 16:.1f}' font-size='11' fill='{GREEN}' "
                 f"text-anchor='end'>Best: {best[-1]:.1f} km</text>")
    parts.append(f"<text x='{x(6):.1f}' y='{y(avg[0]) + 4:.1f}' font-size='11' fill='{MUTED}'>Population average</text>")
    (OUT / "convergence.svg").write_text(svg(W, H, "".join(parts)), encoding="utf-8")


def comparison():
    """30 runs per method as dots; dashed lines mark the baseline and the best-known plan."""
    r = json.loads((ROOT / "resultados" / "experimento_comparativo.json").read_text(encoding="utf-8"))
    runs, res = r["ejecuciones"], r["resumen"]
    base, best = res["vecino_cercano_km"], res["mejor_conocido_km"]
    metodos = [("aleatoria", "Random search"), ("ag", "Plain GA"), ("solo_local", "Local search, 1 start"),
               ("multiarranque", "Multi-start local search"), ("hibrido", "Hybrid GA (GA + local search)")]
    W, L, R, T, row = 760, 196, 96, 84, 46
    H = T + row * len(metodos) + 40
    lo, hi = 279, 303
    x = lambda v: L + (W - L - R) * (v - lo) / (hi - lo)
    parts = [f"<text x='24' y='26' font-size='16' font-weight='600' fill='{INK}'>"
             f"Five methods, 30 seeds each (15 markets)</text>",
             f"<text x='24' y='44' font-size='12' fill='{MUTED}'>Total route distance (km), lower is better. "
             f"Right column: runs that reach the best-known plan.</text>"]
    for v in range(280, hi + 1, 5):
        parts.append(f"<line x1='{x(v):.1f}' x2='{x(v):.1f}' y1='{T - 10}' y2='{H - 34}' stroke='{GRID}'/>")
        parts.append(f"<text x='{x(v):.1f}' y='{H - 18}' font-size='11' fill='{MUTED}' text-anchor='middle'>{v}</text>")
    for v, label, anchor in ((best, f"Best known {best:.1f}", "start"), (base, f"Nearest neighbor {base:.1f}", "middle")):
        parts.append(f"<line x1='{x(v):.1f}' x2='{x(v):.1f}' y1='{T - 10}' y2='{H - 34}' stroke='{INK}' stroke-dasharray='4 3'/>")
        parts.append(f"<text x='{x(v) - (4 if anchor == 'start' else 0):.1f}' y='{T - 16}' font-size='11' fill='{INK}' "
                     f"text-anchor='{anchor}'>{label}</text>")
    for i, (clave, nombre) in enumerate(metodos):
        cy = T + 14 + i * row
        color = GREEN if clave in ("hibrido", "multiarranque") else GREY
        parts.append(f"<text x='{L - 12}' y='{cy + 4}' font-size='12' fill='{INK}' text-anchor='end'>{nombre}</text>")
        for k, e in enumerate(runs):
            jitter = ((k * 7) % 11 - 5) * 1.6
            parts.append(f"<circle cx='{x(e[clave + '_km']):.1f}' cy='{cy + jitter:.1f}' r='3.5' fill='{color}' "
                         f"fill-opacity='0.55'/>")
        hits = res[clave]["alcanza_mejor_conocido"]
        parts.append(f"<text x='{W - R + 16}' y='{cy + 4}' font-size='12' fill='{GREEN if hits == 30 else MUTED}' "
                     f"font-weight='{600 if hits == 30 else 400}'>{hits}/30</text>")
    (OUT / "method_comparison.svg").write_text(svg(W, H, "".join(parts)), encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    convergence()
    comparison()
    print("Charts written to", OUT)
