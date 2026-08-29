#!/usr/bin/env python3
"""Build the deterministic, non-actuating Canon-to-ViridisOS registry."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


STANDARD = "VOS-CANON-KERNEL-REGISTRY-1"
CATALOG_SCHEMA = "https://jdhart81.github.io/viridis-canon/schemas/research-catalog-v1.json"


def canonical_digest(value: object) -> str:
    content = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_catalog(catalog: dict) -> None:
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise ValueError("unsupported Canon catalog schema")
    if catalog.get("publication_scope") != "public":
        raise ValueError("only the public Canon catalog may be ingested")
    if catalog.get("human_publish_gate") is not True:
        raise ValueError("Canon human publication gate is not recorded")
    payload = {key: value for key, value in catalog.items() if key != "catalog_digest"}
    if catalog.get("catalog_digest") != canonical_digest(payload):
        raise ValueError("Canon catalog digest mismatch")
    rows = catalog.get("records")
    if not isinstance(rows, list):
        raise ValueError("Canon catalog records must be an array")
    ids: set[str] = set()
    for row in rows:
        record_id = row.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("Canon record_id is required")
        if record_id in ids:
            raise ValueError(f"duplicate Canon record_id: {record_id}")
        if re.fullmatch(r"[0-9a-f]{64}", str(row.get("source_sha256", ""))) is None:
            raise ValueError(f"invalid source digest: {record_id}")
        ids.add(record_id)


def build_registry(catalog: dict, canon_commit: str, bindings: dict) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", canon_commit) is None:
        raise ValueError("canon_commit must be a full 40-character Git commit")
    validate_catalog(catalog)
    catalog_ids = {row["record_id"] for row in catalog["records"]}
    unknown = sorted(set(bindings) - catalog_ids)
    if unknown:
        raise ValueError(f"bindings reference unknown Canon records: {', '.join(unknown)}")

    records = []
    for source in catalog["records"]:
        verified = source.get("status") == "verified" and source.get("integrity") == "gate-passed"
        quarantined = source.get("status") == "quarantined"
        if verified:
            research_state = "ZERO_SORRY_RESEARCH"
            kernel_state = "KERNEL_CANDIDATE"
            disposition = "BACKLOG_NO_WRAPPER"
        elif quarantined:
            research_state = "QUARANTINED"
            kernel_state = "QUARANTINED"
            disposition = "QUARANTINED"
        else:
            research_state = "CANON_WORKING"
            kernel_state = "NOT_ELIGIBLE"
            disposition = "BACKLOG_CANON_ADMISSION_REQUIRED"

        binding = bindings.get(source["record_id"], {})
        disposition = binding.get("disposition", disposition)
        records.append({
            "record_id": source["record_id"],
            "title": source["title"],
            "path": source["path"],
            "source_sha256": source["source_sha256"],
            "doi": source.get("doi", ""),
            "lean_module": source.get("lean_module", ""),
            "canon_status": source.get("status", ""),
            "canon_integrity": source.get("integrity", ""),
            "research_state": research_state,
            "kernel_state": kernel_state,
            "disposition": disposition,
            "module_id": binding.get("module_id", ""),
            "decision_tree_paths": binding.get("decision_tree_paths", []),
            "certification_authority": False,
        })

    return {
        "standard": STANDARD,
        "source_catalog": {
            "schema": catalog["schema"],
            "repository": catalog["repository"],
            "release": catalog["release"],
            "catalog_digest": catalog["catalog_digest"],
            "canon_commit": canon_commit,
        },
        "policy": {
            "kernel_candidate_requires": ["status=verified", "integrity=gate-passed"],
            "automatic_module_activation": False,
            "automatic_decision_tree_activation": False,
            "automatic_certification_authority": False,
        },
        "stats": {
            "records": len(records),
            "kernel_candidates": sum(row["kernel_state"] == "KERNEL_CANDIDATE" for row in records),
            "canon_working": sum(row["research_state"] == "CANON_WORKING" for row in records),
            "quarantined": sum(row["research_state"] == "QUARANTINED" for row in records),
            "module_bindings": sum(bool(row["module_id"]) for row in records),
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--canon-commit", required=True)
    parser.add_argument(
        "--bindings",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runtime" / "canon_kernel_bindings.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runtime" / "canon_kernel_registry.json",
    )
    args = parser.parse_args()
    registry = build_registry(load_object(args.catalog), args.canon_commit, load_object(args.bindings))
    args.output.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(registry["stats"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
