"""Strict, dependency-free structure readers for Molook. No bond perception.

Coordinates are Cartesian angstroms; identifiers are source row/serial identifiers.
Unsupported or ambiguous format features fail rather than silently changing identity.
"""
import hashlib
import json
import math
import re
import shlex
from pathlib import Path

VERSION = "1.1.1"
ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split())
STATUSES = {"initial", "illustrative", "running", "accepted", "unverified"}
MAX_ATOMS = 50000
MAX_TOTAL = 250000


def number(s):
    n = float(re.sub(r"\(\d+\)$", "", str(s)).replace("D", "E").replace("d", "e"))
    if not math.isfinite(n):
        raise ValueError("Non-finite coordinate or cell value")
    return n


def atom(i, e, xyz, fragment="structure", **extra):
    if e not in ELEMENTS:
        raise ValueError(f"Unknown element {e!r}; supply an explicit element mapping")
    return dict(id=str(i), element=e, position=[number(x) for x in xyz], fragment=str(fragment), **extra)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def coordinate_hash(atoms):
    # JSON/JavaScript round trips turn 1.0 into 1; numeric identity is unchanged.
    return digest([[a["id"], a["element"], [float(x) for x in a["position"]]] for a in atoms])


def cell_from_lengths(vals):
    a, b, c, alpha, beta, gamma = map(number, vals)
    if min(a, b, c) <= 0 or not all(0 < x < 180 for x in (alpha, beta, gamma)):
        raise ValueError("Invalid cell lengths or angles")
    al, be, ga = map(math.radians, (alpha, beta, gamma))
    cx, cy = c * math.cos(be), c * (math.cos(al) - math.cos(be) * math.cos(ga)) / math.sin(ga)
    z2 = c*c - cx*cx - cy*cy
    if z2 <= 0:
        raise ValueError("Degenerate cell")
    return [[a, 0., 0.], [b*math.cos(ga), b*math.sin(ga), 0.], [cx, cy, math.sqrt(z2)]]


def xyz(text):
    lines, frames, p = text.splitlines(), [], 0
    while p < len(lines):
        if not lines[p].strip():
            p += 1
            continue
        n = int(lines[p].strip())
        if not 0 < n <= MAX_ATOMS or p+n+2 > len(lines):
            raise ValueError("XYZ count/truncation error or >50000 atoms")
        comment = lines[p+1]
        if "Properties=" in comment and not re.search(r"Properties=(?:\"|')?species:S:1:pos:R:3(?:\s|[\"']|$)", comment):
            raise ValueError("Extended XYZ supports only species:S:1:pos:R:3; convert other columns explicitly")
        atoms = []
        for i, line in enumerate(lines[p+2:p+2+n], 1):
            tok = line.split()
            if len(tok) != 4:
                raise ValueError("XYZ requires exactly element x y z per row")
            atoms.append(atom(i, tok[0], tok[1:4]))
        f = dict(title=comment or f"Frame {len(frames)+1}", atoms=atoms, bonds=[], bond_mode="absent", warnings=["XYZ contains no explicit bonds. No covalent bonds inferred; Cartesian coordinates assumed in Å."])
        lattice = re.search(r'Lattice="([^"]+)"', comment)
        if lattice:
            nums = list(map(number, lattice[1].split()))
            if len(nums) != 9:
                raise ValueError("XYZ Lattice requires nine numbers")
            periodic = re.search(r'pbc="([^"]+)"', comment)
            pbc = periodic[1].split() if periodic else ["T"]*3
            if len(pbc) != 3 or any(x.upper() not in {"T", "F", "TRUE", "FALSE"} for x in pbc):
                raise ValueError("Invalid XYZ pbc field")
            f["cell"] = dict(vectors=[nums[i:i+3] for i in (0, 3, 6)], periodic=[x.upper() in {"T", "TRUE"} for x in pbc])
        frames.append(f)
        p += n+2
    return frames


