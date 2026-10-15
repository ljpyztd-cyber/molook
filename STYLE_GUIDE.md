# 视觉风格说明

设计目标：明亮、克制、清楚的科学结构工作台。把结构和比较关系放在视觉中心；用低饱和青灰组织操作，红/蓝等元素色留给结构。

| 元素 | 当前值 / 规则 |
| --- | --- |
| 页面背景 | `#f3f6f7` |
| 卡片 / 渲染背景 | `#ffffff` |
| 主文字 | `#223847` |
| 次文字 | `#687b88` |
| 主操作色 | `#226d70` |
| 细边框 | `#dce5e8` |
| 字体 | Segoe UI → Microsoft YaHei → sans-serif，不依赖在线字体 |
| 卡片圆角 | 10 px；控件 6–7 px |
| 字号 | 页标题 25 px，卡片 16 px，控件 12–14 px，辅助信息 11 px |
| 大屏布局 | 左侧 248 px 控件列 + 右侧弹性结构区；面板双列 |
| 小屏布局 | 900 px 以下结构单列；620 px 以下结构区优先、控件移到下方 |

可直接从 `style.css` 的 `:root` 修改主题。`.page-header`、`.comparison-bar`、`.controls`、`.card`、`.card-head`、`.card-foot` 是主要组件。

## 结构渲染约定

- 白色背景、正交相机、清晰球棍；氢默认显示，可关闭。
- 片段着色只改变碳原子，其他元素保留识别色；片段颜色由数据集提供。
- 多面板默认独立旋转/缩放，主动勾选后才联动；联动时各自保持结构中心，不联动平移。
- 标签有浅底，强调片段身份；不要遮住核心结构。过密时关闭标签或筛选片段。
- 示意、初始、待核验状态使用低饱和提示色，不用“已验收”装饰演示。
- 导出是新的高清 WebGL 渲染，不是拉伸屏幕截图。默认每面板 1,800 px，可选 1,200/2,400 px。
- 独立适配的面板不是共同尺度；导出底部保留这一说明。

## 改样式后的验收

检查 1400 px 桌面与约 390 px 窄屏；无横向溢出，长标题/来源能折行，按钮可读且可聚焦。
检查双面板和单面板、隐藏氢/片段、旋转后的适配、高清 PNG 的标签留白。
保持数据来源和显示状态可查；不要把实现细节塞入主要操作路径。

## English quick reference

Use a light, restrained scientific workbench: white cards on `#f3f6f7`, ink `#223847`, muted text `#687b88`, teal actions `#226d70`, and borders `#dce5e8`. System fonts avoid network dependencies. Start visual changes in `assets/structure-viewer/style.css`.

Cards use 10 px corners, compact 6–7 px controls, and a 248 px desktop sidebar. Panels stack below 900 px; below 620 px the structure area precedes the controls. Keep long labels readable without horizontal overflow.

Use orthographic cameras and independent panel interaction by default. Fragment coloring affects carbon; other elements retain their identification colors. Preserve source-status labels and provenance. High-resolution exports are rendered again at the chosen resolution, not enlarged screenshots. Independently fitted panels are not on a common scale.
