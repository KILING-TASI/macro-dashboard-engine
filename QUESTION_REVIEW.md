# 问题导向的证据复查

本专题借鉴公开网站的流程组织方式，代码与教学数据由本仓原创实现，没有复制对方源码、报告或数据。先看资料能支持什么，再看计算与缺口；不把网页能打开或程序退出成功当成原文已核验。

## 单仓最短流程

安装本仓即可运行，不要求作者缓存、其他仓库、付费终端或网络取数。示例是原创教学资料。

```text
pip install .
macro-dashboard-engine script industry_evidence_review review --input examples/expansion-teaching/industry-evidence-teaching.json --out-dir reports/question-review
```

输出新目录中的 `report.html`、`input.json`、`result.json` 和 `receipt.json`。先读结论和缺口，再展开底稿。换资料或假设时另用新目录，历史结果不覆盖。输入字段见示例；示例链接与哈希为教学占位，不能冒充真实证据。

价格、产能、开工率和库存分别展示；同单位、范围、来源版本的前期基准才计算差值。教学库存未知，所以四类证据不齐；不合成为确定景气或盈利预测。新增数据采集归数据仓，ETF只消费经核对的特征。

## 真实研究与验收边界

教学只验收流程和边界，不作为真实研究案例或准确率证据。实际研究须填入有权使用的原始来源、期间、单位和版本，按报告提示复核原文与缺失项。第三方代码、公告、研报和数据仍按各自权利范围处理。
