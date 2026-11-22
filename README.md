# 东岬双站复测质控台账

东岬精密机加厂的站务员根据轴套校准清单封定两站修订。夜班分析员点收站件并登记当班清单，关站后按指定证据签报。班长用报告号复核通过、判废和永不完结的风险，决定是否继续使用该路线。次班的校准勘误生成独立修订及站件，历史定稿按原号领取。

## 运行

需要 Python 3.11 和标准库。由运行平台提供 `check_project.py`。在项目根目录运行。

```sh
python3 -B check_project.py
python3 -B -m unittest discover -s tests -t .
python3 -B demo.py
```

演示显式读取 `samples/shift.json`，在临时工作目录分别打开甲站、乙站、实收和报告数据库。两站关闭后签报。次班重开甲站出更正件、重开中心领取新旧报告，然后输出概率、出处和对账结果。业务库初始化保留原数据。演示结束时清理本次临时目录。

## Python 接口

`CalibrationStore` 和 `IssuanceRegister` 使用同一权威站库路径。站务员可以使用不同站库分别服务两个站。`IntakeStore` 和 `ReportLedger` 各用中心业务路径。四种存储对象均提供 `close()`，可交给 `contextlib.closing` 管理。身份按所属库解释，换班沿用原库。中心不需要站库连接。

| 接口 | 输入与结果 |
| --- | --- |
| `calibration.imports.revise(store, batch)` | 提交完整校准批，返回整数修订号。校准内容与原据共同封定。 |
| `issue.freeze.freeze(store, register, station, revision_id)` | 返回 `IssuedPiece`，其 `piece_id` 是具名身份，`data` 是传给中心的固定字节。 |
| `intake.receive.receive(store, expected_station, data)` | 点收固定字节，返回整数实收号。已实收的同一固定件经合法重交返回原号。 |
| `intake.routes.route(store, mappings)` | 提交逐站出口映射，返回整数清单号。`get_route` 可读回固定映射。 |
| `analysis.review.review(intake, ledger, receipt_ids, entry, route_id)` | 提交两个有序实收号、入口和固定清单号。返回 `SignedReview`，含报告号和三项 `Fraction` 概率。 |
| `reports.lookup.read(ledger, report_id, export=False)` | 返回已签 `ReportRecord`。传入 `export=True` 获取同一快照的 JSON 文本。 |

`intake.catalog.list_station_pieces` 按站列出可选实收号和修订出处，`get_receipt` 按号取件。`calibration.store.CalibrationStore.load_source` 在站端按站别和修订号读取校准原据。定稿保存入口、清单号和两个有序父件。父件保存站别、来源修订号、实收号和固定件身份。

## 数据和核算规则

校准批是 JSON 兼容字典，包含 `station`、`batch`、`outlets` 和 `states`。`outlets` 声明本站出口。`states` 有一至三个对象，每个对象包含 `name`、`weight`、`records`。每条原据包含 `record`、`piece`、`outlet`、`probability`。`record` 在一批内唯一，`piece` 为实物编号。同状态同出口的多条计量相加，未列的已声明出口概率为零。数值接受整数或能被 `Fraction` 精确解析的字符串。各值在零至一之间，状态权重按站合计为一，每个状态的出口按状态合计为一。标识使用非空可打印文本，首尾无空白。

站件外层为 UTF-8 规范 JSON，字段为 `version`、`station`、`revision`、`body`、`piece_id`。版本值为 1。内容身份由规范载荷的 SHA-256 产生，用于核对交接内容一致性。正文公开出口及足以复现同一工件重复到访的行为。原据、实物编号、批次名及状态原名留站。

清单形如 `{'A': {'send': 'B', 'ok': 'pass'}, 'B': {'back': 'A', 'scrap': 'reject'}}`。两站名各自唯一，`pass` 与 `reject` 为保留终局名。所选件声明的每个出口都须有映射，额外合法映射按需取用。报告按请求中的来件顺序保留出处，按入口站及站别核算。两站独立确定检具状态，同一工件回站沿用初选，给定状态后各次按其出口分布行动。概率精确记录为 `(通过, 判废, 永不完结)`，三项合计为一，导出使用精确分数字符串。

非法输入抛出 `ValueError`，缺失的修订、实收、清单或报告号抛出 `LookupError`。报告签存遇到 SQLite 写入失败抛出 `PublicationError`，保留原始异常作为原因。报告号在正文和父件全部提交后返回。领取和导出直接读取已签快照。
