# 宏观研究看板

观察增长、物价、货币和信贷变化，并对照行业价格、产能、开工率与库存证据。

[![原创代码 MIT](https://img.shields.io/badge/原创代码-MIT-green)](LICENSE) · [当前发行版 v1.7.7](https://github.com/KILING-TASI/macro-dashboard-engine/releases/tag/v1.7.7) · [运行检查](https://github.com/KILING-TASI/macro-dashboard-engine/actions)

## 能解决什么问题

**增长、物价和信贷有哪些变化？行业四类证据齐了吗？**

独立维护宏观和行业指标解释；新增数据采集与资料储备归数据仓，ETF可以消费已核特征。

## 快速开始

从[发行页](https://github.com/KILING-TASI/macro-dashboard-engine/releases/tag/v1.7.7)下载完整源码并解压，需要 Python 3.10 或以上。在源码目录执行：

```text
python try_demo.py --no-open --out-dir reports/first-demo
```

按提示打开新生成的 HTML。Windows 也可双击 `Start-Demo.cmd`，Linux/macOS 可用 `sh Start-Demo.sh`。教学使用原创模拟资料，不自动取真实数据；重复运行使用新目录，历史结果保留。

![已保存的报告示例](assets/preview/macro-demo.png)

图片是历史示例，不能推定全部新报告已完成视觉验收。

## 使用自己的资料

先按[资料准备](BEGINNER.md)填写输入，再看[详细命令与方法](USAGE.md)。需要安装CLI时，在自己的Python环境运行：

```text
python -m pip install .
macro-dashboard-engine --help
```

仓库、Python发行包、安装命令及Skill注册名均为 `macro-dashboard-engine`。CLI安装和Skill注册是两个步骤：自然语言调用按[SKILL.md](SKILL.md)配置，保留完整资源；不必安装全部仓库。安装普通构建依赖可能联网，教学流程不需要作者缓存。

## 结果范围

同期表现不直接解释为因果；行业证据不自动合成为盈利预测，尚未取得全部31行业真实数据。

报告中的来源、日期、假设和未知事项需一起阅读。程序运行成功不等于来源已经认证、资料完整或投资判断有效。原创代码采用MIT，第三方代码、公告、研报和数据仍按各自权利范围处理。

## 文档与维护

- [详细命令与方法](USAGE.md)
- [资料准备与排错](BEGINNER.md)
- [Skill调用指引](SKILL.md)
- [版本记录](CHANGELOG.md)
- [许可与第三方范围](THIRD_PARTY_NOTICES.md)
- [问题与证据复查](QUESTION_REVIEW.md)
- [审计范围](AUDIT_SCOPE.md)

[贡献说明](CONTRIBUTING.md) · [安全反馈](SECURITY.md) · [更新与清理](LIFECYCLE.md) · [English](README.en.md)

[按问题选择其他工具](https://github.com/KILING-TASI/research-workbench/blob/main/references/tool-navigation.md)。共12个活跃仓，资料契约校验已并入[数据仓](https://github.com/KILING-TASI/cn-data-adapters/blob/main/CONTRACT_MIGRATION.md)。各仓分别发布；main的后续文档整理不改写旧发行包和冻结结果。

## 安装与结果状态

可单独安装本仓，无需工作台。生成报告表示本流程已运行，不表示资料完整或原文已经认证；来源、口径和缺口按报告说明复查。命令行安装与助手Skill注册是两个步骤。
