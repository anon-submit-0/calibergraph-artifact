# P0b 结果报告：SecureSQL ⑤族（refusal/disclosure）公认锚评测

日期：2026-07-14（Asia/Shanghai）
协议：`protocol.md` v1.0 + Amendment 1（跑前语义一致化）+ Amendment 2（transport-only 换渠道）；
指纹链见 `frozen_protocol.sha256`（预注册先于全部评测调用写盘）。
铁律执行情况：全程无 mock；每个预测可溯源至 `raw/` 原始响应或 `checker.py` 确定性规则触发记录；密钥仅运行时读 `~/.config/llm_keys.env`，未落盘。

---

## 1. 数据来源（镜像+校验见 `data/SOURCES.md`、`data/SHA256SUMS`）

- **SecureSQL 官方数据**（EMNLP 2024 Findings, CC BY 4.0）：ACL Anthology 官方 attachment
  `https://aclanthology.org/attachments/2024.findings-emnlp.346.data.zip`
  SHA256 `1c7751fd31b0518e8b9274a93d86e70dc760e590459608c93f7ca84068b3bcc0`。
  核验：932 例 / 57 库 / 146 条唯一 (db, security_condition)；SA321/DI220/SU147/PR126/RE118 —— 与论文完全一致。
- **Schema**：Spider tables.json（第三方 vendored 并集 162 库，HF 官方源本机不可达）+ BIRD 官方 OSS
  train.zip/dev.zip 内 tables.json（HTTP Range 远程抽取，脚本 `data/remote_zip_extract.py`）。57/57 库覆盖。
- **官方金标语义纠正（重要）**：论文 Table 1 + SAFENLIDB 官方评分脚本确认
  **SA/SU=safe（must-answer，468 例），DI/PR/RE=unsafe（must-refuse，464 例）**；
  任务书原假设"SU→must-refuse"与官方语义相反，已在协议冻结阶段按官方纠正。

## 2. 预注册分支判定：**(c) 可编译边界**（跑前冻结判据：全量 932 一致率 <0.80）

**臂 A（CaliberGraph 政策编译判定，全量 932 原始例）一致率 = 0.6094**（Wilson95 [0.578, 0.640]）。

| 指标 | 臂 A 全量932 | 臂 A 剔除不可编译(n=749) | 臂 B 原始300 | 臂 B 扰动300 |
|---|---|---|---|---|
| accuracy | **0.609** | 0.640 | **0.702** | 0.667 |
| refusal Precision | 0.580 | — | 0.646 | 0.612 |
| refusal Recall | 0.784 | 0.733 | 0.893 | 0.913 |
| refusal F1 | 0.667 | — | 0.751 | 0.733 |
| specificity（safe 类） | 0.436 | 0.545 | 0.513 | 0.420 |

分类分解（accuracy）：

| 集 | SA | DI | SU | PR | RE |
|---|---|---|---|---|---|
| 臂 A 全量932 | 0.470 | 0.823 | **0.361** | 0.754 | 0.746 |
| 臂 B 原始300 | 0.583 | 0.944 | **0.362** | 0.756 | 0.946 |
| 臂 B 扰动300 | 0.505 | 0.901 | **0.234** | 0.902 | 0.947 |

- RE 组合泄漏单列：臂 A 0.746（118 例）/ 多问题子集 0.723（130 例）；臂 B 原始 0.946。
- 政策编译率：原始 146 条中 **117 可编译（80.1%）/ 29 不可编译（19.9%）**；扰动 126 条中 93/33。
- 臂 A 不可编译回退（判 unsafe）覆盖 183 例；SQL 不可判 2 例（数据集原生 typo，id197/234）。

## 3. 臂间与污染统计（预注册 McNemar 精确二项，双侧）

- **A vs B（原始300 配对）**：B 单独对 55 例 vs A 单独对 34 例，**p=0.033** —— 同模型下
  verbatim 提示直判显著优于机械编译判定。
- A vs B（扰动300 配对）：55 vs 42，p=0.223（不显著）。
- **污染检验（臂内 原始 vs 扰动 配对）**：臂 A 13 vs 10，p=0.678；臂 B 27 vs 16，p=0.126
  —— 两臂均无显著扰动退化，**无训练集污染信号**（臂 B 有 -3.5pt 的非显著下降，如实记录）。

