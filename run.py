"""Start the included demo. Python 3.10+; no pip installation needed."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required")
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["start", "stop", "status"], default="start")
    parser.add_argument("--no-open", action="store_true", help="Print local URL without opening a browser")
    parser.add_argument("--project", type=Path, default=root / "demo-project")
    args = parser.parse_args()
    project = args.project.resolve()
    bundle = project / "codex-files/molook-demo-v1.1.1"
    cli = [sys.executable, "-B", str(root / "scripts/preview.py")]
    if not bundle.exists():
        if args.action != "start":
            print('{"running": false, "message": "Demo has not been built"}')
            return 0
        subprocess.run(cli + ["build", "--project", str(project), "--output", str(bundle),
                             "--dataset", str(root / "examples/demo.json")], check=True)
    command = cli + [args.action, "--bundle", str(bundle)]
    if args.action == "start" and not args.no_open:
        command += ["--open"]
    return subprocess.run(command).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