def sdf(text):
    frames = []
    for rec in text.split("$$$$"):
        if not rec.strip():
            continue
        if frames:
            rec = rec.lstrip("\r\n")
        lines = rec.splitlines()
        if len(lines) < 4 or "V2000" not in lines[3]:
            raise ValueError("Only SDF/MOL V2000 supported (not V3000/query molecules)")
        n, nb = int(lines[3][:3]), int(lines[3][3:6])
        if not 0 < n <= MAX_ATOMS or len(lines) < 4+n+nb or "M  END" not in lines:
            raise ValueError("Invalid SDF counts or missing M END")
        atoms = [atom(i+1, ln[31:34].strip(), [ln[:10], ln[10:20], ln[20:30]]) for i, ln in enumerate(lines[4:4+n])]
        bonds = []
        for ln in lines[4+n:4+n+nb]:
            i, j, order = int(ln[:3]), int(ln[3:6]), int(ln[6:9])
            if order not in (1, 2, 3, 4):
                raise ValueError("SDF query/unspecified bonds unsupported")
            bonds.append(dict(a=str(i), b=str(j), order=1.5 if order == 4 else order))
        # Components determined solely by explicit connectivity.
        adjacency = {a["id"]: [] for a in atoms}
        for b in bonds:
            if b["a"] not in adjacency or b["b"] not in adjacency:
                raise ValueError("SDF bond references missing atom")
            adjacency[b["a"]].append(b["b"]); adjacency[b["b"]].append(b["a"])
        groups, group = {}, 0
        for a in atoms:
            if a["id"] in groups:
                continue
            group += 1
            stack = [a["id"]]
            while stack:
                key = stack.pop()
                if key not in groups:
                    groups[key] = f"fragment-{group}"
                    stack.extend(adjacency[key])
        for a in atoms:
            a["fragment"] = groups[a["id"]]
        frames.append(dict(title=lines[0] or "SDF structure", atoms=atoms, bonds=bonds, bond_mode="explicit", warnings=["SDF bond order retained; aromatic bonds drawn as 1.5. Formal charges/stereochemistry remain in source; no chemical validation performed."]))
    return frames


def pdb(text):
    frames, atoms, connections, cell = [], [], [], None
    seen_models = 0
    for ln in text.splitlines():
        tag = ln[:6].strip()
        if tag == "MODEL":
            seen_models += 1
            if atoms:
                raise ValueError("Malformed PDB MODEL boundaries")
        elif tag in {"ATOM", "HETATM"}:
            if ln[16:17].strip():
                raise ValueError("PDB alternate locations require explicit upstream selection")
            if ln[54:60].strip() and number(ln[54:60]) != 1:
                raise ValueError("PDB partial occupancy unsupported; select a concrete configuration")
            e = ln[76:78].strip()
            atoms.append(atom(ln[6:11].strip(), e, [ln[30:38], ln[38:46], ln[46:54]], f"{ln[21:22].strip() or '_'}:{ln[22:27].strip()}:{ln[17:20].strip()}", label=ln[12:16].strip()))
        elif tag == "ENDMDL":
            frames.append(dict(atoms=atoms)); atoms = []
        elif tag == "CONECT":
            ids = [ln[i:i+5].strip() for i in range(6, len(ln), 5) if ln[i:i+5].strip()]
            for j in ids[1:]:
                if ids[0] != j:
                    connections.append(tuple(sorted((ids[0], j))))
        elif tag == "CRYST1":
            cell = dict(vectors=cell_from_lengths([ln[6:15], ln[15:24], ln[24:33], ln[33:40], ln[40:47], ln[47:54]]), periodic=[True]*3)
    if atoms:
        frames.append(dict(atoms=atoms))
    for i, f in enumerate(frames):
        f.update(title=f"PDB model {i+1}", bonds=[dict(a=a, b=b, order=1) for a,b in sorted(set(connections))], bond_mode="explicit-partial" if connections else "absent", warnings=["Only listed CONECT connections shown, order unknown (drawn single). No automatic protein/residue bonds; no crystallographic symmetry expansion."])
        if cell:
            f["cell"] = cell
    return frames


