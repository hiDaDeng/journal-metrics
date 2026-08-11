---
name: journal-metrics
description: 查询期刊指标。用户提供期刊名、ISSN 或 eISSN 时，汇总本地近三年 JIF、JCR 分区、JCR 学科、SCI/SCIE/SSCI/ESCI/AHCI 收录索引、2026 新锐分区等指标；也用于核对同名期刊、APC、评审方式、查重、投稿周期与集团目录排名。不要用于评价单篇论文质量或查询实时网络指标。
metadata:
  creator: 邓旭东
  source: https://github.com/hiDaDeng/journal-metrics
  updated: 2026-08-11
---

# Journal Metrics

从多个本地 SQLite 索引汇总期刊指标。保持来源和口径独立，不自行推断，不用一个来源补写另一个来源缺失的字段。

## 查询

1. 取得用户给出的期刊名、ISSN 或 eISSN。信息不足时直接使用现有名称，不要先追问。
2. 在本技能目录运行以下命令；默认使用结构化 JSON 供 agent 汇总：

```bash
python3 scripts/query.py "<期刊名或 ISSN>" --json
```

3. 按返回状态处理：
   - `found`：按下方格式回答。
   - `ambiguous`：列出候选期刊及 ISSN，请用户指定；不要擅自选择。
   - `not_found`：如果 `suggestions` 非空，默认自动采用候选第 1 条继续查询，并明确标注“候选自动命中”；只有在没有可用候选时，才回答“本地数据未收录”。

查询顺序固定为：

1. 查询 `journal-metrics.sqlite` 的 JCR 与新锐分区。
2. 同时查询 `doaj.sqlite`；JCR 已给出 ISSN 时只按 ISSN 合并，不进行标题兜底。
3. DOAJ 出版者是 Wiley 时再查询 `publishers/wiley.sqlite`；Frontiers 同理。DOAJ 未收录时，允许用集团数据库的精确名称或 ISSN 命中作为兜底。

## 输出

先给一个紧凑的概览总表，并把 JCR、新锐分区、DOAJ、出版集团信息都顺序放在同一个信息面板里。优先使用清爽、克制的文本布局，而不是返回 HTML 字符串。

如果结果来自候选自动命中，在正文开头先补两行说明：

- 原查询：...
- 采用候选第 1 条：...

### 概览

优先把最有辨识度和决策价值的信息放到首屏，用一个两列表呈现。默认使用英文标签与英文表头；`2026 新锐分区` 这一行保留中文名称与中文值：

| Field | Value |
|---|---|
| Journal | **...** 或可点击期刊链接 |
| ISSN | `...` |
| JIF | **...** |
| JCR Quartile | **...** |
| 2026 新锐分区 | ... · ... |
| Indexing | ... |
| JCR Categories | ... |
| Ranking | ... |

其中：

- `JIF` 与 `JCR 分区` 默认取近三年中最近一个非空值。
- `收录索引` 取近三年所有可直接识别的 `SCI`、`SCIE`、`SSCI`、`ESCI`、`AHCI` 的并集；不显示年份。
- `JCR 学科` 取近三年中最近一个更具体的非空学科值；如果最新年份只有 `Multiple` 这类泛化值，优先回退到最近一个更具体的年份，但输出中不显示年份。
- `排名` 取近三年中最近一个非空值；如果三年都没有，省略该行。
- `期刊` 这一行在本地数据存在可靠期刊页 URL 时，优先输出为可点击链接；保守 fallback 规则固定为：先用 `doaj.journal_url`，若无 DOAJ 再用出版集团目录中的期刊 URL。若本地库没有可靠 URL，不要自行拼接或猜测官网地址。
- 如果某项概览值缺失，在表格中写 `—`。
- `2026 新锐分区` 放在 `JCR 分区` 之后，不再单独拆表。

不要默认输出逐年 `JCR` 趋势表，除非用户明确要求按年份展开。

存在 `doaj` 时，继续给 DOAJ 表：

把 DOAJ 信息继续追加在同一个总表中，标签写成：

- `DOAJ · Publisher`
- `DOAJ · Country`
- `DOAJ · License`
- `DOAJ · License Since`
- `DOAJ · Author Holds Copyright`
- `DOAJ · APC`
- `DOAJ · Waiver Policy`
- `DOAJ · Other Fees`
- `DOAJ · Review Process`
- `DOAJ · Plagiarism Screening`
- `DOAJ · Submission to Publication`
- `DOAJ · Preservation Services`
- `DOAJ · DOI/PID`
- `DOAJ · Last Full Review`
- `DOAJ · Article Records`

默认保留以上字段。除非用户要求，否则不逐条展开 URL、编辑部链接、版权链接或作者指南链接。
如果该期刊未命中 DOAJ，不要额外输出“DOAJ 未收录”这类占位说明，直接省略整个区块。

存在 `publisher_metrics` 时继续给出版集团表：

把出版集团信息继续追加在同一个总表中，标签写成：

