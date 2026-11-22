import json
from dataclasses import asdict

from reports.ledger import PairReportRecord, ReportRecord


def export_report(record: ReportRecord | PairReportRecord) -> str:
    if isinstance(record, PairReportRecord):
        document = {
            'report_id': record.report_id,
            'left': list(record.left),
            'right': list(record.right),
            'matrix': [[str(mass) for mass in row] for row in record.matrix],
            'parents': [asdict(parent) for parent in record.parents],
        }
    else:
        document = {
            'report_id': record.report_id,
            'entry': record.entry,
            'route_id': record.route_id,
            'mass': [str(value) for value in record.mass],
            'parents': [asdict(parent) for parent in record.parents],
        }
    return json.dumps(document, sort_keys=True, separators=(',', ':'))
