# Molook

[简体中文](README.zh-CN.md) · [Agent deployment prompt / Agent 部署提示词](DEPLOY_WITH_AGENT.md) · [Releases](https://github.com/ljpyztd-cyber/molook/releases)

**Molook** (Mol + Look), 中文名 **分子窗**. An offline, local molecular structure viewer with a clean white-and-teal interface. Compare up to four structures, inspect source atom IDs, measure geometry and export high-resolution figures with provenance.

**Version 1.1.1: each panel rotates and zooms independently by default.** Linked rotation/zoom is available only when you explicitly select the checkbox.

![Synthetic example interface](preview.jpg)

## Run in a minute

Requires **Python 3.10+** and a modern **WebGL-enabled browser**. No pip/npm installation, cloud account or API key is needed. The 3Dmol.js renderer is included locally.

Download and extract the release ZIP, or clone the repository:

```sh
git clone https://github.com/ljpyztd-cyber/molook.git
cd molook
python -B run.py
```

On Windows, you can also double-click `START_DEMO.cmd`. On macOS/Linux use `python3` if that is your Python command. Open the `http://127.0.0.1:<port>/` URL printed by the launcher if the browser does not open automatically.

```sh
python -B run.py --no-open     # start without opening a browser
python -B run.py status        # check this demo instance
python -B run.py stop          # stop this demo instance
python -B scripts/self_test.py # standard-library tests
```

Windows also includes `STOP_DEMO.cmd`. The first start builds a snapshot under `demo-project/codex-files/molook-demo-v1.1.1/`. Repeated starts reuse the matching service. The service listens only on **127.0.0.1** and stops after 120 idle minutes by default.

To choose a different work directory, add `--project "/path/to/MyProject"` to **all** start/status/stop commands. Generated bundles, imports, exports and logs stay under that project's `codex-files/` folder.

Do not open `index.html` directly: imports, exports and view restoration require the Python service. This is a local application, not a hosted multi-user service or a GitHub Pages deployment.

## Features

- Two/four-panel comparison; independent cameras by default, optional linked rotation/zoom.
- Ball-and-stick, stick, space-filling and line styles; element or fragment carbon colors; hydrogen, label, cell and fragment visibility controls.
- Stable source atom IDs, direct Cartesian distances, angles and signed dihedrals.
- Explicit-bond geometric contact candidates, clearly distinguished from scientific assignments.
- PNG export at 1,200 / 1,800 / 2,400 pixels **per panel**, with source hashes, actual export cameras and visibility metadata in the PNG and JSON sidecar.
- Save/restore view settings within the same dataset; source coordinates remain unchanged.

The UI labels are currently Chinese. The README and agent deployment instructions are provided in English and Chinese.

## Load your own structures

Click **＋ 导入结构** (Import structure), or build a separate bundle from the CLI:

```sh
python -B scripts/preview.py build --project "/path/to/MyProject" --input "/path/to/model.sdf" --title "My structures"
python -B scripts/preview.py start --bundle "/path/printed/by/build" --open
python -B scripts/preview.py stop --bundle "/path/printed/by/build"
```

Repeat `--input` for multiple structures. For named/color-coded fragments and custom presets, use `--dataset examples/demo.json`; see [the data contract](DATA_FORMAT.md) and the executable example generator.

| Format | Supported scope |
| --- | --- |
| XYZ | Single/multiple frames, exactly element + x/y/z; simple Extended XYZ lattice/pbc |
| SDF / MOL | V2000 with explicit connectivity and bond orders; no V3000 or query bonds |
| PDB | Explicit element columns, MODEL, CRYST1 and CONECT; no alternate locations or partial occupancy |
| CIF | Single explicit P1 block with full occupancy; no symmetry expansion or disorder selection |

Missing bond information is **not guessed**. XYZ therefore displays atoms without inferred covalent bonds. All normalized positions are in ångströms; XYZ input units must be confirmed by the data provider.

## Scientific and operational boundaries

The included scenes are synthetic illustrations, **not optimized geometries or research results**. Rendering does not establish convergence, chemical validity or scientific acceptance. An `accepted` record requires an evidence reference supplied by the data provider.

Measurements use the original Cartesian positions without minimum-image conventions. Contact lines are limited geometric candidates, not a complete hydrogen-bond analysis. Independently fitted panels do not share a common scale.

Display operations do not rewrite source coordinates. Input snapshots and hashes are retained. Existing bundles are immutable snapshots: after editing source code or data, build a **new output folder** rather than modifying an existing bundle or bypassing its integrity checks.

The service uses same-origin/host checks and a per-instance write token. Do not publish `.runtime/`, imported private structures, private exports or logs. The public package contains only application code, documentation, third-party notices and synthetic examples.

## Handoff and development

- [Copy-ready agent prompts (EN / 中文)](DEPLOY_WITH_AGENT.md)
- [Architecture and maintenance notes](AGENT_HANDOFF.md)
- [Visual style guide](STYLE_GUIDE.md)
- [Data contract](DATA_FORMAT.md)
- [Release notes](CHANGELOG.md) and [validation scope](VALIDATION.md)

Local testing uses the Python standard library. GitHub Actions runs the same tests on Windows and Ubuntu with Python 3.10 and 3.13. The release packager uses an explicit file list and excludes runtime outputs and Git history.

## License

Application code and synthetic examples: [MIT](LICENSE). Bundled 3Dmol.js 2.5.5: BSD-3-Clause plus its bundled dependency notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
