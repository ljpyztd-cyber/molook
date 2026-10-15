"""Deterministic synthetic biphenyl/ethanol/water scenes, NOT optimized models."""
import copy
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from preview_formats import read_structure, validate_dataset


def scene(torsion, solvent_shift):
    atoms, bonds = [], []

    def atom(element, x, y, z):
        atoms.append((element, x, y, z))
        return len(atoms)

    def bond(a, b, order=1):
        bonds.append((a, b, order))

    rings = []
    for side in (-1, 1):
        angle = math.radians(torsion if side == 1 else -12)
        center = side * (1.397 + .74)
        ids = []
        for i in range(6):
            theta = i * math.pi / 3
            x, y = 1.397 * math.cos(theta), 1.397 * math.sin(theta)
            ids.append(atom("C", center + x, y * math.cos(angle), y * math.sin(angle)))
        for i in range(6):
            bond(ids[i], ids[(i + 1) % 6], 4)
            if i == (0 if side == -1 else 3):
                continue
            theta = i * math.pi / 3
            x, y = 2.477 * math.cos(theta), 2.477 * math.sin(theta)
            hid = atom("H", center + x, y * math.cos(angle), y * math.sin(angle))
            bond(ids[i], hid)
        rings.append(ids)
    bond(rings[0][0], rings[1][3])

    # Hand-placed molecules are for appearance/interaction demonstration only.
    offset = len(atoms)
    ethanol = [("C", -1.3, 3.7, .2), ("C", .18, 3.9, .5), ("O", .9, 2.72, .7),
               ("H", -1.68, 3.3, 1.14), ("H", -1.8, 4.64, -.02), ("H", -1.49, 3.0, -.62),
               ("H", .37, 4.53, 1.37), ("H", .53, 4.4, -.41), ("H", 1.83, 2.92, .84)]
    for e, x, y, z in ethanol:
        atom(e, x, y + solvent_shift, z)
    for a, b in [(1,2),(2,3),(1,4),(1,5),(1,6),(2,7),(2,8),(3,9)]:
        bond(offset + a, offset + b)
    oxygen = atom("O", -.3, -3.65 - solvent_shift, .8)
    h1 = atom("H", .46, -3.08 - solvent_shift, .8)
    h2 = atom("H", -.02, -4.56 - solvent_shift, .8)
    bond(oxygen, h1)
    bond(oxygen, h2)
    return atoms, bonds


def sdf_record(atoms, bonds, title):
    lines = [title, "  StructureViewer synthetic", "Illustrative coordinates only; no optimization",
             f"{len(atoms):3d}{len(bonds):3d}  0  0  0  0            999 V2000"]
    lines += [f"{x:10.4f}{y:10.4f}{z:10.4f} {e:<3s} 0  0  0  0  0  0  0  0  0  0  0  0" for e, x, y, z in atoms]
    lines += [f"{a:3d}{b:3d}{order:3d}  0  0  0  0" for a, b, order in bonds]
    return "\n".join(lines + ["M  END", "$$$$", ""])


def main():
    output = Path(__file__).resolve().parent
    models = []
    for key, title, color, angles in [("a", "示例 A · 青绿", "#338f83", (30,60)),
                                       ("b", "示例 B · 蓝灰", "#477eaa", (-42,-70))]:
        path = output / f"demo-{key}.sdf"
        text = "".join(sdf_record(*scene(angle, i * .18), f"Synthetic scene {key.upper()} / frame {i+1}") for i, angle in enumerate(angles))
        path.write_text(text, encoding="utf-8", newline="\n")
        frames = read_structure(path)
        for i, frame in enumerate(frames):
            frame["status"] = "illustrative"
            frame["title"] = f"演示帧 {i+1} · 合成坐标"
            frame["warnings"] = ["纯样式演示：坐标由脚本合成，未优化，不代表科学结果。"]
        models.append(dict(id=f"demo-{key}", title=title, frames=frames,
                           fragments={"fragment-1":{"title":"联苯","color":color},
                                      "fragment-2":{"title":"乙醇","color":"#c28a50"},
                                      "fragment-3":{"title":"水","color":"#9b6bb3"}},
                           presets=[{"id":"host","title":"仅联苯","fragments":["fragment-1"],"note":"显示筛选；源数据不变"},
                                    {"id":"guests","title":"仅乙醇与水","fragments":["fragment-2","fragment-3"],"note":"合成位置，非溶剂化结果"}]))
    data = validate_dataset(dict(schema="structure-viewer/1", title="Structure Viewer · 结构之美",
                                 description="白底 · 青灰 · 片段着色 | 拖动比较，按需测量，高清导出。以下均为合成示意坐标，未经优化。", models=models))
    (output / "demo.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("Synthetic examples regenerated: 2 models, 4 frames, 34 atoms per frame")


if __name__ == "__main__":
    main()
