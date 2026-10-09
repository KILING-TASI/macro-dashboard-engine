---
name: macro-dashboard
description: 宏观看板生成器 - 抓取国内外重要宏观数据（东方财富+FRED），通过 ECharts 单文件 HTML 看板可视化，进行美林时钟/库存周期/信用周期/长周期（朱格拉/库兹涅茨/债务/康波）研判，并输出宏观因子→股市传导链路与配置建议。触发词：宏观看板、宏观研判、美林时钟、周期定位、康波、朱格拉、宏观报告、股市场配置。
metadata:
  version: "1.3.0"
  author: "CodeBuddy AI"
  created: "2026-10-09"
---

# 宏观看板（Macro Dashboard）

抓取国内外宏观实时数据 → 周期研判（美林时钟 + 库存 + 信用）→ 生成**自包含单文件 HTML 看板**（内联 ECharts，浏览器直接打开）。

## 何时触发

- 用户要求"宏观看板 / 宏观数据可视化 / 宏观周期研判"
- 用户提到"美林时钟 / 库存周期 / 信用周期 / 宏观传导 / 资产配置看板"
- 用户想看国内外核心宏观指标（GDP/CPI/PPI/PMI/社融/M2/美债/美联储…）的可视化汇总

## 快速开始

一条命令生成完整看板：

```bash
python3 <skill-directory>/scripts/run_pipeline.py --out /workspace/macro-dashboard.html
```

成功后用 present_files 打开 `/workspace/macro-dashboard.html`。

> `<skill-directory>` 指本 Skill 所在目录（即本 SKILL.md 的上级目录）。

## 完整工作流

### 1. 确认需求（可跳过，有合理默认值）

- 关注模块：默认全部（周期研判 + 国内 + 海外 + 传导配置）
- 时间范围：默认近 36 个月（海外日线 60 期）
- 若用户提供了 CSV/Excel 宏观数据 → 解析为 `eastmoney_data.json` 兼容格式再走流水线（见下方"自定义数据"）

### 2. 生成看板

```bash
python3 <skill-directory>/scripts/run_pipeline.py --out /workspace/macro-dashboard-$(date +%Y%m%d).html
```

流水线自动执行：抓取东财（9 项国内指标）→ 抓取 FRED（7 项海外指标）→ 周期研判 → 生成 HTML。

### 3. 分步执行（需要自定义或调试时）

```bash
cd /tmp/macro
# ① 抓取
python3 <skill-directory>/scripts/fetch_eastmoney.py --out eastmoney_data.json
python3 <skill-directory>/scripts/fetch_fred.py --out fred_data.json
# ② 研判（短周期 + 长周期梯队）
python3 <skill-directory>/scripts/compute_cycle.py --eastmoney eastmoney_data.json --fred fred_data.json --out cycle.json
python3 <skill-directory>/scripts/compute_long_cycle.py --fred fred_data.json --out long_cycle.json
# ③ 出板
python3 <skill-directory>/scripts/build_dashboard.py --eastmoney eastmoney_data.json --fred fred_data.json --cycle cycle.json --longcycle long_cycle.json --out /workspace/macro-dashboard.html
```

### 4. 向用户汇报研判结论

看板生成后，除 present_files 外，**必须在回复中总结**（读 cycle.json / long_cycle.json 或从流水线 stdout 提取）：
- 美林时钟当前象限（复苏/过热/滞胀/衰退）与判定依据
- 库存周期、信用周期状态
- 长周期梯队：朱格拉（7-11年）、库兹涅茨（15-25年）、债务周期阶段 + 康波定性定位
- 配置建议（风格/板块/逻辑链）

## 降级与容错

| 场景 | 行为 |
|---|---|
| 东财接口失败 | FRED 正常 → 海外正常出图，国内用 `assets/sample_data.json` 兜底并标注 |
| FRED 接口失败 | 东财正常 → 国内正常出图，海外兜底并标注 |
| 全部失败 / 无网络 | 全部用离线快照生成看板，顶部显示「示例数据」角标 |
| 某指标缺失 | 对应图表留空或用近似指标（如 M1-M2 剪刀差替代社融），研判注明降级口径 |

