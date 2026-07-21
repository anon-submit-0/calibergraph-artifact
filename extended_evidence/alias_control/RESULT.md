# P1b 结果报告 — RapidFuzz 确定性 Alias 消歧对照（rapidfuzz_alias_top1）

- 协议：`protocol.md`（先冻结，SHA256 `1e5cddd750ce9b8dcb01b46dae3293f8255faef502cb3d274ba205521a362f04`，与 `scores.json.protocol_sha256` 一致，先注册后执行链条可验证）
- 执行：2026-07-14，纯本地确定性，**LLM 调用 = 0**；rapidfuzz 3.13.0（MIT），Python 3.9.6
- 复现性：重跑一次，`predictions_*.jsonl` 与 `scores.json` 字节级一致（确定性验证通过）
- 计分：与 v24 public_benchmark `results/` 既有 baseline 完全同口径（score_rows 语义逐行复刻）

## 一、总表（overall）

| 层 | n | metric | dim_exact | dim_recall | joint | refusal P | refusal R |
|---|---|---|---|---|---|---|---|
| GovTwin-159 | 159 | **1.000** | 0.597 | 1.000 | **0.597** | 1.000 | 1.000 |
| MultiGov-510 | 510 | **0.639** | 0.341 | 0.404 | **0.000** | 0.000 | 0.000 |
| Iowa-32 | 32 | **0.812** | 0.562 | 0.938 | **0.500** | 1.000 | 0.571 |
| （参照）CaliberGraph | — | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## 二、family 分解（关键行）

| 层 / family | n | metric | dim_exact | joint | refusal R |
|---|---|---|---|---|---|
| GovTwin hierarchy | 64 | 1.000 | **0.000** | 0.000 | — |
| GovTwin single_or_flat | 86 | 1.000 | 1.000 | 1.000 | — |
| GovTwin synthetic_refusal | 9 | 1.000 | 1.000 | 1.000 | **1.000** |
| MultiGov answerable_direct | 115 | 1.000 | 0.000 | 0.000 | — |
| MultiGov denominator_caliber | 29 | 1.000 | 0.000 | 0.000 | — |
| MultiGov finest_grain_trap | 163 | 1.000 | 0.000 | 0.000 | — |
| MultiGov temporal_anchor | 19 | 1.000 | 0.000 | 0.000 | — |
| MultiGov policy_refusal | 184 | 0.000 | 0.946 | 0.000 | **0.000** |

## 三、分支判定：**命中预注册主分支 (i)** —— 铁律 3 兑现

**Metric identity 部分乃至大部可解**（①族"有机制"确有效）：
- GovTwin 全部 159 例（含 9 例拒答）metric 维度 1.000；MultiGov 全部 326 例可答案例 metric 命中 1.000（overall 0.639 全部由 184 例 policy 拒答被放行拖低）；Iowa 0.812。
- 即：**alias 消歧这一"识别问题"，一个 60 行的确定性 fuzzy matcher 就能大体解决。**

**但 joint 与治理类拒答崩塌**（②③④⑤族全放行，无 witness 无从拦截）：
1. **粒度族②崩塌**：GovTwin hierarchy 64 例 dim_exact=0 —— "segment level 1" 对 level 2/3 的 token_set_ratio=92.9 ≥ 阈值 85，三层粒度全被选入，无 grain witness 无法裁到金标粒度；MultiGov finest_grain_trap 163 例同因全灭。
2. **跨域 alias 碰撞**：MultiGov 12 个 domain 的同名维度（"fine scope" 等）全部过阈值（每例选入 12 个维度），无治理图 scope witness 无法定域 ⇒ MultiGov joint = **0.000**（510 例无一 joint 正确）。
3. **policy/口径族拒答全放行**：MultiGov 184 例 policy_refusal 全部照常作答（refusal R=0.000）；Iowa 的 `DROP TABLE iowa_liquor_sales` 因表名含 "sales" 反而匹配到 sales_dollars 作答，profit_margin/gross margin 两例不可答指标照答（refusal R=0.571，漏 3/7）。
4. Iowa 另暴露 metric 近义混淆（"Invoice count"→item_count、"Store count"→item_count）与父子维度过选（county+city 同选）。

**如实报告的反向发现（不隐瞒）**：GovTwin 的 9 例 synthetic_refusal 与 Iowa 的 4/7 拒答被该 baseline **凭零匹配兜底正确拒掉**（GovTwin refusal P/R=1.000/1.000）——因为这两层的拒答族是"目录外身份型"请求，alias 机制天然覆盖；而 MultiGov 的拒答族是"治理型"（policy/披露/口径），alias 机制 0 命中。此对比本身即为论文可用证据：**拒答有两种，身份型拒答 alias 机制可解，治理型拒答必须 witness**。

## 四、结论（借靶子讲剑）

①族"有机制"对照成立：RapidFuzz alias top-1 把 metric 识别做到 GovTwin 1.000 / MultiGov 可答子集 1.000 / Iowa 0.812，证明 CaliberGraph 的贡献**不在** alias 表面形式识别；而 joint（0.597 / 0.000 / 0.500 vs CaliberGraph 三层 1.000）与治理型拒答（MultiGov refusal R 0.000 vs 1.000）的差距，把贡献精确定位到 **caliber witness / 粒度编译 / 域定界 / policy 编译**这四个 alias 机制之外的环节。预注册期望 (i) 成立，无需启用意外分支 (ii)。

## 五、产出物清单

- `protocol.md`（冻结协议）
- `run_alias_control.py`（runner，确定性，零 LLM）
- `predictions_govtwin.jsonl`（159 行）/ `predictions_multigov.jsonl`（510 行）/ `predictions_iowa.jsonl`（32 行）
- `scores.json`（overall + family 分解 + 输入/协议 SHA256 + 盲评审计 gold_field_leaks=0）
- 本文件 `RESULT.md`