def cif(text):
    if re.search(r"(?m)^;", text):
        raise ValueError("CIF semicolon multiline values unsupported; provide a simple P1 structure")
    tokens = shlex.split(text, comments=True, posix=True)
    data, loops, blocks, p = {}, [], 0, 0
    while p < len(tokens):
        t = tokens[p]
        if t.lower().startswith("data_"):
            blocks += 1; p += 1
        elif t.lower() == "loop_":
            p += 1; tags, rows = [], []
            while p < len(tokens) and tokens[p].startswith("_"):
                tags.append(tokens[p].lower()); p += 1
            while p < len(tokens) and not tokens[p].startswith("_") and tokens[p].lower() != "loop_" and not tokens[p].lower().startswith("data_"):
                rows.append(tokens[p]); p += 1
            if not tags or len(rows) % len(tags):
                raise ValueError("Malformed CIF loop")
            loops.append([dict(zip(tags, rows[i:i+len(tags)])) for i in range(0, len(rows), len(tags))])
        elif t.startswith("_") and p+1 < len(tokens):
            data[t.lower()] = tokens[p+1]; p += 2
        else:
            raise ValueError(f"Unsupported CIF token {t}")
    if blocks != 1:
        raise ValueError("CIF must contain one data block")
    group = data.get("_space_group_it_number", data.get("_symmetry_int_tables_number"))
    hm = data.get("_space_group_name_h-m_alt", data.get("_symmetry_space_group_name_h-m"))
    ops = [v for rows in loops for row in rows for k,v in row.items() if k in {"_space_group_symop_operation_xyz", "_symmetry_equiv_pos_as_xyz"}]
    ops += [v for k,v in data.items() if k in {"_space_group_symop_operation_xyz", "_symmetry_equiv_pos_as_xyz"}]
    if (group and group != "1") or (hm and hm.replace(" ", "").upper() != "P1") or any(op.replace(" ", "").lower() != "x,y,z" for op in ops) or not (group or hm or ops):
        raise ValueError("Only explicit P1 CIF supported. Expand symmetry upstream; this preview does not generate equivalent atoms.")
    vectors = cell_from_lengths([data[f"_cell_{name}"] for name in ("length_a", "length_b", "length_c", "angle_alpha", "angle_beta", "angle_gamma")])
    atom_loops = [rows for rows in loops if rows and "_atom_site_type_symbol" in rows[0]]
    if len(atom_loops) != 1:
        raise ValueError("CIF requires one atom loop with explicit type_symbol")
    atoms = []
    for i, row in enumerate(atom_loops[0], 1):
        if number(row.get("_atom_site_occupancy", 1)) != 1 or row.get("_atom_site_disorder_group", ".") not in {".", "?", "0"}:
            raise ValueError("CIF disorder/partial occupancy requires explicit selection upstream")
        frac = [row.get(f"_atom_site_fract_{k}") for k in "xyz"]
        if all(v is not None for v in frac):
            xyzv = [sum(number(frac[j])*vectors[j][k] for j in range(3)) for k in range(3)]
        else:
            xyzv = [row[f"_atom_site_cartn_{k}"] for k in "xyz"]
        atoms.append(atom(row.get("_atom_site_label", str(i)), row["_atom_site_type_symbol"], xyzv))
    return [dict(title="P1 cell (listed atoms only)", atoms=atoms, bonds=[], bond_mode="absent", cell=dict(vectors=vectors, periodic=[True]*3), warnings=["P1 listed atoms only. Fractional-to-Cartesian conversion uses declared cell. No symmetry expansion, wrapping or inferred bonds. CIF geometry tables are not interpreted as bonds."])]


def read_structure(path):
    path = Path(path).resolve()
    if path.stat().st_size > 64*1024*1024:
        raise ValueError("Input file >64 MiB; select representative frames first")
    content = path.read_bytes()
    readers = {".xyz": xyz, ".sdf": sdf, ".mol": sdf, ".pdb": pdb, ".cif": cif}
    if path.suffix.lower() not in readers:
        raise ValueError(f"Unsupported format {path.suffix}; use XYZ/SDF V2000/PDB/P1 CIF")
    frames = readers[path.suffix.lower()](content.decode("utf-8-sig"))
    source = dict(name=path.name, sha256=hashlib.sha256(content).hexdigest(), format=path.suffix[1:], coordinate_unit="angstrom", parser=f"structure-viewer/{VERSION}")
    for i, f in enumerate(frames):
        f.update(id=f"frame-{i+1}", status="unverified", source={**source, "record": i+1})
    return frames


