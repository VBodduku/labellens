"""Builds the final ScanResult from an extraction and the engine's output."""
from __future__ import annotations

from datetime import datetime

from shared.contract import CONTRACT_VERSION, LabelExtraction, Lang, ScanResult
from shared.engine_interface import EngineOutput


def build_scan_result(extraction: LabelExtraction, output: EngineOutput, lang: Lang) -> ScanResult:
    return ScanResult(
        contract_version=CONTRACT_VERSION,
        scan_id=extraction.scan_id,
        lang=lang,
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        extraction=extraction,
        annotations=output.annotations,
        nutrition_analysis=output.nutrition_analysis,
        reports=output.reports,
        unknowns=output.unknowns,
    )
