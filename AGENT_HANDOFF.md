# Architecture and maintenance / 架构与接手

Read [the bilingual deployment prompt](DEPLOY_WITH_AGENT.md) first. / 首先阅读中英文部署提示词。

| File / 文件 | Responsibility / 职责 |
| --- | --- |
| `run.py`, `START_DEMO.cmd`, `STOP_DEMO.cmd` | Demo lifecycle / 演示启动、复用和停止 |
| `assets/structure-viewer/index.html` | Page structure and accessible controls / 页面与控件 |
| `assets/structure-viewer/style.css` | Theme variables and responsive layout / 主题和响应式布局 |
| `assets/structure-viewer/app.js` | Immutable records, panel state, geometry, cameras, exports / 数据副本、面板状态、测量、相机与导出 |
| `scripts/preview_formats.py` | Strict readers and dataset validation / 格式读取和数据校验 |
| `scripts/preview.py` | Bundle builder and loopback HTTP service / 构建及本机服务 |
| `examples/generate_demo.py` | Deterministic synthetic scenes / 确定性合成示例 |
| `scripts/self_test.py` | Standard-library integration tests / 标准库集成测试 |
| `scripts/package_release.py` | Explicit release file list, hashes, ZIP / 发布清单、哈希及打包 |

Key JavaScript entry points: `drawScene`, `measureValue`, `contactCandidates`, `currentView`, `exportPNG`.
`settings.linked` is false at startup; camera callbacks only synchronize when the checkbox is explicitly enabled. Each panel keeps its own translation center. Restoring a deliberately saved linked view restores its saved settings.

初始 `settings.linked=false`。仅主动启用联动时，相机回调同步旋转/缩放，各面板保留自己的平移中心。恢复用户保存的联动视图会恢复该视图的设置。

## Bundle layout / 运行目录

`web/` and `runtime/` are snapshots, `sources/` holds input copies, and `bundle.json` contains hashes. `imports/`, `exports/`, and `.runtime/` are generated locally. Do not publish these runtime directories.

`web/`、`runtime/` 为快照，`sources/` 保留输入副本，`bundle.json` 为校验清单；`imports/`、`exports/`、`.runtime/` 在运行时生成，不应公开。

PNG exports contain provenance metadata and a JSON sidecar. Saved views require a matching dataset hash and locally archived imported models. A view JSON alone does not transfer an imported private structure to another instance.

PNG 带来源元数据及 JSON 旁车；恢复视图要求数据集哈希匹配并保留导入档案，单独携带视图 JSON 不会自动迁移私有导入数据。

## Troubleshooting / 故障定位

- Blank structure: inspect WebGL availability and the browser console. / 空白结构：检查 WebGL 与浏览器错误。
- No bonds in XYZ: expected; supply explicit connectivity. / XYZ 无键属于正常行为，需提供显式连接。
- Import/export fails with direct HTML: use `run.py` or `preview.py start`. / 直接打开 HTML 无后端接口，请使用启动器。
- Integrity mismatch: retain the old bundle and build a new folder. / 校验不一致：保留原目录并新建构建。
- Service diagnostics: `.runtime/server.log`; never share `.runtime/server.json`. / 日志位于前者，后者含实例凭据，请勿分享。
- Address/port: use the URL actually printed by the launcher; do not assume a fixed port. / 使用启动器实际输出端口。
- Releasing a modification: review only intended source files; run tests, regenerate the distribution manifest with the packager, and verify a clean extraction. / 发布修改：审查文件，自检，重新打包生成清单，并解压验证。

## Release workflow / 发布流程

```sh
python -B scripts/package_release.py
python -B scripts/self_test.py
```

The packager writes ZIP/checksum files under `codex-files/releases/` and updates the root distribution manifest. That manifest deliberately excludes itself; the ZIP SHA256 covers the entire archive. Fingerprints detect byte changes and are not digital signatures.

打包脚本在 `codex-files/releases/` 生成 ZIP/校验值并更新根目录清单。清单不包含自身，ZIP 的 SHA256 覆盖整个压缩包；文件指纹不等于数字签名。
