"""Create an explicit, runtime-free release ZIP and SHA256 manifests (stdlib only)."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILES = [
    ".gitattributes", ".gitignore", ".github/workflows/tests.yml", "AGENTS.md",
    "README.md", "README.zh-CN.md", "START_HERE.md", "DEPLOY_WITH_AGENT.md", "AGENT_HANDOFF.md",
    "STYLE_GUIDE.md", "DATA_FORMAT.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "VALIDATION.md", "VERSION.json", "preview.jpg", "run.py", "START_DEMO.cmd", "STOP_DEMO.cmd",
    "scripts/preview.py", "scripts/preview_formats.py", "scripts/self_test.py", "scripts/package_release.py",
    "examples/generate_demo.py", "examples/demo.json", "examples/demo-a.sdf", "examples/demo-b.sdf",
    "examples/fixtures/README.md", "examples/fixtures/geometry.xyz", "examples/fixtures/water.sdf",
    "examples/fixtures/water.pdb", "examples/fixtures/cell.cif",
    "assets/structure-viewer/index.html", "assets/structure-viewer/style.css", "assets/structure-viewer/app.js",
    "assets/structure-viewer/vendor/3Dmol-min.js", "assets/structure-viewer/vendor/3Dmol-min.js.LICENSE.txt",
    "assets/structure-viewer/vendor/LICENSE-3Dmol.txt", "assets/structure-viewer/vendor/dependency.json",
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    version = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), "Invalid release version"
    payload = {}
    secret_patterns = [r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
                       r"\bgithub_pat_[A-Za-z0-9_]{50,}\b", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"]
    for name in RELEASE_FILES:
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(), f"Missing/escaped release file: {name}"
        raw = path.read_bytes()
        if path.suffix not in {".jpg", ".png"}:
            text = raw.decode("utf-8-sig")
            assert not any(re.search(pattern, text) for pattern in secret_patterns), f"Possible credential: {name}"
            assert not re.search(r"[A-Z]:[\\/]Users[\\/][^\\/\s]+", text), f"Machine user path: {name}"
        payload[name] = raw
    vendor = "assets/structure-viewer/vendor/"
    dependency = json.loads(payload[vendor + "dependency.json"])
    for name, expected in dependency["files"].items():
        assert sha(payload[vendor + name]) == expected, f"Vendor byte change: {name}"
    manifest = {"schema":"structure-viewer-distribution/1", "version":version,
                "files":{name:sha(raw) for name, raw in sorted(payload.items())}}
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    (ROOT / "MANIFEST.sha256.json").write_bytes(manifest_bytes)
    payload["MANIFEST.sha256.json"] = manifest_bytes
    output = ROOT / "codex-files/releases"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"structure-viewer-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(payload.items()):
            entry = zipfile.ZipInfo("structure-viewer/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    checksum = sha(archive.read_bytes())
    (output / (archive.name + ".sha256")).write_text(checksum + "  " + archive.name + "\n", encoding="ascii")
    print(json.dumps({"archive":str(archive), "files":len(payload), "bytes":archive.stat().st_size, "sha256":checksum}))


if __name__ == "__main__":
    main()
