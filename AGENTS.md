# Structure Viewer agent guide

Scope: this standalone application only. Read README.md (or README.zh-CN.md), DEPLOY_WITH_AGENT.md and AGENT_HANDOFF.md.

- Python 3.10+, standard library only; the browser renderer is bundled locally.
- Default to independent panel cameras. Linking is an explicit user choice.
- Preserve source coordinates, stable IDs, explicit connectivity and provenance. Rendering does not establish scientific acceptance.
- Keep the service on 127.0.0.1 and retain origin/host, request-token and bundle-integrity checks.
- Put generated files inside the selected project's codex-files folder. Build new bundles after code/data changes; preserve old snapshots.
- Run python -B scripts/self_test.py. Inspect the real browser and exported image when rendering changes.
- Preserve third-party licenses and exact dependency hashes. Do not add CDN calls or upload user data during ordinary preview work.
- Publish only the explicit files listed in scripts/package_release.py; exclude runtime state, imports, private exports, logs, caches and unrelated project files.
