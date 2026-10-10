# 宏观指标字典

本文档定义宏观看板涉及的所有指标：含义、频率、单位、数据来源与解读口径。

更新日期：2026-10-09。待审分支的正式/演示及证据规则见[来源登记](source_catalog.json)；此字典不等于全部指标已采集或逐项核验。

> **配色约定（全看板统一）**：中国市场惯例 —— **红色 = 上涨/利好/走高**，**绿色 = 下跌/利空/走低**。

---

## 一、国内宏观指标（数据源：东方财富数据中心）

东方财富接口：`https://datacenter-web.eastmoney.com/api/data/v1/get`
必须携带 header：`Referer: https://data.eastmoney.com/`

| 指标 | reportName | 关键字段 | 频率 | 单位 | 解读口径 |
|---|---|---|---|---|---|
| GDP | `RPT_ECONOMY_GDP` | `DOMESTICL_PRODUCT_BASE`（总量）、`SUM_SAME`（同比） | 季 | 亿元 / % | 同比增速是核心，看趋势与市场预期差 |
| CPI | `RPT_ECONOMY_CPI` | `NATIONAL_SAME`（全国同比）、`NATIONAL_SEQUENTIAL`（环比） | 月 | % | >3% 通胀压力，<0 通缩风险 |
| PPI | `RPT_ECONOMY_PPI` | `BASE_SAME`（同比）、`BASE_ACCUMULATE`（累计） | 月 | % | PPI 领先企业盈利；PPI-CPI 剪刀差定利润分配 |
| PMI（制造业） | `RPT_ECONOMY_PMI` | `MAKE_INDEX` | 月 | 指数 | 50 为荣枯线，>50 扩张 |
| PMI（非制造业） | `RPT_ECONOMY_PMI` | `NMAKE_INDEX` | 月 | 指数 | 同上 |
| 社会消费品零售总额 | `RPT_ECONOMY_TOTAL_RETAIL` | `RETAIL_TOTAL`（总额）、`RETAIL_TOTAL_SAME`（同比） | 月 | 亿元 / % | 反映内需消费强弱 |
| 货币供应 | `RPT_ECONOMY_CURRENCY_SUPPLY` | `BASIC_CURRENCY`(M0)、`CURRENCY`(M1)、`FREE_CASH`(M2) 及各 `_SAME` 同比 | 月 | 亿元 / % | **M1-M2 剪刀差**是信用/实体活力核心指标 |
| 房价指数 | `RPT_ECONOMY_HOUSE_PRICE` | `CITY`、`FIRST_COMHOUSE_SAME`（新房同比） | 月 | 指数 | 反映地产周期与居民资产负债表 |

**待补指标**（正式数据缺项留空，不能使用演示兜底）：
- 社会融资规模存量及同比；增量及部分融资分项已接入待审信用模块，见[信用说明](credit_transmission.md)
- 工业增加值同比
- 固定资产投资完成额同比
- 中国 10Y 国债收益率

> 注：数据以「按月/季」为频率，最新一期通常有发布滞后（CPI/PPI 次月 9 日左右，社融次月中旬）。

---

## 二、海外宏观指标（数据源：FRED CSV）

FRED 接口（无需 API key）：`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES_ID>`

| 指标 | FRED Series ID | 频率 | 单位 | 解读口径 |
|---|---|---|---|---|
| 美国CPI（指数） | `CPIAUCSL` | 月 | 指数 | 计算同比即美国通胀 |
| 美国失业率 | `UNRATE` | 月 | % | 就业是美联储政策锚 |
| 联邦基金利率 | `FEDFUNDS` | 月 | % | 全球流动性总闸门 |
| 10Y 美债收益率 | `DGS10` | 日 | % | 全球资产定价锚，影响 A 股估值 |
| 美元兑人民币 | `DEXCHUS` | 日 | 汇率 | 人民币贬值→外资流出压力 |
| 美元指数（广义） | `DTWEXBGS` | 日 | 指数 | 美元强弱影响新兴市场 |
| WTI 原油 | `DCOILWTICO` | 日 | 美元/桶 | 输入型通胀、周期品盈利 |
| **中国3月期银行间利率** | `IR3TIB01CNM156N` | 月 | % | 中国货币松紧代理（P1） |
| **铜价（全球）** | `PCOPPUSDM` | 月 | 美元/吨 | 增长预期（P1） |
| **金价** | `IQ12260` | 月 | 指数 | 避险情绪（P1），铜金比分母 |
| **10Y美债实际利率** | `DFII10` | 日 | % | 真实融资成本（P1，TIPS） |
| **VIX 恐慌指数** | `VIXCLS` | 日 | 指数 | 风险偏好（P1） |
| **美债10Y-2Y利差** | `T10Y2Y` | 日 | % | 衰倒挂=衰退信号（P1） |

**派生指标**（fetch_fred.py 内按日期对齐计算）：
- **铜金比** = 铜价 / 金价 —— 上行=增长预期改善（顺周期）
- **中美利差** = 中国3月期利率 − 联邦基金利率 —— 负值走阔=外资流出压力

---

## 三、指标选取原则

1. **增长维度**：GDP、PMI（制造业+非制造业）、社零、工业增加值
2. **通胀维度**：CPI、PPI、PPI-CPI 剪刀差
3. **流动性维度**：M1、M2、M1-M2 剪刀差、社融
4. **信用维度**：社融增速、企业中长贷
5. **汇率/外部维度**：美元兑人民币、美元指数、美债收益率、原油

---

## 四、数据质量与降级策略

| 优先级 | 来源 | 触发条件 |
|---|---|---|
| 1 | 实时接口抓取（东财 / FRED） | 网络可用 |
| 2 | 用户手动提供（CSV/Excel/粘贴） | 用户有自有数据 |
| 3 | 原创模拟教学序列 | 仅显式 `--demo`，与正式数据分开；旧快照需另用 `--demo-snapshot` 指定并核对权利 |

部分真实输入标为数据不完整；全部无有效输入时失败。演示标为示例数据，不把失败视为读取样本的授权。CSV/Excel 等需先转换为脚本 JSON 结构，尚无通用导入器。
