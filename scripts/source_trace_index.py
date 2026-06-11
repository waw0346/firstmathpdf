#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build and verify a source trace index for cropped math problems.

This script does not edit problem text, answers, solutions, or original PDFs.
It creates/updates a separate SQLite table that records where each cropped
problem came from: source PDF, page, column, subject page range, and crop bounds.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))

import crop_pipeline_audit  # noqa: E402

DB_PATH = BASE / "db" / "problems.db"
REPORT_JSON = BASE / "logs" / "agents" / "source_trace_index.json"
REPORT_MD = BASE / "wiki" / "00_SOURCE_TRACE_INDEX.md"


DDL = """
CREATE TABLE IF NOT EXISTS problem_source_trace (
    problem_id TEXT PRIMARY KEY,
    source_pdf_path TEXT NOT NULL,
    source_pdf_name TEXT NOT NULL,
    source_page_number INTEGER NOT NULL,
    source_column TEXT NOT NULL,
    source_subject_code TEXT NOT NULL DEFAULT '',
    source_page_range TEXT NOT NULL,
    crop_path TEXT NOT NULL DEFAULT '',
    crop_y0_pt REAL,
    crop_y1_pt REAL,
    gap_to_boundary_pt REAL,
    image_block_count INTEGER NOT NULL DEFAULT 0,
    trace_method TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    FOREIGN KEY(problem_id) REFERENCES problems(id)
);
"""


INDEX_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_problem_source_trace_pdf ON problem_source_trace(source_pdf_name)",
    "CREATE INDEX IF NOT EXISTS idx_problem_source_trace_page ON problem_source_trace(source_pdf_name, source_page_number)",
    "CREATE INDEX IF NOT EXISTS idx_problem_source_trace_subject ON problem_source_trace(source_subject_code)",
]


def subject_from_id(problem_id: str) -> str:
    if "_확통_" in problem_id:
        return "확통"
    if "_미적분_" in problem_id:
        return "미적분"
    if "_기하_" in problem_id:
        return "기하"
    return ""


def page_range_for(number: int, subject: str) -> str:
    if number <= 22:
        return "0-7"
    if subject == "확통":
        return "8-11"
    if subject == "미적분":
        return "12-15"
    if subject == "기하":
        return "16-19"
    return "8-19"


def build_rows() -> tuple[list[tuple], dict]:
    audit = crop_pipeline_audit.audit()
    rows = []
    errors = []
    verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in audit["simulated_rows"]:
        problem_id = item["id"]
        pdf_name = item["pdf"]
        pdf_path = item["pdf_path"]
        bounds = item["bounds"]
        crop_path = item.get("crop_path") or ""
        if not pdf_name or not bounds:
            errors.append(problem_id)
            continue
        subject = subject_from_id(problem_id)
        number = int(bounds["num"])
        rows.append(
            (
                problem_id,
                pdf_path,
                pdf_name,
                int(bounds["page"]),
                bounds["col"],
                subject,
                page_range_for(number, subject),
                crop_path,
                float(bounds["clip_y0"]),
                float(bounds["crop_y1"]),
                float(bounds["gap_to_boundary_pt"]),
                int(bounds["image_blocks"]),
                "crop_pipeline_audit.v1",
                verified_at,
            )
        )

    summary = {
        "db_crop_rows": audit["db_crop_rows"],
        "trace_rows_ready": len(rows),
        "untraceable": len(errors),
        "untraceable_sample": errors[:20],
        "missing_pdf": audit["missing_pdf"],
        "position_miss": audit["position_miss"],
        "boundary_risk_under_20pt": audit["boundary_risk_under_20pt"],
        "image_block_cases": audit["image_block_cases"],
    }
    return rows, summary


def apply_index(rows: list[tuple]) -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(DDL)
        for sql in INDEX_DDL:
            con.execute(sql)
        con.executemany(
            """
            INSERT INTO problem_source_trace (
                problem_id, source_pdf_path, source_pdf_name, source_page_number,
                source_column, source_subject_code, source_page_range, crop_path,
                crop_y0_pt, crop_y1_pt, gap_to_boundary_pt, image_block_count,
                trace_method, verified_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(problem_id) DO UPDATE SET
                source_pdf_path=excluded.source_pdf_path,
                source_pdf_name=excluded.source_pdf_name,
                source_page_number=excluded.source_page_number,
                source_column=excluded.source_column,
                source_subject_code=excluded.source_subject_code,
                source_page_range=excluded.source_page_range,
                crop_path=excluded.crop_path,
                crop_y0_pt=excluded.crop_y0_pt,
                crop_y1_pt=excluded.crop_y1_pt,
                gap_to_boundary_pt=excluded.gap_to_boundary_pt,
                image_block_count=excluded.image_block_count,
                trace_method=excluded.trace_method,
                verified_at=excluded.verified_at
            """,
            rows,
        )
        con.commit()
        return con.execute("SELECT COUNT(*) FROM problem_source_trace").fetchone()[0]
    finally:
        con.close()


def write_reports(summary: dict, applied_count: int | None) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(summary)
    payload["applied_trace_rows"] = applied_count
    payload["policy"] = "separate trace table only; originals/problems/answers/solutions are not modified"
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    apply_line = "dry-run only" if applied_count is None else f"{applied_count} rows in problem_source_trace"
    md = f"""---
tags: [source-trace, db, crop, audit]
---

# 원본 역추적 인덱스

> 원본 문제, 원본 정답, 원본 해설은 변경하지 않는다. 이 문서는 크롭 이미지가 어느 원본 PDF와 페이지 범위에서 생성되었는지 별도 색인으로 추적하기 위한 결과이다.

## 결과

- DB crop 대상: {summary['db_crop_rows']}
- 역추적 가능 행: {summary['trace_rows_ready']}
- 역추적 불가 행: {summary['untraceable']}
- 적용 상태: {apply_line}
- PDF 매칭 실패: {summary['missing_pdf']}
- 문제 위치 탐지 실패: {summary['position_miss']}
- 다음 문제 경계 위험: {summary['boundary_risk_under_20pt']}
- 이미지 블록 포함 문제: {summary['image_block_cases']}

## 추가된 색인 필드

- `problem_id`
- `source_pdf_path`
- `source_pdf_name`
- `source_page_number`
- `source_column`
- `source_subject_code`
- `source_page_range`
- `crop_path`
- `crop_y0_pt`
- `crop_y1_pt`
- `gap_to_boundary_pt`
- `image_block_count`
- `trace_method`
- `verified_at`

## 운영 원칙

- 문제 본문, 정답, 기존 해설은 수정하지 않는다.
- DB 본문 컬럼을 덮어쓰지 않고 `problem_source_trace` 테이블에만 원본 역추적 정보를 둔다.
- 신규 PDF ingest 후에는 이 스크립트를 실행해 PDF 매칭, 위치 탐지, 이미지 포함, 경계 위험을 동시에 점검한다.
- `scripts/ingest_pdf_v4.py`는 기본적으로 ingest 완료 후 `source_trace_index.py --apply`와 `crop_pipeline_audit.py`를 실행한다.
- `agents/ingest_agent.py --source-trace`로 같은 색인을 수동 갱신할 수 있다.
"""
    REPORT_MD.write_text(md, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write problem_source_trace into db/problems.db")
    args = parser.parse_args()

    rows, summary = build_rows()
    applied_count = apply_index(rows) if args.apply else None
    write_reports(summary, applied_count)
    print(json.dumps({**summary, "applied_trace_rows": applied_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
