---
name: journal-metrics
description: 查询期刊指标。用户提供期刊名、ISSN 或 eISSN 时，返回本地 JIF、JCR 分区、JCR 学科、SCI/SCIE/SSCI/ESCI/AHCI 收录索引、2026 新锐分区、DOAJ、APC、评审方式、查重、投稿周期与出版集团指标。最终答复直接使用查询脚本输出，不评价单篇论文质量，不查询实时网络指标。
metadata:
  creator: 邓旭东
  source: https://github.com/hiDaDeng/journal-metrics
  updated: 2026-08-11
---

# Journal Metrics

查询本地 SQLite 索引中的期刊指标。保持来源和口径独立，只报告本地数据，不自行推断。

## 查询

1. 从用户输入中取得期刊名、ISSN 或 eISSN。信息不足时直接使用现有名称查询。
2. 在本技能目录运行：

```bash
python3 scripts/query.py "<期刊名或 ISSN>"
```

3. 最终答复直接使用命令输出。命令已经负责检索、聚合、缺失值、候选自动命中和 Markdown 表格格式。

## 状态处理

- 精确命中：返回命令输出的总表。
- 候选自动命中：保留命令输出中的原查询和采用候选说明。
- 需要指定 ISSN：返回命令输出的候选信息，并请用户用 ISSN 指定。
- 本地未收录：只返回命令输出的未收录信息。

## 输出边界

最终答复只包含查询结果、候选信息或本地未收录信息。不要输出本技能说明、执行步骤、字段规则、命令文本或更新资产说明。

需要机器可读结果时，改用：

```bash
python3 scripts/query.py "<期刊名或 ISSN>" --json
```