**注意**：FRED 请求**不能携带自定义 User-Agent**（会被拒绝导致超时），脚本已处理，勿改动 `fetch_fred.py` 的 `HEADERS = {}`。

东财接口需带 `Referer: https://data.eastmoney.com/`，已内置。

## 自定义数据接入

用户有自有数据（CSV/Excel/粘贴）时，构造与 `fetch_eastmoney.py` 输出同构的 JSON：

```json
{"source": "user", "as_of": "2026-08",
 "indicators": {"cpi": {"name":"CPI同比","unit":"%","dates":["2026-07","2026-08"],
                         "series":{"value":[0.5,0.8]},"latest":0.8,"prev":0.5}}}
```

然后 `compute_cycle.py --eastmoney 自定义.json` 走正常流程。指标 schema 见 `references/indicators.md`。

## 定时自动化

配合自动化任务，可生成周度/月度宏观看板：

```bash
# 每周一 08:30 生成最新看板
python3 <skill-directory>/scripts/run_pipeline.py --out /workspace/macro-dashboard-weekly.html
```

## 输出规范（看板内容）

1. **KPI 速览**：12 张指标卡（最新值 + 变化，红涨绿跌）
2. **周期研判**：美林时钟四象限散点 + 象限结论 + 判定依据；库存周期；信用周期；**货币/流动性周期、估值周期、铜金比周期、中美利差周期（P1）**
3. **多周期共振时间轴**：8 维度 × 24 个月热力图
4. **扩展周期图表（P1/P2）**：美元指数/实际利率、铜金比、中美利差、VIX/美债利差、地产、盈利代理
5. **长周期梯队（P3）**：朱格拉（设备投资 7-11 年带通分量+峰谷标注）、库兹涅茨（地产 15-25 年）、债务周期（Δ债务/GDP + 水平双轴）、康波六浪技术革命时间轴 + 康波/熊彼特定性定位（⚠ 明确标注非数据计算）
6. **传导与配置**：五条传导链路图（货币/信用/通胀/汇率/海外流动性）+ 因子×行业热力矩阵 + 配置建议卡（含 P1 周期修正与冲突抑制）
7. **国内宏观**：CPI/PPI、PMI、M1/M2+剪刀差、社零/GDP
8. **海外宏观**：联邦利率/10Y美债、汇率/美元指数、美国CPI/失业率、WTI
9. **数据明细表** + 风险提示脚注

研判方法论文档（判定规则、阈值、传导映射表）：
- `references/cycle_framework.md` — 美林时钟/库存/信用/流动性/估值/铜金比/利差周期判定规则
- `references/transmission.md` — 传导链方法论与敏感度矩阵
- `references/indicators.md` — 指标字典与数据源字段（含 P1/P2 新增序列）
- `references/long_wave.md` — 长周期方法论（带通滤波参数、阶段判定规则、康波定性框架与使用边界）
- `assets/long_wave.json` — 康波/熊彼特定性知识库（六次技术革命浪潮时间轴、当前相位）

## 长周期模块说明（P3）

- **数据驱动**（`compute_long_cycle.py`）：朱格拉/库兹涅茨用「重采样季度 → z-score → 去超长趋势 → 带通滤波(MA short − MA long) → 阶段判定（水平 z + 4 期斜率）→ 峰谷识别（含最小跨度约束）」。债务周期用**债务/GDP 同比变化**（勿用水平均值——单调上升无判别力）+ 银行信贷脉冲。
- **定性框架**（`assets/long_wave.json`）：康波/熊彼特无可靠量化序列，用六次技术革命浪潮时间轴做定性定位，看板中强制标注「定性判断，非数据计算」，与数据驱动结论严格区分。
- **历史验证**：朱格拉谷底 1989Q2（储贷危机）、2001Q1（互联网泡沫）、2007Q4（次贷危机）均与真实设备投资周期吻合；库兹涅茨谷底 1990Q2、2011Q3 对应两轮地产危机。

## 风险提示（回复中必须带上）

> 看板基于公开宏观数据的历史规律，周期框架为经验性方法论，不构成投资建议。
