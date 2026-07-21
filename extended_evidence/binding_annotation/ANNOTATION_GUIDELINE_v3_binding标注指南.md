# MultiGov 物理绑定（binding）人工标注指南 v3

## v3 修复说明（相对最初版本）
- 修复了候选项缺失：每题现在**完整提供 option_A–D 四个同域候选**（其一为已发布契约中的绑定）+ option_E；
- 判定所需的三个已发布目录文件**已随包提供**（released_catalogs/ 目录）；
- 正确答案位置已平衡（A/B/C/D 各 15 题），不存在位置规律。

## 背景与目的
此前三位从业者已验证 action/metric/grain 标签的可重构性（κ=0.968）。本轮扩展到 **physical binding 层**：仅凭已发布契约，验证"指标→必需物理资产"的绑定关系能否被独立重构。

## 包内文件
- `binding_annotation_sheet_v3_annotatorX.csv`：60 题（12 域分层，seed=20260712 可复现）。三份为相同的空白模板，分发后各自独立填写。
- `released_catalogs/`：判定唯一依据——`metric_catalog.jsonl`（指标定义/别名/coverage 节点）、`physical_coverage.jsonl`（各域物理节点清单）、`governance_edges.jsonl`（治理边）。**包内不含答案文件**（metric_coverage_bindings.jsonl 已隔离在作者侧）。

## 标注任务
每题给出指标（名称/别名）、其 coverage 依赖节点与角色，以及 4 个同域候选物理节点。请查阅 released_catalogs/ 判断：该指标的必需物理资产是 A/B/C/D 中哪一个；若认为已发布契约信息不足以推出，选 E。
- `your_answer` 填一个字母；`confidence` 按真实把握填 1–5（不必都是 5）；有任何犹豫或歧义请写 notes。

## 独立性要求（严格执行）
- 三人**各自在自己的电脑上**独立完成，过程中不讨论、不互看、不使用任何 AI 工具；
- 请记录各自实际用时（分钟），随表回交；
- 回交原始文件本身（不要合并、不要誊录到新文件）——三份文件的自然差异（编码/换行/填写痕迹）正是独立性的证据。

## 标注者要求
具备 BI 指标治理/数据目录/语义建模背景之一；未参与本论文写作、编译器实现或金标制作。

## 回收
三份原件交回后，作者侧脚本计算 Fleiss κ、三方一致率、majority-vs-released 一致率、E 率，全部分歧逐例披露并做敏感性分析。预计每人 60–90 分钟。
