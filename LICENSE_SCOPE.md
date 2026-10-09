# 许可范围清单

核对日期：2026-10-10。根 [LICENSE](LICENSE) 采用标准 MIT 文本，版权标注 KILING-TASI，同时保留已有 `macro-dashboard-engine contributors` 声明；第三方版权及许可原样保留。

| 材料 | 许可范围及核对状态 |
|---|---|
| 原创 Python、工作流、HTML/CSS/JS 及有权授权的原创说明 | 按现有 MIT；其中第三方库、引文及外部资料单独处理 |
| `assets/dashboard_controls.js` | 本次原创显示逻辑，按现有 MIT；导出的展示数据仍保留各自数据权利，不变成 MIT 数据 |
| `assets/echarts.min.js` | Apache ECharts 5.5.1，统一换行后与上游分发文件一致；Apache-2.0、D3 BSD-3-Clause 及内嵌 Microsoft 声明原样保留，不改为 MIT |
| `scripts/teaching_data.py` 和原创模拟输入 | 本次原创、无外部观测；按项目 MIT。模拟数值没有现实经济含义 |
| `assets/preview/macro-demo.png` | 实际生成的教学界面；数值原创。截图不把 ECharts、字体或商标的权利整体转授为 MIT；无外部照片、账户或原文全文 |
| 字体 | CSS 仅引用本机系统字体，没有字体文件随源码分发；字体名称和显示效果不等于字体软件授权 |
| `assets/sample_data.json` | 既有第三方历史快照，逐序列来源和再分发许可未认证，明确排除 MIT；不再作默认演示，Git 源码归档排除，保留显式本地复现入口 |
| `assets/long_wave.json`、`assets/policy_calendar.json` 及方法资料 | 原创编排部分适用 MIT；理论、事件事实、引用及原始资料权利随原来源，未逐项认证。不能由本清单推断全部内容已获再授权 |
| 联网取得的数据、公告、研报及用户输入 | 不由项目 MIT 授权，不随源码归档；按原权利人、来源条款及用户权限处理 |

## 分发与生成结果

ECharts 上游许可及通知保存在 `third_party/echarts-5.5.1/`，校对 URL、版本及哈希见该目录的 `provenance.json`。生成的单文件 HTML 内嵌项目 LICENSE、ECharts LICENSE/NOTICE 和 D3 许可，保留库文件原版权声明；HTML 中的外部数据仍不变成 MIT 数据。

本仓库没有 pyproject、npm 包元数据或已发布安装包；不为统一许可新建虚假的发布元数据。源码归档检查确认声明和必要资源已收录，未附研究缓存、账户记录、PDF 原文、商业表格或字体文件。此清单是可核范围，不是全部材料权利认证。

## 数据渠道

FRED 的[使用条款](https://fred.stlouisfed.org/legal/)区分具体序列的版权与用途；下载免费不等于可任意缓存、商业展示或再分发。没有逐序列核准的历史快照因此排除默认演示和源码归档。东方财富、新浪及商务部接口目前没有取得涵盖本项目再分发的明确授权记录；保留来源链接，不把接口可访问视为许可。

个人研究取数与公开发布是不同用途，实际使用前需核对当时来源条款及具体序列。既有连接器不等于本项目代用户取得授权，也不保证所有用途允许。
