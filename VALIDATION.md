# Validation / 验证范围

## Version 1.1.0 — 2026-10-15

The release is checked with the bundled standard-library suite and an actual local WebGL browser. / 发布前使用包内标准库测试和真实本地 WebGL 浏览器验证。

- Distribution manifest and exact third-party asset hashes. / 发布清单与第三方文件哈希。
- XYZ, SDF, PDB and P1 CIF parsing; demo source coordinates/connectivity match the generated data. / 四种格式读取及示例源坐标/连接一致性。
- Reject modified coordinate fingerprints and unsupported accepted states without evidence. / 拒绝坐标指纹不一致及无证据验收状态。
- Bundle build, no-overwrite boundary, independent runtime, service reuse and stop. / 构建、防覆盖、独立运行、复用和停止。
- Loopback origin/host boundary, authenticated mutation, and exclusion of runtime/private paths from static routes. / 本机来源校验、写操作认证以及私有路径隔离。
- Import source-byte preservation, imported-view restoration, and saved-view export. / 导入源字节保留、导入视图恢复及视图导出。
- Browser checks: synthetic examples render, independent cameras are the default, a panel can rotate without moving its neighbor, and PNG export works. / 浏览器检查：示例正常渲染、默认独立相机、单面板旋转不带动另一面板及 PNG 导出。
- A separately extracted release runs without the original source installation. / 单独解压发布包可运行，无原安装目录依赖。

The exact test count and pass/fail result are printed by `python -B scripts/self_test.py`. Cross-platform CI status is available in the repository's Actions tab. Local browser verification was performed on Windows; macOS UI behavior is not claimed as tested.

`python -B scripts/self_test.py` 输出实际测试数量与结果。跨平台 CI 结果见仓库 Actions。浏览器检查在 Windows 完成，不宣称已实测 macOS 界面。

This validates software behavior, not scientific correctness of arbitrary input structures. / 本验证针对软件行为，不认定任意输入结构的科学正确性。
