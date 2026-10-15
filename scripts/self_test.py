"""Stdlib smoke tests. Generated files stay under this package's codex-files/."""
import base64
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import unittest
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from preview_formats import read_structure, validate_dataset

FIX = ROOT / "examples/fixtures"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset():
    return json.loads((ROOT / "examples/demo.json").read_text(encoding="utf-8"))


def cli(*args, expected=0):
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/preview.py"), *map(str, args)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != expected:
        raise AssertionError(f"Command {args[0]}: return code {result.returncode}; {result.stderr}")
    return json.loads(result.stdout if expected == 0 else result.stderr)


class DataTests(unittest.TestCase):
    def test_distribution_manifest(self):
        path = ROOT / "MANIFEST.sha256.json"
        if not path.exists():
            self.skipTest("Development tree: distribution manifest not generated yet")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for name, expected in manifest["files"].items():
            with self.subTest(file=name):
                target = (ROOT / name).resolve()
                self.assertTrue(target.is_relative_to(ROOT))
                self.assertEqual(sha(target), expected)

    def test_vendor_bytes(self):
        vendor = ROOT / "assets/structure-viewer/vendor"
        data = json.loads((vendor / "dependency.json").read_text(encoding="utf-8"))
        for name, expected in data["files"].items():
            self.assertEqual(sha(vendor / name), expected)

    def test_demo_integrity(self):
        data = validate_dataset(dataset())
        self.assertEqual(len(data["models"]), 2)
        for model in data["models"]:
            parsed = read_structure(ROOT / "examples" / model["frames"][0]["source"]["name"])
            self.assertEqual(len(parsed), 2)
            for actual, frame in zip(parsed, model["frames"]):
                self.assertEqual(actual["atoms"], frame["atoms"])
                self.assertEqual(actual["bonds"], frame["bonds"])
                self.assertEqual(actual["source"]["sha256"], frame["source"]["sha256"])
                self.assertEqual(frame["status"], "illustrative")
                self.assertEqual(len(frame["atoms"]), 34)

    def test_xyz_no_bond_guessing(self):
        frames = read_structure(FIX / "geometry.xyz")
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["atoms"][0]["position"], [1., 0., 0.])
        self.assertEqual(frames[1]["atoms"][0]["position"], [1.2, 0., 0.])
        self.assertEqual(frames[0]["bonds"], [])
        self.assertEqual(frames[0]["bond_mode"], "absent")

    def test_sdf_explicit_connectivity(self):
        frame = read_structure(FIX / "water.sdf")[0]
        self.assertEqual(len(frame["atoms"]), 3)
        self.assertEqual(len(frame["bonds"]), 2)
        self.assertEqual(frame["bond_mode"], "explicit")

    def test_pdb_serials(self):
        frame = read_structure(FIX / "water.pdb")[0]
        self.assertEqual([a["id"] for a in frame["atoms"]], ["10", "20", "30"])
        self.assertEqual(len(frame["bonds"]), 2)

    def test_cif_cell(self):
        frame = read_structure(FIX / "cell.cif")[0]
        self.assertEqual(len(frame["cell"]["vectors"]), 3)
        self.assertEqual(frame["cell"]["periodic"], [True, True, True])

    def test_coordinate_tamper_rejected(self):
        data = dataset()
        data["models"][0]["frames"][0]["atoms"][0]["position"][0] += .1
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_dataset(data)

    def test_acceptance_needs_evidence(self):
        data = dataset()
        data["models"][0]["frames"][0]["status"] = "accepted"
        with self.assertRaisesRegex(ValueError, "evidence"):
            validate_dataset(data)

    def test_html_assets_are_local(self):
        html = (ROOT / "assets/structure-viewer/index.html").read_text(encoding="utf-8")
        urls = re.findall(r'(?:src|href)="([^"]+)"', html)
        self.assertTrue(urls)
        self.assertTrue(all(not u.startswith(("http:", "https:", "//")) for u in urls))


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + secrets.token_hex(3)
        cls.project = ROOT / "codex-files" / ("self-test " + stamp)
        cls.bundle = cls.project / "codex-files/preview"
        cls.inputs = {p: sha(p) for p in (ROOT / "examples").glob("*.sdf")}
        cls.build_args = ("build", "--project", cls.project, "--output", cls.bundle, "--dataset", ROOT / "examples/demo.json")
        cli(*cls.build_args)
        cls.url = cli("start", "--bundle", cls.bundle)["url"]
        cls.session = cls.get("api/session")

    @classmethod
    def get(cls, path, headers=None):
        request = urllib.request.Request(cls.url + path, headers=headers or {})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as r:
                body = r.read()
                return json.loads(body) if "application/json" in r.headers.get("Content-Type", "") else body
        except urllib.error.HTTPError as exc:
            exc.close()
            raise

    @classmethod
    def post(cls, path, value, token=True):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Preview-Token"] = cls.session["token"]
        request = urllib.request.Request(cls.url + path, data=json.dumps(value).encode(), headers=headers)
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cli("stop", "--bundle", cls.bundle)
        if cli("status", "--bundle", cls.bundle)["running"]:
            raise AssertionError("Service still running after stop")
        for path, expected in cls.inputs.items():
            if sha(path) != expected:
                raise AssertionError("Source file changed")

    def test_bundle_runtime_is_self_contained(self):
        result = subprocess.run([sys.executable, "-B", str(self.bundle / "runtime/preview.py"), "status", "--bundle", str(self.bundle)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["running"])

    def test_reuse(self):
        result = cli("start", "--bundle", self.bundle)
        self.assertTrue(result["reused"])
        self.assertEqual(result["url"], self.url)

    def test_existing_output_is_protected(self):
        self.assertIn("Output exists", cli(*self.build_args, expected=1)["error"])

    def test_http_dataset(self):
        data = self.get("dataset.json")
        self.assertEqual(data["schema"], "structure-viewer/1")
        self.assertEqual(len(data["models"]), 2)
        self.assertIn(b"Structure", self.get(""))

    def test_private_paths_not_served(self):
        for path in (".runtime/server.json", "sources/input_dataset.json", "../bundle.json"):
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as context:
                self.get(path)
            self.assertEqual(context.exception.code, 404)

    def test_cross_origin_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.get("api/session", {"Origin":"https://example.invalid"})
        self.assertEqual(context.exception.code, 403)

    def test_unauthenticated_mutation_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.post("api/export", {"kind":"view","metadata":{}}, token=False)
        self.assertEqual(context.exception.code, 403)

    def test_import_preserves_original_bytes(self):
        raw = (FIX / "geometry.xyz").read_bytes()
        model = self.post("api/import", {"name":"geometry.xyz","data_base64":base64.b64encode(raw).decode()})["model"]
        self.assertEqual(model["frames"][0]["source"]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(model["frames"][0]["status"], "unverified")
        restored = self.post("api/restore-imports", {"models":[model]})
        self.assertEqual(restored["models"], [model])

    def test_saved_view_export(self):
        result = self.post("api/export", {"kind":"view","metadata":{"schema":"structure-viewer-view/1","note":"smoke test"}})
        saved = self.get(result["url"].lstrip("/"))
        self.assertEqual(saved["note"], "smoke test")
        self.assertEqual(saved["dataset_sha256"], self.session["dataset_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
