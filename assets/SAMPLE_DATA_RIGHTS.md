# 既有历史快照的权利状态

`sample_data.json` 原样保留以便既有研究复查，其备注指向东方财富与 FRED 历史快照。该数据不是本次原创模拟输入；未取得逐序列再分发授权，不由根 MIT 许可覆盖。

默认 `--demo` 已改用原创模拟数据；源码归档通过 `.gitattributes` 排除这个快照。需要本地复现旧演示且已核对数据用途与权利时，显式指定：

```text
python scripts/run_pipeline.py --demo --demo-snapshot assets/sample_data.json --workdir local-data/legacy-demo
```

源码 ZIP 不包含该文件。用户可提供同构的、自己有权使用的快照路径；上述参数不授予数据权利，也不支持将教学结果冒充真实取数。没有删除历史数值或证据链接，未逐项认证的范围见[许可清单](../LICENSE_SCOPE.md)。
