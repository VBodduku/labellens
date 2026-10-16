"""Small in-memory store per scan_id so /api/recheck can reuse interpretations and summaries."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock

from shared.contract import Lang, ProfileReport, UnknownItem
from shared.engine_interface import TermInterpretation

MAX_SCANS = 256


def fingerprint(report: ProfileReport) -> tuple[tuple[str, str, str], ...]:
    """What a summary depends on: every result's state and reason."""
    return tuple((r.restriction_id, r.state, r.reason_code) for r in report.results)


@dataclass
class ScanRecord:
    lang: Lang
    interpretations: dict[str, TermInterpretation] = field(default_factory=dict)
    retake_unknowns: list[UnknownItem] = field(default_factory=list)
    summaries: dict[str, tuple[tuple[tuple[str, str, str], ...], str]] = field(default_factory=dict)

    def remember_summaries(self, reports: list[ProfileReport]) -> None:
        self.summaries = {r.profile_id: (fingerprint(r), r.summary) for r in reports if r.summary}

    def reusable_summaries(self, reports: list[ProfileReport]) -> dict[str, str]:
        """Stored summaries whose verdicts have not changed since they were written."""
        return {r.profile_id: self.summaries[r.profile_id][1] for r in reports
                if r.profile_id in self.summaries and self.summaries[r.profile_id][0] == fingerprint(r)}


class ScanMemory:
    def __init__(self, capacity: int = MAX_SCANS) -> None:
        self._records: OrderedDict[str, ScanRecord] = OrderedDict()
        self._capacity = capacity
        self._lock = Lock()

    def put(self, scan_id: str, record: ScanRecord) -> None:
        with self._lock:
            self._records[scan_id] = record
            self._records.move_to_end(scan_id)
            while len(self._records) > self._capacity:
                self._records.popitem(last=False)

    def get(self, scan_id: str) -> ScanRecord | None:
        with self._lock:
            record = self._records.get(scan_id)
            if record is not None:
                self._records.move_to_end(scan_id)
            return record


SCAN_MEMORY = ScanMemory()
