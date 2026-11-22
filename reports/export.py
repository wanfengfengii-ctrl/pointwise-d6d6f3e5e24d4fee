import json
from dataclasses import asdict

from reports.ledger import ReportRecord


def export_report(record: ReportRecord) -> str:
    return json.dumps({
        'report_id': record.report_id,
        'entry': record.entry,
        'route_id': record.route_id,
        'mass': [str(value) for value in record.mass],
        'parents': [asdict(parent) for parent in record.parents],
    }, sort_keys=True, separators=(',', ':'))
