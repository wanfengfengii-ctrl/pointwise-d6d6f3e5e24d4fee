from reports.export import export_report
from reports.ledger import PairReportRecord, ReportLedger, ReportRecord


def read(ledger: ReportLedger, report_id: int, export: bool = False) -> ReportRecord | PairReportRecord | str:
    if type(report_id) is not int or not 0 < report_id < 2**63:
        raise ValueError('invalid report number')
    record = ledger.load_report(report_id)
    if record is None:
        raise LookupError(f'no signed report {report_id}')
    return export_report(record) if export else record
