# 宏观研究看板



把增长、物价、货币和银行信贷数据放在一张看板里，查看近期变化、来源和缺口，并对照行业的历史表现。

[![原创代码 MIT](https://img.shields.io/badge/%E5%8E%9F%E5%88%9B%E4%BB%A3%E7%A0%81-MIT-green)](LICENSE)

## 统一安装与启动

本轮源码版本为 `1.7.1`。统一安装入口需要 Python 3.10 或以上。在完整源码目录新建自己的 Python 环境，下面的 Windows 命令不需要激活脚本：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\macro-dashboard-engine.exe --help
.\.venv\Scripts\macro-dashboard-engine.exe demo --out-dir reports/demo --auto-name
```

九个仓库都用仓库名启动；在已激活的环境中可以直接输入工具名。Linux/macOS 使用 `.venv/bin/python` 和 `.venv/bin/macro-dashboard-engine`。教学结果写入当前工作目录；`--auto-name` 自动另选新名字，旧结果保留。不加该参数时，教学入口拒绝已有目录。`macro-dashboard-engine run --help` 查看原生参数，原来的命令继续兼容。其他专题可用 `macro-dashboard-engine script --help` 查看入口，以脚本名调用，不需要记住源码路径。pip 安装提供 CLI；作为 Skill 使用仍须保留完整源码及许可资源，不能只复制 SKILL.md。安装可能需要联网获取普通构建依赖；教学离线。下面保留原生入口及此前发行记录，本轮安装和版本以本节为准。


## 先试一下

需要 Python 3.8 或以上版本。教学演示只用 Python 标准库，无需联网，也不用安装其他研究仓库；图表库随源码提供。

下载或克隆当前 main 的完整源码，在仓库根目录打开终端。v1.7.0已发布，可从[发布页](https://github.com/KILING-TASI/macro-dashboard-engine/releases/tag/v1.7.0)下载[完整源码/Skill包](https://github.com/KILING-TASI/macro-dashboard-engine/releases/download/v1.7.0/macro-dashboard-engine-v1.7.0.zip)，解压后在`macro-dashboard`目录运行相同命令。下载后请用[SHA256SUMS](https://github.com/KILING-TASI/macro-dashboard-engine/releases/download/v1.7.0/SHA256SUMS)核对摘要。Windows运行：

```text
python scripts/demo_preview.py --out-dir local-data/public-demo
```

成功后打开 `local-data/public-demo/macro-demo.html`。同目录的 `demo-input.json` 和 `cycle.json` 保存了输入和计算结果，方便复查。**演示数值为原创模拟，不是当前经济数据。**

如果输出目录已经存在，把命令中的目录改成 `local-data/public-demo-2` 或其他新名字，原文件会保留。已安装 Windows Python 启动器但没有配置python命令时，可以把开头换成`py -3`。提示缺少模板、图表库或许可文件时，请重新解压完整源码包。

## 结果示例

![原创模拟数据生成的宏观看板](assets/preview/macro-demo.png)

这是此前实际生成的教学报告截图，保留了当时的日期和计算版本；当前结果以重新运行生成的报告为准。[截图与样本说明](assets/preview/README.md)。

看板可以按指标、来源和状态筛选，调整图表日期窗口，查看增长评分的贡献，并把当前展示内容和参数保存成JSON。窗口只改变显示范围，不重新计算周期判断。[交互说明](references/view_controls.md) · [实际交互截图](assets/preview/macro-controls.png)

## 能做什么，暂不支持什么

| 可以做 | 需要注意的边界 |
|---|---|
| 整理国内GDP、CPI、PPI、PMI、社零、货币和房价，以及海外利率、就业、汇率和大宗商品序列 | 配置有9项国内指标、27条FRED原始序列和2条派生序列；接口可能缺项，获取成功不等于官方原文已核验 |
| 查看增长、通胀、信用和其他周期代理的近期变化 | M1−M2剪刀差不能替代贷款需求；PPI/PMI不能替代真实库存，利率分位不能替代股票估值 |
| 查看LPR、新增贷款、社融分项及美国银行调查 | 当前自动取数配置9条信用序列；中国和美国分别观察，不互相补缺。[信用说明](references/credit_transmission.md) |
| 比较行业收益与宏观因素的历史关联，观察长周期分量 | 历史关联不是因果归因或收益预测；全样本滤波不能当作实时回测 |
| 保留来源、日期、未知值和计算依据 | 未取得历史发布/修订版本时，不声称数据在当时已知；尚未自动完成M1回溯、春节修正或官方交易日历核验 |

输入是取数脚本生成的JSON或相同结构的用户数据，没有通用CSV/Excel导入器。缺值不填零，不用教学样本或其他国家数据补缺。明确声明累计GDP、合并月份社零或未核验的M1跨断点比较时，程序会拒绝相应趋势计算；未声明的渠道字段仍需核对口径。

单位与计算细节见[指标字典](references/indicators.md)、[方法卡](references/macro_method_cards.md)和[周期规则](references/cycle_framework.md)。例如0.8表示0.8%，百分点差与百分比变化分开；FRED的CPIAUCSL季调指数同比不等于通常公布的未季调同比。

## 独立使用与其他仓库的关系

仓库名是`macro-dashboard-engine`，真实Skill名称是[SKILL.md](SKILL.md)中的`macro-dashboard`。Skill说明与Python命令行可以并用。源码根目录包含SKILL.md、scripts、references、assets和third_party；复制Skill时需保留这些资源的相对位置，不必重命名现有仓库或调用。

本仓以源码分发，不需要pip安装本项目或其他自家专业包。没有wheel/npm安装包；PDF、研报解析不是本包能力。Node仅用于开发检查，生成看板不需要Node。已验证独立目录和虚拟环境中的命令行运行，尚未验证自然语言Skill发现。

工作台可以接收[宏观接口1.0.0](references/macro_contract.md)的有限观测，但不是运行依赖。公司经营与综合研究判断留给工作台；本仓不替代其官方发布核验、资产窗口或原件解析，也不承担财报、基金全评价和公司事件库的职责。数据入口和各批次验收详情统一见[数据目录与契约说明](references/data_contract_inventory.md)。

其他已验证入口，在仓库根目录运行：

```text
# 离线教学，每次另建运行目录
python scripts/run_pipeline.py --demo --workdir local-data/demo

# 实例：通用情景与中国统计口径，输出目录须是新的
python scripts/run_scenarios.py --out-dir local-data/scenarios
python scripts/run_scenarios.py --suite cn --out-dir local-data/cn-scenarios

# 正式取数，需要网络和相应来源权限
python scripts/run_pipeline.py --workdir local-data/research
```

情景目录的`index.json`索引输入、手算预期、实际结果和方法版本。中国口径实例覆盖GDP当季/累计、社零合并期及M1断点，依据见[官方核验登记](references/examples/cn-definition-sources.json)。模拟通过不等于真实取数或统计口径全面认证。

已有真实输入可以生成新报告：

```text
python scripts/build_dashboard.py --eastmoney local-data/em.json --fred local-data/fr.json --out local-data/from-archive.html
```

直接生成入口请用新文件名；它与流水线的覆盖保护不同。流水线指定输出已存在时拒绝覆盖，只有显式`--overwrite`才在成功后替换；失败保留旧结果。可选输入与导出办法见[接口说明](references/macro_contract.md)。

## 当前源码与历史版本

截至2026-10-10，原[PR #1](https://github.com/KILING-TASI/macro-dashboard-engine/pull/1)已合并，默认main包含上述教学入口、数据质量修正、信用证据、情景实例和成功/失败提示。首次使用不需要切换到旧PR分支。

| 范围 | 当前状态 |
|---|---|
| 已集成main | 基线`04fdcdd`已包含修复、教学/情景及首页更新；不是未合补丁 |
| v1.7.0源码/Skill | 已发布，源码包与Skill元数据均为1.7.0；周期方法2.1.0、宏观接口1.0.0保持，历史快照不改 |
| GitHub Release / 安装版 | v1.7.0已发布，tag对应`5a4c1d5`，附件SHA256与独立验收包一致；此前无旧Release，旧版只提供源码 ZIP；本轮新增 Python wheel 工程，不提供 npm 包 |
| 历史源码包、截图和验收记录 | 按各自提交与方法版本保留，不覆盖；旧文件不保证含当前新增入口和校验 |

已发布ZIP固定于`5a4c1d5`，包内“候选”文字记录打包时状态；本次main文档更正不替换ZIP或标签。历史记录中的“待审”描述当时状态，不代表当前main状态。[变更记录](CHANGELOG.md) · [后续路线](ROADMAP.md) · [历史设计v1.4](docs/设计方案.md)

## 验证、许可和来源

当前已集成改动通过35项Python测试，并在Windows/Linux、Python3.8/3.12的CI中运行教学与情景检查。独立源码包验收核对过输入、结果、模块来源、许可和失败时旧文件保留；宿主仍有其他仓库，属于目录和进程隔离。此前真实归档复查范围为5个行业、33个月，不代表本次重新取得或逐点核验全部真实数据。

```text
python -m unittest discover -s tests -v
python scripts/check_repository.py --archive
node tests/test_dashboard_controls.js
```

CI和教学结果不证明预测有效；真实联网取数、历史可得版本、跨仓同样本联调、自然语言发现及新页面视觉并未全部验收。具体通过范围见[统一验收说明](references/data_contract_inventory.md)。

原创代码及有权授权的原创说明采用[MIT](LICENSE)，版权标注KILING-TASI并保留原contributors声明。ECharts、D3等第三方材料保留原许可；数据、公告和研报各有权利边界，代码MIT不授予它们的再分发权。[许可范围](LICENSE_SCOPE.md) · [第三方说明](THIRD_PARTY_NOTICES.md) · [使用边界](DISCLAIMER.md)

原发布机构与获取渠道分开登记；东方财富、FRED、新浪及商务部接口可访问，不等于所有用途获授权。来源和缺口见[来源登记](references/source_catalog.json)及[研究路由](references/research_routing.md)。旧第三方快照仅保留[显式本地复查入口](assets/SAMPLE_DATA_RIGHTS.md)，不随源码归档。