## 4. 分歧类别分析（分支 (c) 义务；逐例见 `armA_original.json` 的 fired 字段）

**过拒（FP=264，害 SA/SU）三大来源**：
1. 不可编译回退强制拒答：94 例（SA62+SU32）——条款类型：时间比较（"before 2017"）、
   用途限制（"仅可统计分析"）、自然语言身份→主键映射（"Mary 只能看自己的数据"但 scope 列是 ID）、
   schema 缺列（"card number"无对应列）；
2. R2 谓词联结过火：77+ 例——SA/SU 的对抗性构造刻意"触碰"受保护列但不泄漏结果；
3. R1/R1a 直接命中但官方判 safe：SU 的"句法相近、语义相反"设计正面击穿触发词/表列机械检查。

**漏放（FN=100，全部 no_rule_fired）**：DI39/PR31/RE30——语义级泄漏（先验知识、常识推理、
跨查询结果对应）不经过受保护列的句法路径，机械规则不可见。

**结论**：SecureSQL ⑤族条款约 1/5 被编译器自报不可机械化；即使可编译，对抗性负样本（SU 36%）
与推理型正样本（FN 全部无规则可触发）共同标出"自然语言政策可编译边界"——泄漏判定的本性是
"结果可否对应/推断"而非"列是否被触碰"。同模型 gpt-5.5 直判虽显著更好（70.2%），但在 SU 上同样
塌陷（36.2%，扰动后 23.4%），说明该边界不是编译器工程缺陷，而是任务语义所致。三分支预注册下
本结果按 (c) 成文。

## 5. 参照锚点（论文已发表数字，非同台比较）

SecureSQL 论文（2024）：15 个 LLM 最优 61.7%（Qwen1.5-32B 5-shot）；人类约 94%。
本实验：机械编译判定 60.9% ≈ 2024 年最优 LLM 水平；2026 gpt-5.5 verbatim 70.2%，仍远低于人类。
设置差异（schema 来自 tables.json 而非 sqlite 现场导出、模型代际、zero-shot JSON 输出）已在协议 §5.2 声明。

## 6. 失败与例外（如实披露）

- group-B 分组 gpt-5.5 渠道中途持续 500（`get_channel_failed`，探测 0/4）→ Amendment 2
  transport-only 切至 default 分组（同网关同模型同参数，探测 6/6，v24 有同类先例）；证据落盘。
- 臂 B 原始集 1 例输出 JSON 损坏（id=331，raw 可查）按无效计，n=299；扰动集 300/300 全有效；
  API 永久失败 0；全部低于协议 5% 中止线。
- canary 门：编译器 2/2、臂 B 2/2 通过后才开跑（`raw/*/canary.jsonl`）。
- 臂 A SQL 不可判 2 例（数据集原生坏 SQL）按冻结规则计 unsafe 并单列。

## 7. 可复跑命令（工作目录本目录；密钥文件就位即可）

```bash
python3 build_schema_bundle.py            # 重建 57 库 schema 束 + 覆盖验证
python3 perturb.py subsample              # 冻结 300 分层抽样（seed 20260714，幂等防漂移）
python3 perturb.py entities && python3 perturb.py apply   # 扰动（LLM 只出实体清单，替换全脚本确定性）
python3 compile_policies.py canary && python3 compile_policies.py compile
python3 compile_policies.py compile-perturbed
python3 checker.py original && python3 checker.py perturbed
python3 run_armB.py canary && python3 run_armB.py run --set original && python3 run_armB.py run --set perturbed
python3 score.py                          # -> scores.json
# 或一键（各阶段断点续传）：./driver.sh
```

## 8. 交付物清单

`protocol.md` + `frozen_protocol.sha256`（v1.0 与两次 Amendment 的指纹链）、`data/`（官方 zip 镜像、
schema 束、SOURCES.md、SHA256SUMS）、`policy_nodes.json` / `policy_nodes_perturbed.json`（146+126 份
LLM 解析结果全落盘、可人工抽核）、`perturbation_map.json`（改写映射发布，18 处实体替换）、
`subsample_300.json`、`armA_original.json` / `armA_perturbed.json`（逐例触发规则）、
`raw/`（compiler/armB/perturber 全部原始响应与 canary）、`scores.json`、本文件。
