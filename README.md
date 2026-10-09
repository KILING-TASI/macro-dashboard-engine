# Macrodashboard Engine

说明版本：1.3 · 更新日期：2026-10-09

抓取国内外重要宏观数据（东方财富 + FRED），生成**自包含单文件 HTML 看板**，并给出宏观周期研判与宏观→股市传导配置建议。

## 能力范围

看板覆盖「短—中—长」三层周期梯队：

| 层级 | 周期 | 时间尺度 | 主导变量 |
|---|---|---|---|
| 战术层 | 美林时钟、库存周期、信用周期、货币流动性、估值、铜金比、中美利差、盈利、情绪、地产 | 3 个月 ~ 4 年 | 增长 / 通胀 / 信用 / 流动性 |
| 战略层 | **朱格拉周期**、**库兹涅茨周期**、**债务周期** | 7 ~ 25 年 | 设备投资 / 地产 / 债务 |
| 背景层 | **康波周期**、**熊彼特创新周期**（定性框架） | 50 ~ 60 年 | 技术革命集群 |

并输出 **宏观因子 → 股市传导链路**（货币 / 信用 / 通胀 / 汇率 / 海外流动性五条主链）与 **因子 × 行业敏感度矩阵**及配置建议。

## 快速开始

一条命令生成完整看板：

```bash
python3 scripts/run_pipeline.py --out /workspace/macro-dashboard.html
```

成功后用浏览器打开 `macro-dashboard.html`（内联 ECharts，无需联网、无需服务器）。

### 分步执行

```bash
cd /tmp/macro
# ① 抓取
python3 <skill>/scripts/fetch_eastmoney.py --out eastmoney_data.json
python3 <skill>/scripts/fetch_fred.py --out fred_data.json
# ② 研判（短周期 + 长周期梯队）
python3 <skill>/scripts/compute_cycle.py --eastmoney eastmoney_data.json --fred fred_data.json --out cycle.json
python3 <skill>/scripts/compute_long_cycle.py --fred fred_data.json --out long_cycle.json
# ③ 出板
python3 <skill>/scripts/build_dashboard.py --eastmoney eastmoney_data.json --fred fred_data.json \
  --cycle cycle.json --longcycle long_cycle.json --out /workspace/macro-dashboard.html
```

## 数据源

- **东方财富**（`datacenter-web.eastmoney.com`）：国内 9 项指标 — GDP / CPI / PPI / PMI / 社零 / M0 / M1 / M2 / 70 城房价
- **FRED**（`fred.stlouisfed.org`）：海外 18 项 + 12 条长周期全历史序列（设备投资、固定资产投资、新屋开工、Case-Shiller 房价、债务/GDP、银行信贷等，最早回溯至 1919 年）

> ⚠️ **关键约束**：FRED 请求**不能携带自定义 User-Agent**（会被拒绝导致超时），脚本内 `HEADERS = {}` 请勿改动。东财接口需带 `Referer: https://data.eastmoney.com/`。

## 降级与容错

三级兜底，保证看板永远能出图：

1. **实时抓取**（东财 + FRED）
2. **用户自定义数据**（构造同构 JSON 传入）
3. **离线快照**（`assets/sample_data.json`，顶部标注「示例数据」角标）

## 目录结构

```
├── SKILL.md                  # Skill 主文档（触发条件 / 工作流 / 输出规范）
├── README.md                 # 本文件
├── LICENSE
├── assets/
│   ├── template.html         # 单文件看板模板（22 张 ECharts 图表）
│   ├── echarts.min.js        # 内联用 ECharts 5.5.1
│   ├── long_wave.json        # 康波 / 熊彼特定性知识库
│   └── sample_data.json      # 离线兜底快照
├── scripts/
│   ├── run_pipeline.py       # 一键编排
│   ├── fetch_eastmoney.py    # 国内数据连接器
│   ├── fetch_fred.py         # 海外数据连接器（含长周期序列）
│   ├── compute_cycle.py      # 短周期研判引擎（10 个周期）
│   ├── compute_long_cycle.py # 长周期引擎（朱格拉/库兹涅茨/债务）
│   └── build_dashboard.py    # 看板组装器
└── references/
    ├── cycle_framework.md    # 短周期判定规则
    ├── long_wave.md          # 长周期方法论（带通滤波参数、康波框架）
    ├── transmission.md       # 传导链方法论与敏感度矩阵
    └── indicators.md         # 指标字典与数据源字段
```

## 方法论要点

- **周期阶段判定**：用「水平 z-score + 方向斜率」融合，避免只看绝对值造成的误判（如 PMI 低位改善被误判为衰退）。
- **长周期提取**：重采样季度 → z-score → 去超长趋势 → 带通滤波 `MA(short) − MA(long)` → 峰谷识别（含最小跨度约束）。朱格拉谷底 1989Q2（储贷危机）、2001Q1（互联网泡沫）、2007Q4（次贷危机）与真实设备投资周期吻合。
- **债务周期**：用债务/GDP 的**同比变化**而非水平值（水平单调上升无判别力）+ 银行信贷脉冲。
- **康波/熊彼特**：无可靠高频量化序列，采用六次技术革命浪潮时间轴做**定性定位**，看板中强制标注「定性判断，非数据计算」。

## 风险提示

看板基于公开宏观数据的历史规律，周期框架为经验性方法论，**不构成投资建议**。

## 免责声明

本项目仅供学习与研究，不构成投资建议或交易指令，不保证收益或结果准确性。请在使用前阅读[免责声明与使用边界](DISCLAIMER.md)，并结合本次数据来源、假设与缺口独立判断。代码许可不包含第三方数据使用授权。
