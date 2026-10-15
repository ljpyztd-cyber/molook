# Deploy with your agent / 给 Agent 的部署提示词

No separate skill is required. Copy the appropriate prompt below into your agent and replace the work-directory placeholder. / 无需安装其他 skill。将下面提示词交给 agent，并替换工作目录占位符。

## 中文提示词

```text
请部署并接手 Structure Viewer：
https://github.com/ljpyztd-cyber/structure-viewer

工作目录：<填写可写的本地目录>

1. 先读取 README.zh-CN.md、AGENTS.md 和 AGENT_HANDOFF.md。克隆仓库或使用 Release ZIP；保留完整目录结构，不覆盖已有工作。
2. 检查 Python >= 3.10 与浏览器 WebGL。依赖已离线包含，不需要 pip/npm、API key 或额外 skill。
3. 在包根目录运行 python -B scripts/self_test.py；若只有 python3 命令则替换命令名。出现失败应先解释实际原因。
4. 运行 python -B run.py --project "<工作目录>/demo" --no-open，打开实际输出的 127.0.0.1 URL。服务只监听本机；不要部署到公网或更改网络访问控制。
5. 验证两个示例正常渲染，默认未勾选“联动旋转 / 缩放”；拖动一个面板，另一个不动。检查帧切换、片段筛选、一次测距和 PNG 导出。
6. 演示结构是合成示意坐标，不能称为优化或验收结果。接入我的数据时保留源坐标、原子 ID、显式连接和来源哈希；不为美观猜键或重优化。
7. 默认保持白底青灰风格和各面板独立操作。样式参考 STYLE_GUIDE.md，数据参考 DATA_FORMAT.md。修改源码后构建新的 bundle，不修改旧快照或绕过校验。
8. 最后告诉我本地地址、启动/停止命令、导出目录及实际通过的检查。所有生成文件放在所选项目的 codex-files 中。公开分享时排除运行状态、会话凭据和我的私有数据。

后续按我的要求改进本地应用；不要主动上传我的结构、开公网端口或安装后台服务。
```

## English prompt

```text
Deploy and take over Structure Viewer:
https://github.com/ljpyztd-cyber/structure-viewer

Working directory: <a writable local directory>

1. Read README.md, AGENTS.md and AGENT_HANDOFF.md. Clone the repository or extract its release ZIP, keeping its directory layout and preserving existing work.
2. Check Python >= 3.10 and browser WebGL. Dependencies are bundled offline; no pip/npm package, API key or extra skill is required.
3. Run python -B scripts/self_test.py from the package root (use python3 if needed). Investigate and report any actual failure before claiming success.
4. Run python -B run.py --project "<working directory>/demo" --no-open and open the returned 127.0.0.1 URL. Keep the service local; do not expose it publicly or change network access controls.
5. Verify both synthetic examples render, linked rotation/zoom is off by default, and dragging one panel leaves the other unchanged. Check frame selection, fragment filtering, one distance measurement and PNG export.
6. The examples are synthetic illustrations, not optimized or scientifically accepted results. When loading my data, preserve source coordinates, atom IDs, explicit connectivity and source hashes; do not guess bonds or optimize structures for appearance.
7. Preserve the white/teal visual style and independent panel control by default. Use STYLE_GUIDE.md and DATA_FORMAT.md. After code changes, build a new bundle instead of modifying old snapshots or bypassing integrity checks.
8. Report the local URL, start/stop commands, export directory and checks that actually passed. Keep generated files under the selected project's codex-files directory. Exclude runtime state, session credentials and my private data from any public package.

Continue improving the local application as requested. Do not upload my structures, expose network ports or install a background service without my instruction.
```

## Stop / 停止

Use the **same** `--project` value as at startup / 使用与启动时**相同**的项目目录：

```sh
python -B run.py stop --project "/path/to/work/demo"
```