- `Publisher · Name`
- `Publisher · Directory Ranking`
- `Publisher · Submission to First Decision`
- `Publisher · Acceptance Rate`
- `Publisher · Submission to Acceptance`
- `Publisher · Acceptance to Online`
- `Publisher · OA Model`
- `Publisher · APC`
- `Publisher · Peer Review Model`
- `Publisher · Article Count`
- `Publisher · Article Views`
- `Publisher · Article Downloads`
- `Publisher · Directory IF`
- `Publisher · CiteScore`
- `Publisher · Observed At`

如果该期刊没有可用出版集团指标，不要额外输出“出版集团指标未收录”这类占位说明，直接省略整个区块。

## 字段规则

- “近三年”取索引库中最新三个 JCR 年份；当前资产为 2024–2026。
- JIF 是各年份来源表中的年度值，不是三年均值。不要擅自计算平均数。
- 概览中的聚合规则是“最近可用值优先，索引并集保留，学科优先选择最近的具体值”；不要自行计算平均数、百分位或跨来源推断。
- 同一年存在多个值、分区、索引或学科类别时全部保留，并提醒该期刊存在多条学科记录。
- 顶层 `not_found` 仍明确写“本地数据未收录”；表格单元格中的缺失值统一写 `—`。
- JCR 分区与 2026 新锐分区分开呈现，不做数值换算，不用其中一个补另一个。
- `索引` 只能来自近三年 JCR 记录中可直接识别的信息；不要用集团目录、常识或其他来源补写 SCI/SSCI。
- `排名` 与 `集团目录排名` 分开呈现，不得混为同一口径。
- 集团目录中的排名、IF、周期和 APC 只能标注为集团目录信息，不能补写到 JCR 年份表。
- DOAJ 的 `review_process` 原样概括为评审方式，例如 anonymous peer review、double blind peer review；不要自行改写成更具体但库中没有的结论。
- DOAJ 的 `plagiarism_screening` 原样映射为“是 / 否 / 本地数据未收录”。
- DOAJ 的 `submission_to_publication_weeks` 是投稿到发表，不是首次决定或投稿到录用。
- DOAJ 的 `article_records_in_doaj` 是 DOAJ 收录记录数，不是期刊累计或年度发文量。
- DOAJ 未命中不等于期刊不是开放获取；只表示本地 DOAJ 导出未收录。
- 混合期刊的 APC 是选择开放发表时的费用，不要表述成所有投稿都必须付费。
- 集团目录中的 `article_count_total` 是累计发文量，不是年度发文量；不得改称“年发文量”。
- `publisher_jif` 是集团目录当前展示值，单独标为“集团目录 IF”，不要用它补写某个 JCR 年份。
- DOAJ 与集团数据的 APC、周期或评审信息不一致时并列报告来源和口径，不擅自选择一个覆盖另一个。
- 审美上优先“首屏抓重点、信息同表、空值收敛”：优先用一个连续总表承载全部可用信息；标题层级清楚，强调重点指标；不要让输出看起来像普通数据表粘贴。
- 末尾不要再输出“注：”或“数据来源：”两类句子。
- 末尾统一保留一行英文收尾文案：
  `[hiDaDeng/journal-metrics](https://github.com/hiDaDeng/journal-metrics) Please re-check critical details before submission.`

## 更新资产

日常查询不读取 Excel。仅在源表更新时运行：

```bash
python3 scripts/build_index.py \
  "<JCR 多年度工作簿.xlsx>" \
  "<2026 新锐分区工作簿.xlsx>" \
  --output assets/journal-metrics.sqlite
```

构建脚本需要 `openpyxl`；查询脚本只使用 Python 标准库。两个来源写入同一数据库的两张独立表，原始工作簿无需拆分或合并。

DOAJ CSV 更新时，转换为独立的快速查询库：

```bash
python3 scripts/build_doaj.py \
  "assets/DOAJ_journalcsv_20260711_2320_utf8.csv" \
  --output assets/doaj.sqlite
```

构建脚本仅使用 Python 标准库，输出 `assets/doaj.sqlite`。正式查询不读取 CSV。

### 出版集团指标

集团数据库保存易变化的投稿与出版指标，和 JCR 数据库分离。

同时更新当前支持的全部集团：

```bash
python3 scripts/sync_publishers.py
```

任一来源失败时保留该来源原有数据库，并明确报告失败来源，不用空库覆盖旧数据。也可按下方命令单独更新。

同步 Wiley 的公开 Journal Finder 汇总数据：

```bash
python3 scripts/sync_wiley.py
```

输出为 `assets/publishers/wiley.sqlite`。该同步使用集团汇总入口，不逐刊访问 Wiley 页面；遇到 HTTP 限制立即停止，不规避访问控制。

同步 Frontiers 的公开期刊总目录：

```bash
python3 scripts/sync_frontiers.py
```

输出为 `assets/publishers/frontiers.sqlite`。该同步一次取得完整集团目录，不逐刊访问；当前可保存 ISSN、累计发文/浏览/下载量、目录展示的 IF 与 CiteScore。Frontiers 的 APC 因期刊和文章类型而异，集团目录未给出具体数值时保持空值。
