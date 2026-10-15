# 数据接口 v1

`examples/demo.json` 是完整可运行样例。顶层 `schema` 为 `structure-viewer/1`，含 `title`、`description`、`models`。

```json
{
  "schema": "structure-viewer/1",
  "title": "My structures",
  "models": [{
    "id": "model-a", "title": "Model A",
    "fragments": {"fragment-1": {"title": "Molecule", "color": "#338f83"}},
    "presets": [{"id": "molecule", "title": "Molecule only", "fragments": ["fragment-1"]}],
    "frames": [{
      "id": "frame-1", "title": "Source geometry", "status": "unverified",
      "source": {"name": "source.sdf", "sha256": "REPLACE_WITH_64_HEX_SOURCE_FILE_SHA256", "coordinate_unit": "angstrom"},
      "atoms": [{"id": "1", "element": "C", "position": [0.0, 0.0, 0.0], "fragment": "fragment-1"}],
      "bonds": [], "bond_mode": "absent", "warnings": []
    }]
  }]
}
```

上例 SHA256 是必须替换的占位，不能直接通过校验。建议由 `read_structure` 产生帧和真实文件指纹，然后补充显示信息。
`coordinate_sha256` 由校验器生成；已有时必须与坐标和原子身份一致。
模型/帧 ID 必须在各自作用域内唯一；原子 ID 用字符串。一个 bond 是 `{"a":"1","b":"2","order":1}`；键级允许 1、1.5、2、3。
`bond_mode` 为 `explicit`、`explicit-partial` 或 `absent`，`absent` 不得附键。

可选 `cell`：`vectors` 是三行 Å 格矢，`periodic` 是三个布尔值，`origin` 默认 `[0,0,0]`。
可选状态：`initial`、`illustrative`、`running`、`accepted`、`unverified`。`accepted` 另需非空 `acceptance_evidence`。软件只保存声明和证据引用，不替代科学审查。
最大 100 模型、每模型 200 帧、每帧 50,000 原子，总计 250,000 原子记录。WebGL 实际交互性能取决于设备。

| 文件类型 | 支持范围 |
| --- | --- |
| XYZ | 单/多帧、每行 element x y z；简单 Extended XYZ Lattice/pbc；没有连接信息 |
| SDF / MOL | V2000，显式键级；连接分量生成片段；不支持 V3000/query bonds；电荷/立体化学留在源文件，不做化学验算 |
| PDB | 显式元素列、MODEL、CRYST1、CONECT；不猜蛋白键；拒绝 altloc/部分占位 |
| CIF | 单数据块、明确 P1、完整占位；分数/笛卡尔坐标；不做对称扩展或无序选择 |

所有归一化坐标单位为 Å，直接保留源坐标意义。XYZ 原始单位需提供者确认。
保存的视图使用 `structure-viewer-view/1`，构建清单使用 `structure-viewer-bundle/1`；这是独立包的数据命名空间。
