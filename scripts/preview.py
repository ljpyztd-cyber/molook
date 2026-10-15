"""Build, validate and serve offline molecular structure previews. Python 3.10+, stdlib only."""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
from preview_formats import VERSION, read_structure, validate_dataset, digest


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project_output(project, output):
    project = Path(project).resolve()
    base = project / "codex-files"
    target = Path(output).resolve() if output else base / ("structure_preview_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    if not target.is_relative_to(base.resolve()) or target == base.resolve():
        raise ValueError("Build output must be a new subfolder of <project>/codex-files")
    return target


def build(args):
    out = project_output(args.project, args.output)
    if out.exists():
        raise ValueError(f"Output exists; choose a new folder (no overwrite): {out}")
    if args.dataset:
        data = json.loads(Path(args.dataset).read_text(encoding="utf-8-sig"))
    else:
        if not args.input: raise ValueError("Provide --input or --dataset")
        if args.status == "accepted" and not args.evidence: raise ValueError("--status accepted needs --evidence")
        models = []
        for i, path in enumerate(args.input, 1):
            frames = read_structure(path)
            for f in frames:
                f["status"] = args.status
                if args.evidence: f["acceptance_evidence"] = args.evidence
            models.append(dict(id=f"model-{i}", title=Path(path).stem, frames=frames))
        data = dict(schema="structure-viewer/1", title=args.title, description="Local structure inspection. Display changes never modify source coordinates.", models=models)
    data = validate_dataset(data)
    package = Path(__file__).resolve().parents[1]
    assets = package / "assets" / "structure-viewer"
    if not assets.is_dir(): raise ValueError("Build requires the distribution assets folder; bundle runtime supports start/stop/status only")
    # Validation precedes creation. A failed build retains evidence, never removes user files.
    out.mkdir(parents=True)
    shutil.copytree(assets, out / "web")
    (out / "runtime").mkdir()
    for name in ("preview.py", "preview_formats.py"):
        shutil.copy2(Path(__file__).parent / name, out / "runtime" / name)
    dump(out / "web/dataset.json", data)
    (out / "sources").mkdir()
    if args.dataset:
        shutil.copy2(args.dataset, out / "sources/input_dataset.json")
    else:
        for i, p in enumerate(args.input, 1): shutil.copy2(p, out / "sources" / f"{i:03d}_{Path(p).name}")
    manifest = dict(schema="structure-viewer-bundle/1", version=VERSION, created_utc=dt.datetime.now(dt.timezone.utc).isoformat(), dataset_sha256=sha(out / "web/dataset.json"), files={str(p.relative_to(out)).replace("\\", "/"): sha(p) for p in out.rglob("*") if p.is_file()})
    dump(out / "bundle.json", manifest)
    print(json.dumps(dict(bundle=str(out), models=len(data["models"]), frames=sum(len(m["frames"]) for m in data["models"]), dataset_sha256=manifest["dataset_sha256"]), ensure_ascii=False))


def bundle_path(raw):
    root = Path(raw).resolve()
    if "codex-files" not in [p.lower() for p in root.parts]:
        raise ValueError("Runtime bundle must be inside a project's codex-files")
    if not (root / "bundle.json").is_file(): raise ValueError("Not a preview bundle")
    manifest = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "structure-viewer-bundle/1": raise ValueError("Unsupported bundle")
    for child in (".runtime", "exports", "imports"):
        if not (root/child).resolve().is_relative_to(root):
            raise ValueError(f"Writable folder escapes bundle: {child}")
    for rel, expected in manifest["files"].items():
        file = (root / rel).resolve()
        if not file.is_relative_to(root) or not file.is_file() or sha(file) != expected:
            raise ValueError(f"Bundle integrity mismatch: {rel}. Rebuild in a new folder.")
    return root


def local_request(url, body=None, session_key=None):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type":"application/json", **({"X-Preview-Token":session_key} if session_key else {})})
    # Ignore machine-wide proxy settings for loopback services.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=2) as response:
        return json.load(response)


def running(root):
    state = root / ".runtime/server.json"
    if not state.exists(): return None
    try:
        obj = json.loads(state.read_text(encoding="utf-8"))
        u = urllib.parse.urlsplit(obj["url"])
        if u.hostname != "127.0.0.1" or u.scheme != "http": return None
        health = local_request(obj["url"] + "api/health")
        if health.get("instance") == obj["instance"] and health.get("dataset_sha256") == sha(root / "web/dataset.json"):
            return obj
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        pass
    return None


def png_metadata(raw, metadata):
    if raw[:8] != b"\x89PNG\r\n\x1a\n": raise ValueError("Expected PNG")
    pos, chunks, width, height = 8, [], 0, 0
    while pos+12 <= len(raw):
        n = int.from_bytes(raw[pos:pos+4], "big")
        kind = raw[pos+4:pos+8]; content = raw[pos+8:pos+8+n]
        if pos+12+n > len(raw) or zlib.crc32(kind+content) & 0xffffffff != int.from_bytes(raw[pos+8+n:pos+12+n], "big"):
            raise ValueError("Invalid PNG chunk/CRC")
        if kind == b"IHDR":
            width,height = struct.unpack(">II", content[:8])
            if not 1 <= width <= 12000 or not 1 <= height <= 12000 or width*height > 60_000_000: raise ValueError("PNG resolution limit exceeded")
        if kind == b"IEND":
            if pos+12+n != len(raw) or not width: raise ValueError("Invalid PNG termination")
            payload = b"Structure Viewer\0\0\0\0\0" + json.dumps(metadata, ensure_ascii=False).encode("utf-8")
            chunk = b"iTXt" + payload
            return raw[:pos] + struct.pack(">I",len(payload)) + chunk + struct.pack(">I", zlib.crc32(chunk)&0xffffffff) + raw[pos:]
        pos += n+12
    raise ValueError("Incomplete PNG")


def serve(args):
    root = bundle_path(args.bundle)
    runtime = root / ".runtime"; runtime.mkdir(exist_ok=True)
    if running(root): raise ValueError("Bundle is already served; use start to reuse")
    token, instance = secrets.token_urlsafe(32), secrets.token_hex(16)
    touched = [time.monotonic()]
    dataset_sha = sha(root / "web/dataset.json")
    static = {"/": "index.html", "/index.html":"index.html", "/app.js":"app.js", "/style.css":"style.css", "/dataset.json":"dataset.json"}
    for p in (root/"web/vendor").iterdir():
        if p.is_file(): static["/vendor/"+p.name] = "vendor/"+p.name
    types = {".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8", ".css":"text/css; charset=utf-8", ".json":"application/json; charset=utf-8", ".png":"image/png", ".txt":"text/plain; charset=utf-8"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "StructureViewer/" + VERSION

        def log_message(self, fmt, *values):
            print(dt.datetime.now(dt.timezone.utc).isoformat(), fmt % values, flush=True)

        def boundary(self):
            host = f"127.0.0.1:{self.server.server_port}"
            origin = self.headers.get("Origin")
            return self.headers.get("Host") == host and (not origin or origin == "http://"+host) and self.headers.get("Sec-Fetch-Site", "none") != "cross-site"

        def reply(self, code, content, content_type="application/json; charset=utf-8"):
            if not isinstance(content, bytes): content = json.dumps(content, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try: self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError): pass

        def do_GET(self):
            if not self.boundary(): return self.reply(403, {"error":"Loopback same-origin access only"})
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health": return self.reply(200, dict(version=VERSION, instance=instance, dataset_sha256=dataset_sha))
            touched[0] = time.monotonic()
            if path == "/api/session": return self.reply(200, {"token":token, "dataset_sha256":dataset_sha, "version":VERSION, "export_path":str(root/"exports"), "idle_minutes":args.idle_minutes})
            if path in static:
                p = (root / "web" / static[path]).resolve()
                if not p.is_relative_to(root/"web"): return self.reply(403, {"error":"Path boundary"})
            elif re.fullmatch(r"/exports/[a-zA-Z0-9_.-]+\.(png|json)", path):
                p = (root / path.lstrip("/")).resolve()
                if not p.is_relative_to(root/"exports"): return self.reply(403, {"error":"Path boundary"})
            else: return self.reply(404, {"error":"No such preview resource"})
            if not p.is_file(): return self.reply(404, {"error":"Missing preview resource"})
            self.reply(200, p.read_bytes(), types.get(p.suffix,"application/octet-stream"))

        def do_POST(self):
            if not self.boundary() or not secrets.compare_digest(self.headers.get("X-Preview-Token", ""),token): return self.reply(403, {"error":"Invalid local session"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= 48*1024*1024: raise ValueError("Request too large (48 MiB limit)")
                self.connection.settimeout(20)
                value = json.loads(self.rfile.read(n))
                touched[0] = time.monotonic()
                if self.path == "/api/stop":
                    self.reply(200, {"stopped":True}); threading.Thread(target=self.server.shutdown, daemon=True).start(); return
                if self.path == "/api/restore-imports":
                    restored=[]
                    for expected in value.get("models",[]):
                        mid=expected.get("id", "")
                        if not re.fullmatch(r"import-\d{8}T\d{6}_[a-f0-9]{8}",mid): raise ValueError("Invalid imported model id")
                        stored=root/"imports"/mid.removeprefix("import-")/"normalized.json"
                        model=json.loads(stored.read_text(encoding="utf-8"))
                        if model!=expected: raise ValueError("Imported model differs from archived source record")
                        validate_dataset(dict(schema="structure-viewer/1",models=[model]));restored.append(model)
                    return self.reply(200, {"models":restored})
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+secrets.token_hex(4)
                if self.path == "/api/import":
                    name = Path(value["name"]).name
                    if not name or len(name)>180 or Path(name).suffix.lower() not in {".xyz",".sdf",".mol",".pdb",".cif"}: raise ValueError("Unsupported input extension")
                    dest = root / "imports" / stamp
                    dest.mkdir(parents=True)
                    src = dest / ("source"+Path(name).suffix.lower())
                    if "data_base64" in value:
                        content=base64.b64decode(value["data_base64"],validate=True)
                    else:
                        text=value["text"]
                        if not isinstance(text,str): raise ValueError("Expected UTF-8 structure text")
                        content=text.encode("utf-8")
                    src.write_bytes(content)
                    frames = read_structure(src)
                    for f in frames: f["source"]["name"] = name
                    model = dict(id="import-"+stamp,title=name,frames=frames)
                    validate_dataset(dict(schema="structure-viewer/1",models=[model]))
                    dump(dest / "normalized.json",model)
                    return self.reply(200, {"model":model})
                if self.path == "/api/export":
                    kind = value["kind"]
                    metadata = value.get("metadata", {})
                    if not isinstance(metadata,dict): raise ValueError("Expected metadata object")
                    metadata.update(renderer_version=VERSION, dataset_sha256=dataset_sha, exported_utc=dt.datetime.now(dt.timezone.utc).isoformat())
                    out = root/"exports"; out.mkdir(exist_ok=True)
                    if kind == "png":
                        prefix = "data:image/png;base64,"
                        if not value["data"].startswith(prefix): raise ValueError("Expected PNG data URI")
                        raw = png_metadata(base64.b64decode(value["data"][len(prefix):],validate=True), metadata)
                        name = "structure_"+stamp+".png"
                        with (out/name).open("xb") as handle: handle.write(raw)
                        dump(out/(name+".json"), metadata)
                    elif kind == "view":
                        name = "view_"+stamp+".json"
                        dump(out/name,metadata)
                    else: raise ValueError("Unknown export kind")
                    return self.reply(200,dict(name=name,url="/exports/"+name,path=str(out/name)))
                self.reply(404,{"error":"Unknown API"})
            except (ValueError,KeyError,TypeError,OSError,OverflowError) as e:
                self.reply(400,{"error":str(e)})

    try: server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        if not args.port or e.errno not in (98, 48, 10048, 10013, 13): raise
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    url = f"http://127.0.0.1:{server.server_port}/"
    state = {"url":url,"pid":os.getpid(),"instance":instance,"token":token,"dataset_sha256":dataset_sha,"started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"idle_minutes":args.idle_minutes}
    dump(runtime / "server.tmp",state); (runtime / "server.tmp").replace(runtime/"server.json")
    print(json.dumps({k:v for k,v in state.items() if k != "token"}),flush=True)

    def idle():
        while not stop_event.wait(15):
            if time.monotonic()-touched[0] > args.idle_minutes*60:
                server.shutdown(); break
    stop_event = threading.Event()
    threading.Thread(target=idle,daemon=True).start()
    try: server.serve_forever(poll_interval=.25)
    finally:
        stop_event.set(); server.server_close()
        # Leave a non-secret receipt for diagnostics. Never kill a PID from stale state.
        dump(runtime/"last_stop.json",dict(instance=instance,stopped_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
        if (runtime/"server.json").exists():
            stored=json.loads((runtime/"server.json").read_text())
            if stored.get("instance")==instance: (runtime/"server.json").unlink()


def lifecycle(args):
    root=bundle_path(args.bundle)
    state=running(root)
    if args.command=="status":
        print(json.dumps(dict(running=bool(state),url=state["url"] if state else None),ensure_ascii=False)); return
    if args.command=="stop":
        if state:
            local_request(state["url"]+"api/stop",{},state["token"])
            for _ in range(40):
                if not running(root): break
                time.sleep(.1)
            if running(root): raise ValueError("Stop requested but service still responding")
        print(json.dumps(dict(stopped=bool(state),already_stopped=not bool(state)))); return
    if state:
        print(json.dumps(dict(url=state["url"],reused=True)));
        if args.open: webbrowser.open(state["url"])
        return
    runtime=root/".runtime"; runtime.mkdir(exist_ok=True)
    lock=runtime/"start.lock"
    if lock.exists() and time.time()-lock.stat().st_mtime>30: lock.unlink()
    try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise ValueError("Another start is in progress; retry shortly")
    os.close(fd)
    try:
        with (runtime/"server.log").open("ab") as log:
            flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
            proc=subprocess.Popen([sys.executable,"-B",str(root/"runtime/preview.py"),"serve","--bundle",str(root),"--port",str(args.port),"--idle-minutes",str(args.idle_minutes)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=flags,start_new_session=os.name!="nt",cwd=str(root))
        for _ in range(70):
            state=running(root)
            if state: break
            if proc.poll() is not None: raise ValueError(f"Server exited; see {runtime/'server.log'}")
            time.sleep(.1)
        if not state: raise ValueError(f"Start outcome unknown; inspect status and {runtime/'server.log'} before retry")
        print(json.dumps(dict(url=state["url"],reused=False,log=str(runtime/"server.log")),ensure_ascii=False))
        if args.open: webbrowser.open(state["url"])
    finally: lock.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("build"); p.add_argument("--project",required=True); p.add_argument("--output"); p.add_argument("--input",action="append"); p.add_argument("--dataset"); p.add_argument("--title",default="Structure review"); p.add_argument("--status",choices=["initial","illustrative","running","accepted","unverified"],default="unverified"); p.add_argument("--evidence")
    p=sub.add_parser("validate"); p.add_argument("--dataset",required=True)
    for command in ("start","serve","status","stop"):
        p=sub.add_parser(command); p.add_argument("--bundle",required=True)
        if command in {"start","serve"}:
            p.add_argument("--port",type=int,default=0); p.add_argument("--idle-minutes",type=float,default=120)
        if command=="start": p.add_argument("--open",action="store_true")
    args=parser.parse_args()
    try:
        if hasattr(args,"idle_minutes") and not 0 < args.idle_minutes <= 1440: raise ValueError("idle-minutes must be in (0, 1440]")
        if hasattr(args,"port") and not 0 <= args.port <= 65535: raise ValueError("Invalid port")
        if args.command=="build": build(args)
        elif args.command=="validate":
            data=validate_dataset(json.loads(Path(args.dataset).read_text(encoding="utf-8-sig")))
            print(json.dumps(dict(valid=True,models=len(data["models"]))))
        elif args.command=="serve": serve(args)
        else: lifecycle(args)
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(json.dumps(dict(error=str(exc)),ensure_ascii=False),file=sys.stderr); return 1
    return 0


if __name__=="__main__": sys.exit(main())
