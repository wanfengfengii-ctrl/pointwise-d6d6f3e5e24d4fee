# 双清单同件终局签报

原有站端封定、中心点收和单路线签报见 `README.md`。两份清单使用同一对站件。出口仍按每个站件的校准分布解释，左右清单分别决定出口去向。抽取序号从各路线首次到访该站时计起。

## 调用和领取

- `analysis.review.review_pair(intake, ledger, receipt_ids, left, right)` 接收 V1 的两个有序实收号。`left` 和 `right` 各为 `(入口站, 固定清单号)` 元组，可使用同一清单，也可从不同站进入。两份方案均沿用 V1 选件校验，包括声明出口的完整映射。
- 返回对象提供 `report_id` 和 `matrix`。矩阵为三行三列的元组套元组，每格为非负 `Fraction`，合计为一。行是左路，列是右路，两轴依次为通过、判废、永不完结。
- 对照报告和单路报告的号码在同一个报告库中可由原 `reports.lookup.read(ledger, report_id, export=False)` 唯一定位。对照记录提供 `report_id`、`left`、`right`、`matrix` 和 `parents`。`left`、`right` 与请求中的元组一致，`parents` 沿用 V1 的两个 `ParentReference` 及请求中的来件顺序。
- `read(ledger, report_id, export=True)` 的对照报告 JSON 字段为 `report_id`、`left`、`right`、`matrix`、`parents`。两个方案各用 `[入口站, 清单号]` 表示。矩阵使用嵌套数组，每格用 `str(Fraction)` 形式的精确字符串表示。父件沿用 V1 JSON 字段。只打开报告库即可领取和导出当时签存的内容。
- 沿用 V1 的 `ValueError`、`LookupError` 和 `reports.publish.PublicationError` 语义。SQLite 签存失败时保留原异常作为原因。只有正文及两条有序父件出处都已提交才返回报告号。

例如，`a`、`b` 是两站实收号，`first`、`second` 是已登记清单号。提交 `review_pair(intake, ledger, (b, a), ('A', first), ('B', second))` 后，领取的父件应先列 `b`。交换方案会转置矩阵，父件仍按请求顺序保存。

## 样例

`pair_examples.py` 用 `samples/shift.json` 和现有校准夹具登记实收及清单。下表列出非零格，未列格均为零。

| 来件与路线 | 预期 |
| --- | --- |
| 甲的 `ok`、`send` 等概率，两路均从甲入，两清单均把 `ok` 判为通过、`send` 判废 | （通过，通过）和（判废，判废）各为 1/2 |
| 同上，只交换右清单中 `ok`、`send` 的终局 | （通过，判废）和（判废，通过）各为 1/2 |
| 两路使用原样例清单，左从甲入、右从乙入。甲等概率通过或送乙，乙等概率判废或退甲 | （通过，通过）、（通过，判废）、（判废，判废）各为 1/3 |
| 原甲件初选各半，分别固定出 `ok` 或 `send`。两路从甲入，左路直接通过或判废，右路 `ok` 通过、`send` 送乙且乙必退甲 | （通过，通过）和（判废，永不完结）各为 1/2 |
| 两清单的所有出口都转送到另一站 | （永不完结，永不完结）为 1 |
| 在单侧闭环样例中显式改用次班甲件。次班件在每次访甲时等概率出 `ok` 或 `send` | 新号的（通过，通过）和（判废，通过）各为 1/2。原号仍保存旧矩阵和原甲件出处 |

## 核验与演示

`python3 -B pair_examples.py baseline` 在原台账登记样例，实际签出两份相同边缘概率的单路定稿。实现后可用 `python3 -B pair_examples.py verify` 先运行原回归，再核对同件矩阵和重开领取。`python3 -B pair_examples.py demo` 输出实际领取的对照报告 JSON。

沿用仓库的 `.pointwise-runtime.json` v1 命令入口，`kind` 为 `cli`。`setup` 记录准备命令的参数数组列表，可保持为空。把 `verify` 和 `demo` 的参数数组接到能实际核验原回归与双清单签报、演示重开领取的入口。核验失败须返回非零退出码。
