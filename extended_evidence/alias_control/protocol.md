# P1b 预注册协议（冻结版）— RapidFuzz 确定性 Alias 消歧对照

- **协议状态**：FROZEN（先冻结后执行；本文件在任何预测/评分产出之前写定，此后不得修改）
- **冻结时间**：2026-07-14（Asia/Shanghai）
- **实验代号**：P1b `rapidfuzz_alias_top1`
- **角色定位**：①族"有机制"对照 —— 有 alias 消歧机制、**无任何 caliber witness / 治理图约束 / policy 检查**（兑现设计铁律 3）
- **铁律**：禁 mock；失败如实报；**零 LLM 调用**（纯确定性本地 baseline，converter-free）

## 1. Baseline 定义（钉死，不得事后调参）

依赖：`rapidfuzz==3.13.0`（MIT License，本机已安装，纯本地）。Python 3 标准库 + rapidfuzz，无网络、无 LLM。

### 1.1 文本归一化
- 查询与 alias 均经 `rapidfuzz.utils.default_process`（小写化、去非字母数字、压缩空白）。

### 1.2 打分函数（钉死一种）
- **`rapidfuzz.fuzz.token_set_ratio`**（processor=`default_process`）。
- 选择理由（先验）：请求文本长于 alias，alias 词元通常是请求词元子集；token_set_ratio 对词序不敏感且对子集包含友好，是 alias-in-request 场景的标准选择。**不使用 WRatio**（其内部启发式混合多种 ratio，可解释性差）。

### 1.3 Metric 选择（top-1）
- 候选键：metric_catalog.jsonl 每个 metric 的 **`aliases` 字段**（仅此字段，不加 metric_name/description）。
- metric 得分 = 该 metric 所有 alias 得分的最大值。
- 取全体 metric 中得分最高者为 top-1；**阈值 θ_m = 60**：若最高分 < 60 视为零匹配。
- **平局裁决（确定性）**：得分相同 → 取"命中 alias 归一化后字符更长"者（更具体）→ 仍平局取 `metric_id` 字典序最小者。
- 遍历顺序：metric 按 `metric_id` 字典序、alias 按文件内出现顺序，保证逐次运行完全可复现。

### 1.4 Dimension 选择（多选）
- 候选键：dimension_catalog.jsonl 每个 dimension 的 **`aliases` 字段**（仅此字段）。
- dimension 得分 = 其所有 alias 得分的最大值；**选取得分 ≥ θ_d = 85 的全部 dimension**（多维请求取超过阈值的全部）。
- **不做** allowed_dimensions 过滤、**不做** domain 过滤、**不做** 粒度/层级裁决 —— 这些属于治理图/witness 能力，本对照按设计不具备。
- 阈值先验理由：metric 是 argmax（阈值只管零匹配兜底），dimension 是集合成员判定，需要高精度阈值；85 为 rapidfuzz 实体链接常用高精度档。**θ_m、θ_d 一次钉死，不得看分后回调。**

### 1.5 Action 规则
- **永远 `answer`**，除非 metric 零匹配（最高分 < θ_m）→ `action = "refuse"` 且 `pred_metric_id = ""`。
- 无 witness、无 caliber、无 policy、无 disclosure 检查：policy_refusal / 粒度陷阱 / 分母口径 / 时窗错配等一律照常放行作答。

## 2. 评测层与输入（钉死）

根目录：`<REPO_ROOT>/releases/v24_group-B_evidence_fusion_submission_20260712/public_artifact/public_benchmark/`

| 层 | blind | gold | metric catalog | dimension catalog | n |
|---|---|---|---|---|---|
| GovTwin-159 | `govtwin_metric_caliber/blind_cases.jsonl` | 同目录 `gold_labels.jsonl` | 同目录 `metric_catalog.jsonl` | 同目录 `dimension_catalog.jsonl` | 159 |
| MultiGov-510 | `multigov_metric_caliber/blind_cases.jsonl` | 同目录 `gold_labels.jsonl` | 同目录 `metric_catalog.jsonl` | 同目录 `dimension_catalog.jsonl` | 510 |
| Iowa-32 | `iowa_liquor_metric_caliber/blind_cases.jsonl` | 同目录 `gold_labels.jsonl` | 同目录 `metric_catalog.jsonl` | 同目录 `dimension_catalog.jsonl` | 32 |

- 仅使用 base `blind_cases.jsonl`（不含 paraphrased/perturbed 变体）。
- **盲评协议**：预测阶段只读 blind_cases + 两张 catalog；gold_labels 仅在评分阶段读取。预测记录中不得出现任何 `expected_*` 字段。

## 3. 计分口径（与 results 已有 baseline 完全同口径）

复刻 `run_govtwin_eval.py` / `run_multigov_metric_caliber_eval.py` / `run_iowa_liquor_eval.py` 的 `score_rows` 语义（三脚本一致）：

- `refused = (action == "refuse") or (pred_metric_id == "")`
- `expected_refusal = (expected_action == "refuse")`
- `metric_ok = (pred_metric_id == expected_metric_id)`（refuse 金标 expected_metric_id=""，故正确拒答同时计 metric_ok）
- `dim_exact_ok = set(pred_dimensions) == set(expected_dimensions)`
- `dim_recall_ok = set(expected_dimensions) ⊆ set(pred_dimensions)`
- `joint_ok = metric_ok and dim_exact_ok`
- `refusal_precision = TP / max(1, TP+FP)`；`refusal_recall = TP / max(1, TP+FN)`（无预测拒答时 precision 记 0，同现有脚本约定）
- 汇总粒度：每层 overall + `query_family` 分解（Iowa 无 family 字段则仅 overall）。时间窗口字段不计分（同现有口径）。

## 4. 预注册期望（借靶子讲剑，两分支均可成文，冻结于跑分之前）

- **(i) 主预期**：metric identity 部分可解（①族 alias 机制确能命中不少 metric 表面形式），但 **joint 显著低于 CaliberGraph（三层均 1.000/或既有报告值）**，且 refusal recall 接近 0（MultiGov 184 例 policy/粒度类拒答几乎全被放行；GovTwin 9 例、Iowa 7 例同理）——因为②③④⑤族失败（粒度、口径、policy、时窗）没有任何机制拦截。此即铁律 3 的兑现：*alias 消歧机制单独存在时，无法替代 caliber witness*。
- **(ii) 意外分支**：若该确定性 baseline 在某层 joint/refusal 意外强（如 joint ≥ 0.9），如实报告并写入 RESULT.md，作为"该层难度主要在 alias 消歧"的证据重新解读该层贡献。
- 两分支都不修改协议、不重跑调参；结果一次成文。

## 5. 产出物（本目录）

1. `protocol.md`（本文件，先冻结）
2. `run_alias_control.py`（runner，确定性，零 LLM）
3. `predictions_{govtwin,multigov,iowa}.jsonl`（per-case 预测）
4. `scores.json`（三层 overall + family 分解 + 输入文件 SHA256 + 协议 SHA256）
5. `RESULT.md`（中文结果报告 + 分支判定）
