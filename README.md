# journal-metrics

[English](./README-EN.md) | [中文](./README.md)

`journal-metrics` 是一个面向智能体的本地期刊查询技能。它通过打包的 SQLite 索引返回干净、紧凑、来源边界清楚的总表，覆盖 JIF、JCR 分区、收录索引、DOAJ 信息，以及部分出版集团投稿指标，不自行补写缺失值。

![](img/journal-metrics.svg)

## 特性

- 通过一个入口查询多个本地 SQLite 索引。
- 返回一个紧凑总表，优先展示最影响选刊判断的字段。
- 保持不同来源的边界，不用猜测补齐缺失字段。

## 安装

在 agent 对话框（Codex/ZCode/Claude Code/OpenCode/Kimi Code 等）中执行命令：

```text
请帮我安装  hiDaDeng/journal-metrics
GitHub: https://github.com/hiDaDeng/journal-metrics
```

如果想在终端安装，执行：

```
npx skills add hiDaDeng/journal-metrics
```

## 使用

在智能体对话中，常见调用方式如下：

```text
$journal-metrics Marketing Science
```
Run
```
**Overview**

|     Field    |       Value       |
|--------------|-------------------|
|   Journal    |MARKETING SCIENCE  |
|    ISSN      |0732-2399/1526-548X|
|     JIF      |       5.2         |
| JCR Quartile |        Q2         |
| 2026新锐分区  |    1 区 · 管理学    |
|  Indexing    |       SSCI        |
|JCR Categories|     BUSINESS      |

[hiDaDeng/journal-metrics] Please re-check critical details before submission.
```

## 项目结构

```text
journal-metrics/
├── SKILL.md
├── agents/openai.yaml
├── scripts/
└── assets/
    ├── journal-metrics.sqlite
    ├── doaj.sqlite
```

## 文件说明

- `SKILL.md`  
  技能主说明，定义智能体的执行规则。

- `agents/openai.yaml`  
  界面名称、简介与默认提示词等元数据。

- `scripts/query.py`  
  主查询入口，负责检索、聚合与输出格式化。

- `scripts/build_index.py`  
  用本地 JCR 工作簿和 2026 新锐分区工作簿构建 `journal-metrics.sqlite`。

- `scripts`  
  技能执行时需要用到的相关代码脚本。

- `assets/journal-metrics.sqlite`  
  主查询库，来源于本地整理后的 JCR 与新锐分区源表。

- `assets/doaj.sqlite`  
  由 DOAJ CSV 快照构建的快速查询库。

## 说明

- 仓库仍在建设中。
- 投稿前请再次核对关键信息。
