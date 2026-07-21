# SecureSQL Anchor — 数据来源与镜像清单（P0b）

镜像日期：2026-07-14（Asia/Shanghai）。全部文件为只读镜像，未做任何内容修改。

## 1. SecureSQL 官方数据（EMNLP 2024 Findings, CC BY 4.0）

论文：Song et al., "SecureSQL: Evaluating Data Leakage of Large Language Models as Natural Language Interfaces to Databases", Findings of EMNLP 2024.
https://aclanthology.org/2024.findings-emnlp.346/

| 文件 | 来源 URL | SHA256 |
|---|---|---|
| `securesql_data.zip` | https://aclanthology.org/attachments/2024.findings-emnlp.346.data.zip | `1c7751fd31b0518e8b9274a93d86e70dc760e590459608c93f7ca84068b3bcc0` |
| `securesql_software.zip` | https://aclanthology.org/attachments/2024.findings-emnlp.346.software.zip | `417de440593fdf11bf7bb23d50c3be42ad4b4fb0962f7a6befec28dcd64c827d` |

解包核验（`data_unzipped/data.json`）：932 例 / 57 库 / 146 条唯一 (db_id, security_condition)；
标签分布 SA=321, DI=220, SU=147, PR=126, RE=118 —— 与论文 Table 2 / Figure 2 完全一致。
questions 与 queries 等长；130 例多问题（RE=108）。

## 2. 数据库 schema（SecureSQL 标注基于 Spider + BIRD；官方 data.zip 不含数据库文件）

| 文件 | 覆盖 | 来源 URL | SHA256（见 SHA256SUMS） |
|---|---|---|---|
| `bird_train_tables.json` | BIRD train 69 库（本实验用 14 库） | 官方 https://bird-bench.oss-cn-beijing.aliyuncs.com/train.zip 内成员 `train/train_tables.json`（HTTP Range 远程抽取，脚本 `remote_zip_extract.py`） | `85300c745b263db88a5e0cdf083e8b2427d90272e954bc8c5f92aa1dc66c836b` |
| `bird_dev_tables.json` | BIRD dev 11 库（本实验用 3 库） | 官方 https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip 内成员 `dev_20240627/dev_tables.json` | `35e7f73f2bc3a3bc4def9466215f7617ff8b37e9b2837f03539a42c9e9c69d97` |
| `sscl_tables/task_{0..9}_tables.json` | Spider tables.json（含 train_others/yelp），10 片并集 162 库 | https://raw.githubusercontent.com/SEU-COIN/SSCL-Text2SQL/main/data/spider_task_stream/task_N/tables.json（Spider 官方 tables.json 的第三方 vendored 拷贝；HuggingFace 官方源本机不可达，如实记录） | 见 SHA256SUMS |
| `spider_union_tables.json` | 上行 10 片去重并集（脚本生成） | 本地生成 | 见 SHA256SUMS |
| `schemas_57.json` | 57 库最终 schema 束（`build_schema_bundle.py` 生成，来源择优：spider 39 / bird_dev 3(+formula_1 由 spider 覆盖) / bird_train 14） | 本地生成 | 见 SHA256SUMS |

Schema↔查询覆盖验证：57 库中 47 库 0 误差；10 库存在残留 mismatch，逐一核查后归为两类，均不修改数据：
1. 解析伪差：BIRD 列名含空格（如 `product.product name`），正则限定符只截到首词；
2. 数据集自带 typo（官方 data.json 原文如此）：`depratment/deparment`(id160,178-180)、`from from`(id362)、
   `employees`(id339)、`organisation`(id41,42)、`productid` 作表名(id920)、`review` 表缺失(id789)、
   `people.id`(id228,230)、`scores`(id99)、`user.city/locationid`(id478)、`projects.outcome_code`(id72)。

## 3. 废弃候选（留档以示检索路径，不参与实验）

- `solar_tables.json`（shravani-01/SOLAR-NLP）：退化格式，CREATE TABLE 无列名，弃用。
- `linkalign_domain_tables.json`（Satissss/LinkAlign）：每表仅 1 列的 schema-linking 子集，弃用。
- `sscl_task8_tables.json`：已被 `sscl_tables/` 全集取代。
- `cloudera_spiderman_tables.json` / `spider_tables_candidate.json` / `spider_full_tables.json`：格式不符或 404 残留。

## 4. 许可

SecureSQL：CC BY 4.0（ACL Anthology attachment）。Spider：CC BY-SA 4.0。BIRD：CC BY-SA 4.0。
本目录仅作科研评测镜像，注明出处。