def validate_dataset(data):
    if data.get("schema") != "structure-viewer/1" or not isinstance(data.get("models"), list) or not data["models"]:
        raise ValueError("Expected structure-viewer/1 dataset with models")
    if len(data["models"]) > 100: raise ValueError("Max 100 models per dataset")
    mids, total = set(), 0
    for model in data["models"]:
        if not isinstance(model.get("id"), str) or model["id"] in mids: raise ValueError("Model ids must be unique strings")
        mids.add(model["id"])
        frames = model.get("frames", [])
        if not 1 <= len(frames) <= 200: raise ValueError("Each model needs 1–200 frames")
        fids = set()
        for f in frames:
            if not isinstance(f.get("id"), str) or f["id"] in fids: raise ValueError("Frame ids must be unique strings")
            fids.add(f["id"])
            if f.get("status") not in STATUSES: raise ValueError("Unknown frame status")
            if f["status"] == "accepted" and not f.get("acceptance_evidence"): raise ValueError("Accepted status requires acceptance_evidence; renderer does not establish scientific acceptance")
            source = f.get("source", {})
            if not source.get("name") or not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")): raise ValueError("Every frame requires a source name and SHA256")
            if source.get("coordinate_unit") != "angstrom": raise ValueError("Normalize coordinates to angstroms explicitly")
            atoms = f.get("atoms", [])
            if not 0 < len(atoms) <= MAX_ATOMS: raise ValueError("Frame atom count must be 1–50000")
            total += len(atoms)
            ids = set()
            for a in atoms:
                if not isinstance(a.get("id"), str) or not a["id"] or a["id"] in ids: raise ValueError("Stable atom ids must be unique nonempty strings")
                ids.add(a["id"])
                if a.get("element") not in ELEMENTS or len(a.get("position", [])) != 3 or any(not isinstance(x, (int,float)) or not math.isfinite(x) for x in a["position"]): raise ValueError("Invalid element/coordinate")
                if not isinstance(a.get("fragment"), str): raise ValueError("Each atom needs a fragment string")
            if f.get("bond_mode") not in {"explicit", "explicit-partial", "absent"}: raise ValueError("Bonds must be explicit, explicit-partial or absent")
            bonds, seen = f.get("bonds", []), set()
            if f["bond_mode"] == "absent" and bonds: raise ValueError("Absent bond mode cannot contain bonds")
            for b in bonds:
                a, c = b.get("a"), b.get("b")
                if a not in ids or c not in ids or a == c or b.get("order") not in {1,1.5,2,3}: raise ValueError("Invalid bond")
                pair = tuple(sorted((a,c)))
                if pair in seen: raise ValueError("Duplicate bond")
                seen.add(pair)
            if "cell" in f:
                cell = f["cell"]; v = cell.get("vectors", [])
                origin=cell.get("origin",[0,0,0])
                if len(origin)!=3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in origin): raise ValueError("Invalid cell origin")
                if len(v) != 3 or any(len(row) != 3 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in row) for row in v): raise ValueError("Invalid cell vectors")
                det = sum(v[0][i]*(v[1][(i+1)%3]*v[2][(i+2)%3]-v[1][(i+2)%3]*v[2][(i+1)%3]) for i in range(3))
                if abs(det) < 1e-8: raise ValueError("Singular cell")
                if len(cell.get("periodic", [])) != 3 or any(type(x) is not bool for x in cell["periodic"]): raise ValueError("Cell needs three periodic booleans")
            expected = coordinate_hash(atoms)
            if f.get("coordinate_sha256", expected) != expected: raise ValueError("Coordinate identity checksum mismatch")
            f["coordinate_sha256"] = expected
            for preset in model.get("presets", []):
                if not preset.get("id") or not isinstance(preset.get("fragments"), list): raise ValueError("Invalid visibility preset")
    if total > MAX_TOTAL: raise ValueError("Dataset exceeds 250000 atom records; select representative frames")
    return data
