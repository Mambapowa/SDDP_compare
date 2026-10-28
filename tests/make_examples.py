"""Génère deux petits cas SDDP fictifs (examples/cas_A et examples/cas_B) pour tester l'outil."""

from __future__ import annotations

import json
import random
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "examples"

SDDP_DAT = """SDDP - Parametros de ejecucion
Tipo de estudio ........................ 1
Ano inicial ............................ 2025
Numero de etapas ....................... {etapas}
Numero de series forward ............... {fwd}
Numero de series backward .............. 20
Tasa de descuento (%) .................. 10.0
Numero maximo de iteraciones ........... {iter}
Tolerancia de convergencia ............. 0.01
"""

CHIDRO_HDR = "!Num Nome........ Ss  PotIn   Vmin     Vmax   FPMed\n"
CTERMI_HDR = "!Num Nome........ Ss  PotIn  GerMin   CEsp  Comb\n"


def hydro(rows):
    return CHIDRO_HDR + "".join(f"{n:4d} {name:<12s} {s:2d} {p:6.1f} {vmin:7.1f} {vmax:8.1f} {fp:6.3f}\n"
                                for n, name, s, p, vmin, vmax, fp in rows)


def thermal(rows):
    return CTERMI_HDR + "".join(f"{n:4d} {name:<12s} {s:2d} {p:6.1f} {gm:7.1f} {ce:6.2f} {c:5d}\n"
                                for n, name, s, p, gm, ce, c in rows)


def demand_csv(scale: float, extra_year: bool) -> str:
    rnd = random.Random(1)
    out = ["Varies per block?,1,Unit,MW,1,2025,1", "Stg,Blk,SYS_NORTE,SYS_SUR"]
    stages = 24 if extra_year else 12
    for st in range(1, stages + 1):
        for blk in (1, 2, 3):
            base = 1000 + 30 * st - 150 * blk + rnd.randint(-5, 5)
            n = base * (scale if 4 <= st <= 6 else 1.0)
            out.append(f"{st},{blk},{n:.1f},{0.6 * base:.1f}")
    return "\n".join(out) + "\n"


def write(case: Path, files: dict[str, str | bytes]) -> None:
    case.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        p = case / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="latin-1")


def main() -> None:
    hydro_a = [(1, "ITAIPU", 1, 1400.0, 2000.0, 29000.0, 0.895), (2, "SALTO", 1, 950.0, 500.0, 5400.0, 0.870),
               (3, "YACYRETA", 2, 3100.0, 1000.0, 21000.0, 0.420)]
    hydro_b = [(1, "ITAIPU", 1, 1400.0, 2000.0, 29000.0, 0.895), (2, "SALTO", 1, 1050.0, 500.0, 5400.0, 0.870),
               (3, "YACYRETA", 2, 3100.0, 1200.0, 21000.0, 0.420), (4, "NOUVELLE_H", 2, 250.0, 10.0, 300.0, 0.910)]
    therm_a = [(1, "TERMO_A", 1, 450.0, 100.0, 2.50, 1), (2, "TERMO_B", 1, 300.0, 0.0, 3.10, 2),
               (3, "CC_SUR", 2, 800.0, 200.0, 1.95, 1)]
    therm_b = [(1, "TERMO_A", 1, 450.0, 100.0, 2.75, 1), (3, "CC_SUR", 2, 800.0, 250.0, 1.95, 1)]
    fuels_a = {"fuels": [{"name": "GAS", "price": 6.5, "unit": "USD/MMBtu"},
                         {"name": "DIESEL", "price": 18.0, "unit": "USD/MMBtu"}],
               "study": {"currency": "USD", "discount_rate": 0.10}}
    fuels_b = json.loads(json.dumps(fuels_a))
    fuels_b["fuels"][0]["price"] = 7.2
    fuels_b["fuels"].append({"name": "HYDROGENE", "price": 25.0, "unit": "USD/MMBtu"})
    bin_a = struct.pack("<100f", *[float(i) for i in range(100)])
    bin_b = struct.pack("<100f", *[float(i) * 1.01 for i in range(100)])

    common = {"dbus.dat": "!Num Nome........ Ss\n   1 BARRA_N       1\n   2 BARRA_S       2\n"}
    write(ROOT / "cas_A", {
        **common,
        "sddp.dat": SDDP_DAT.format(etapas=12, fwd=50, iter=10),
        "chidro.dat": hydro(hydro_a),
        "ctermi.dat": thermal(therm_a),
        "demand.csv": demand_csv(1.0, False),
        "psrclasses.json": json.dumps(fuels_a, indent=2),
        "gndgen.bin": bin_a,
        "mntti.dat": "!Num Etapa Fator\n   2    3   0.50\n",
        "sddp.log": "run A\n",
    })
    write(ROOT / "cas_B", {
        **common,
        "sddp.dat": SDDP_DAT.format(etapas=24, fwd=100, iter=10).replace("10.0", "10.00"),
        "chidro.dat": hydro(hydro_b),
        "ctermi.dat": thermal(therm_b),
        "demand.csv": demand_csv(1.15, True),
        "psrclasses.json": json.dumps(fuels_b, indent=2),
        "gndgen.bin": bin_b,
        "cbatte.dat": "!Num Nome........ Ss  PotIn  Energ\n   1 BAT_SUR       2  100.0  400.0\n",
        "sddp.log": "run B\n",
    })
    print(f"Exemples créés dans {ROOT}")


if __name__ == "__main__":
    main()
