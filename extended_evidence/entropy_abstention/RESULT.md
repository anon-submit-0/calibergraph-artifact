# P1a 结果：熵基置信度弃答 baseline（AAAI-25 Somov & Tutubalina 重实现，预注册协议冻结版）

日期：2026-07-14。协议：`protocol.md`（冻结 sha256 `01e35be4…`，AMENDMENT 1 仅传输层）。
实现：deepseek-3.2 @ <anon> 网关，Schema-RAG round-0 提示（ 冻结镜像），每例 k=5 采样（temperature 0.7），采样一致性熵作弃答判据（网关 logprobs 探针实证不可得，协议 §0 已披露该退化）。
评测：GovTwin-159 + MultiGov seeded-200（复用  canonical 子集 seed=20260711，与论文"same MultiGov-200"可比）。1795 调用全部落盘，**0 条 error 行**，解析 1793 ok + 2 first-brace-block，0 缺失。

## 一、三档阈值全报（pooled 359；括号内 GovTwin / MultiGov）

| 阈值 τ | 弃答率 | answered 子集 joint | 弃答对 would-be 错误覆盖 | refusal P / R（answered，released 口径） |
|---|---|---|---|---|
| 全体一致 (c1=5) | 30.1% (108/359) | **0.972**（0.936 / 1.000） | 81.1% (30/37) | 1.000 / 1.000 |
| 多数一致 (c1≥3) | 1.9% (7/359) | 0.901（0.799 / 0.984） | 5.4% (2/37) | 0.976 / 1.000 |
| 任一（k=5 plurality，不弃答） | 0% | 0.897（0.799 / 0.975） | 0% | 0.976 / 1.000 |

弃答视为拒答的另一读法（协议 §7.4b）：unanimous 档 refusal P 崩至 0.431（R 1.0）——弃答大量落在本可答对的例上：**对正确例的误弃答率 24.2%**（78/322）。

## 二、错误族分布与"弃答-caliber 重叠率"

k=5 plurality 下 would-be 错误共 37 例，**全部落在 ③grain 族**（GovTwin hierarchy 32 + MultiGov finest_grain_trap 5）；①metric identity（131 例）、②caliber（11 例）、④temporal/coverage（8 例）、⑤refusal（81 例）四族 would-be 错误均为 0。

- **弃答∩caliber 错误重叠率：无定义（0/0）**——②族 would-be 错误为 0 例（<5），按冻结协议 §8 小格诚实条款，②族分支判定标注 **underpowered**，报告确数不宣称显著性。
- 但机制级信号更硬：**②caliber 族 11 例全部 5/5 采样一致，平均熵恒等于 0.000**——不确定性通道在 caliber 轴上携带零信息；若口径编译有错，采样一致性弃答在结构上不可能发出信号。⑤refusal 族平均熵 0.009（80/81 全一致），同样近零。
- **自信错误实证存在**：37 例错误中 7 例（18.9%）5/5 一致、熵=0（全为 grain 违规：模型五次采样一致输出祖先+后代双层级，违反 finest-grain 政策，如 govtwin_0008 pred [segment_l1,segment_l2] vs gold [segment_l2]）。任何熵阈值都放行这 7 例——unanimous 档 answered joint 因此停在 0.972 ≠ 1.000。
- **族内无判别力**：grain 族内弃答×错误 Fisher 双侧 p=0.134（错误例弃答 81.1% vs 正确例弃答 65.9%）——熵探测的是"题目所属族的难度"，不是"答案是否正确"。pooled Fisher p=1.5e-11 仅由错误集中于高熵 grain 族驱动，属族间混杂。

## 三、预注册分支判定

**判定：分支 (i) 成立（②格 underpowered 如实标注）。** 依据（协议 §8 原文对照）：②族 Fisher p=1.0（≥0.05，因 0 错误而空洞成立），且机制证据以更强形式出现——caliber 例熵恒为 0（信号通道空）、18.9% 错误零熵自信、grain 族内 p=0.134 无判别力。"caliber/治理类错误是自信错误、不产生不确定性信号"的机制级论点得到支持；②格自身的错误样本不足（11 例 0 错），论文措辞须写 underpowered + 熵≡0 双层表述，不得写"显著"。

## 四、成本（借靶子讲剑的另一半）

1795 调用；prompt 10,634,605 tokens + completion 1,785,634 tokens；单调用平均时延 26.5 s；k=5 = 单次调用 5× 边际成本。以 30.1% 弃答率+24.2% 误弃答为代价，answered joint 最高 0.972，仍低于 CaliberGraph 合同校验参考（1.000，零在线调用，<0.1 ms）。usable 操作点（majority，弃答 1.9%）仅覆盖 5.4% 错误。

## 五、诚实边界

- GovTwin base split 无 ②④ 族案例（协议已预先披露）；②族证据仅 MultiGov 11 例。
- 采样中途 multigov 曾因网关连接挂起停滞 82 分钟，按 AMENDMENT 1（仅传输层：110s socket + 120s 硬墙钟/次，重试≤3）修复后 resumable 续跑，先前 191 条记录原样保留；最终 0 error 行。
- k=5 plurality 本身是 self-consistency 增强，故本 baseline 的 τ=any 档已强于单次调用 Schema-RAG；对比时不可与单调用数字混用。

产物：`protocol.md`、`run_entropy_abstention.py`、`prompts/`、`raw/{govtwin,multigov}_raw.jsonl`（1795 行）、`predictions_{govtwin,multigov}.jsonl`、`scores.json`、本文件。
