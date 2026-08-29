"""Read-only registry joining the public Viridis Canon to ViridisOS.

The registry is descriptive, not actuating. A Canon record can become a kernel
candidate here, but only a separately reviewed runtime module can become READY
and only the certification layer can issue a certificate.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Iterable


DEFAULT_PATH = Path(__file__).with_name("canon_kernel_registry.json")
STANDARD = "VOS-CANON-KERNEL-REGISTRY-1"
ALLOWED_RESEARCH_STATES = {"ZERO_SORRY_RESEARCH", "CANON_WORKING", "QUARANTINED"}
ALLOWED_KERNEL_STATES = {"KERNEL_CANDIDATE", "NOT_ELIGIBLE", "QUARANTINED"}
ALLOWED_DISPOSITIONS = {
    "BACKLOG_NO_WRAPPER",
    "BACKLOG_CANON_ADMISSION_REQUIRED",
    "QUARANTINED",
    "MODULE_CATALOG_RECONCILIATION_REQUIRED",
    "MODULE_BLOCKED_CANON_ADMISSION_REQUIRED",
}


@dataclass(frozen=True)
class CanonKernelRecord:
    record_id: str
    title: str
    path: str
    source_sha256: str
    doi: str
    lean_module: str
    canon_status: str
    canon_integrity: str
    research_state: str
    kernel_state: str
    disposition: str
    module_id: str
    decision_tree_paths: tuple[str, ...]
    certification_authority: bool

    @property
    def kernel_candidate(self) -> bool:
        return self.kernel_state == "KERNEL_CANDIDATE"


class CanonKernelRegistry:
    def __init__(self, path: Path = DEFAULT_PATH):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("standard") != STANDARD:
            raise ValueError("invalid Canon kernel registry standard")
        source = payload.get("source_catalog")
        if not isinstance(source, dict):
            raise ValueError("source_catalog must be an object")
        if re.fullmatch(r"[0-9a-f]{64}", str(source.get("catalog_digest", ""))) is None:
            raise ValueError("invalid Canon catalog digest")
        if re.fullmatch(r"[0-9a-f]{40}", str(source.get("canon_commit", ""))) is None:
            raise ValueError("invalid Canon commit")

        rows = payload.get("records")
        if not isinstance(rows, list):
            raise ValueError("Canon kernel records must be an array")
        records: list[CanonKernelRecord] = []
        seen: set[str] = set()
        for row in rows:
            item = dict(row)
            item["decision_tree_paths"] = tuple(item.get("decision_tree_paths", []))
            record = CanonKernelRecord(**item)
            if record.record_id in seen:
                raise ValueError(f"duplicate Canon record_id: {record.record_id}")
            if re.fullmatch(r"[0-9a-f]{64}", record.source_sha256) is None:
                raise ValueError(f"invalid source digest: {record.record_id}")
            if record.research_state not in ALLOWED_RESEARCH_STATES:
                raise ValueError(f"invalid research state: {record.research_state}")
            if record.kernel_state not in ALLOWED_KERNEL_STATES:
                raise ValueError(f"invalid kernel state: {record.kernel_state}")
            if record.disposition not in ALLOWED_DISPOSITIONS:
                raise ValueError(f"invalid disposition: {record.disposition}")
            if record.certification_authority:
                raise ValueError(f"registry cannot grant certification authority: {record.record_id}")
            if record.kernel_candidate != (
                record.canon_status == "verified" and record.canon_integrity == "gate-passed"
            ):
                raise ValueError(f"kernel eligibility disagrees with Canon: {record.record_id}")
            seen.add(record.record_id)
            records.append(record)

        stats = payload.get("stats", {})
        if stats.get("records") != len(records):
            raise ValueError("registry record count does not match stats")
        if stats.get("kernel_candidates") != sum(row.kernel_candidate for row in records):
            raise ValueError("kernel candidate count does not match stats")
        self.source_catalog = source
        self.policy = payload.get("policy", {})
        self.stats = stats
        self._records = tuple(records)

    def records(self) -> tuple[CanonKernelRecord, ...]:
        return self._records

    def get(self, record_id: str) -> CanonKernelRecord | None:
        key = record_id.strip().casefold()
        return next((row for row in self._records if row.record_id.casefold() == key), None)

    def candidates(self) -> Iterable[CanonKernelRecord]:
        return (row for row in self._records if row.kernel_candidate)

    def as_dict(self) -> dict:
        return {
            "standard": STANDARD,
            "source_catalog": self.source_catalog,
            "policy": self.policy,
            "stats": self.stats,
            "records": [
                {**row.__dict__, "decision_tree_paths": list(row.decision_tree_paths)}
                for row in self._records
            ],
        }
