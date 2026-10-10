# 货币与银行信用传导

观察顺序：资金价格 → 银行信用供给 → 借款需求 → 融资结构 → 现金流压力。
本模块分别展示观测，不将不同地区、不同频率拼成一个评分，不据此生成配置建议。

## 已接入

- 商务部商务数据中心转载的社融月度增量、人民币贷款、企业债券、股票融资，亿元。保留实际截止月；政府债分项未提供，不用总量减已知项的残差推算。
- 东方财富新增人民币贷款，金融机构口径，与社融人民币贷款覆盖范围不同。
- 东方财富LPR（1年、5年期以上），贷款报价参考，不作为DR007或实际贷款利率。
- FRED DRTSCILM / DRSDCILM，美国大中型企业贷款标准收紧/需求增强的银行净占比，季度、未季调。保留FRED季度标签，不推断为中国需求，也不把季度标签当精确公布日。

抓取保留原始响应、获取时间和序列来源。月度滞后超过3个月、季度超过6个月标为滞后；此阈值为展示规则，不是经济判断。零和负增量均有效，缺值不补零。

## 缺口与扩展输入

当前没有自动接入DR007、国内需求/审批调查、居民/企业中长期贷款、政府债净融资、社融存量同比、应收账款回收期。页面逐项列示缺口。
`build_dashboard.py --credit credit_data.json` 可接受已核验的补充数据；不自动猜测字段。
结构为 `indicators[key]`，包含 `name`、`unit`、`source_url`、`frequency` (D/M/Q)、`dates` 和 `values`。
扩展key为 dr007、cn_demand、cn_approval、household_long、corporate_long、government_bonds、afre_stock_yoy、receivable_days。
中长期贷款输入必须为月度增量，累计数据不能直接当月度值；季度调查不插值。

缺完整融资分项与同期名义GDP时不计算信用脉冲。2025年1月M1口径变化须先核验可比历史口径，原信用代理仍需谨慎使用。

## 阅读参考

- 英格兰银行，Money Creation in the Modern Economy：https://www.bankofengland.co.uk/quarterly-bulletin/2014/q1/money-creation-in-the-modern-economy
- Borio，The Financial Cycle and Macroeconomics：https://www.bis.org/publ/work395.pdf
- Minsky，The Financial Instability Hypothesis：https://www.levyinstitute.org/publications/the-financial-instability-hypothesis/
- Huerta de Soto，Money, Bank Credit, and Economic Cycles：https://mises.org/library/book/money-bank-credit-and-economic-cycles

理论视角用于组织可检验假设，不把学派主张作为周期识别准确性的证据。
