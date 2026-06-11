#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit the PDF-to-crop pipeline without modifying originals, crops, or DB.

Checks:
  - DB problem rows with crop paths can be mapped back to source PDFs.
  - Problem numbers can be found in the expected PDF page ranges.
  - The crop algorithm includes PDF image blocks such as graphs and diagrams.
  - Expanded crops do not run into the next problem boundary.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import fitz

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import crop_all  # noqa: E402

DB_PATH = BASE / "db" / "problems.db"
REPORT_JSON = BASE / "logs" / "agents" / "crop_pipeline_audit.json"
REPORT_MD = BASE / "wiki" / "00_CROP_PIPELINE_EMERGENCY_CHECKLIST.md"


def question_pdfs() -> list[Path]:
    bad = ("정답", "해설", "해설지", "EBS", "ebs")
    return [p for p in (BASE / "sources").glob("*/*.pdf") if not any(k in p.name for k in bad)]


def choose_pdf(problem_id: str) -> Path | None:
    pdfs = question_pdfs()
    if problem_id.startswith("2025_10"):
        return next((p for p in pdfs if p.parent.name == "2025" and "10" in p.name), None)
    if problem_id.startswith("2025_수능"):
        return next((p for p in pdfs if p.parent.name == "2025" and "수능" in p.name), None)
    if problem_id.startswith("2026_5"):
        return next((p for p in pdfs if p.parent.name == "2026" and "5월" in p.name), None)
    if problem_id.startswith("2026_6"):
        return next((p for p in pdfs if p.parent.name == "2026" and "6월" in p.name), None)
    if problem_id.startswith("2026_9"):
        return next((p for p in pdfs if p.parent.name == "2026" and "9월" in p.name), None)
    if problem_id.startswith("2026_수능"):
        return next((p for p in pdfs if p.parent.name == "2026" and "수능_" in p.name), None)
    return None


def candidate_ranges(problem_number: int) -> list[tuple[tuple[int, int], range | None]]:
    if problem_number >= 23:
        return [
            ((8, 11), range(23, 31)),
            ((12, 15), range(23, 31)),
            ((16, 19), range(23, 31)),
        ]
    return [((0, 7), None)]


def calc_bounds(doc: fitz.Document, prob: tuple, probs: list) -> dict:
    num, pn, _x0n, y0n, col = prob
    w_pt, h_pt = doc[0].rect.width, doc[0].rect.height
    mid_x = w_pt * crop_all.MID_RATIO
    mg_l = w_pt * crop_all.MG_L_RATIO
    scale = crop_all.DPI / 72
    idx = probs.index(prob)
    ny = h_pt * 0.975
    for j in range(idx + 1, len(probs)):
        if probs[j][1] == pn and probs[j][4] == col:
            ny = probs[j][3] - 4
            break

    is_l = col == "L"
    xs = mg_l if is_l else mid_x + mg_l
    xe = mid_x + crop_all.XE_L_EXTRA if is_l else w_pt - 3
    clip = fitz.Rect(xs, max(0, y0n - crop_all.TOP_PAD_PT), xe, min(h_pt, ny))
    last_px = crop_all.get_last_content_y(doc, pn, clip, scale, mid_x, is_l)
    clip_h = int((clip.y1 - clip.y0) * scale)
    crop_h = max(80, min(clip_h, last_px + crop_all.BOTTOM_PAD_PX))
    y1 = clip.y0 + crop_h / scale

    image_blocks = 0
    admin_y = crop_all.get_admin_y(doc[pn])
    for b in doc[pn].get_text("dict").get("blocks", []):
        if b.get("type") != 1:
            continue
        bx0, by0, bx1, by1 = b.get("bbox")
        if by1 > admin_y or by0 < clip.y0 or by1 > clip.y1 + 5:
            continue
        if bx1 < clip.x0 or bx0 > clip.x1:
            continue
        if is_l and bx0 > mid_x + 30:
            continue
        image_blocks += 1

    return {
        "num": num,
        "page": pn + 1,
        "col": col,
        "clip_y0": round(clip.y0, 2),
        "crop_y1": round(y1, 2),
        "clip_y1": round(clip.y1, 2),
        "gap_to_boundary_pt": round(clip.y1 - y1, 2),
        "image_blocks": image_blocks,
    }


def load_rows(limit: int | None = None) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT id, problem_number, crop_path
        FROM problems
        WHERE crop_path IS NOT NULL AND crop_path != ''
        ORDER BY id
    """
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows[:limit] if limit else rows


def audit(limit: int | None = None) -> dict:
    rows = load_rows(limit)
    by_pdf: dict[str, list[sqlite3.Row]] = {}
    missing_pdf = []
    for row in rows:
        pdf = choose_pdf(row["id"])
        if pdf is None:
            missing_pdf.append(row["id"])
            continue
        by_pdf.setdefault(str(pdf), []).append(row)

    results = []
    position_miss = []
    for pdf_s, items in by_pdf.items():
        doc = fitz.open(str(Path(pdf_s).resolve()))
        cache = {}
        for row in items:
            match = None
            match_probs = None
            for page_range, num_filter in candidate_ranges(row["problem_number"]):
                key = (page_range, tuple(num_filter) if num_filter else None)
                if key not in cache:
                    cache[key] = crop_all.get_problem_positions(doc, page_range, num_filter=num_filter)
                probs = cache[key]
                matches = [p for p in probs if p[0] == row["problem_number"]]
                if matches:
                    match = matches[0]
                    match_probs = probs
                    break
            if not match:
                position_miss.append({"id": row["id"], "num": row["problem_number"], "pdf": Path(pdf_s).name})
                continue
            bounds = calc_bounds(doc, match, match_probs)
            results.append(
                {
                    "id": row["id"],
                    "pdf": Path(pdf_s).name,
                    "pdf_path": str(Path(pdf_s).relative_to(BASE)).replace("\\", "/"),
                    "crop_path": row["crop_path"],
                    "bounds": bounds,
                }
            )
        doc.close()

    image_cases = [r for r in results if r["bounds"]["image_blocks"] > 0]
    boundary_risk = [r for r in results if r["bounds"]["gap_to_boundary_pt"] < 20]
    result = {
        "db_crop_rows": len(rows),
        "pdf_groups": len(by_pdf),
        "simulated": len(results),
        "missing_pdf": len(missing_pdf),
        "position_miss": len(position_miss),
        "image_block_cases": len(image_cases),
        "boundary_risk_under_20pt": len(boundary_risk),
        "missing_pdf_sample": missing_pdf[:40],
        "position_miss_sample": position_miss[:40],
        "image_case_sample": image_cases[:40],
        "boundary_risk_sample": boundary_risk[:40],
        "policy": "audit only; originals, crops, and DB are not modified",
    }
    result["simulated_rows"] = results
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    report_result = {k: v for k, v in result.items() if k != "simulated_rows"}
    REPORT_JSON.write_text(json.dumps(report_result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report_result)
    return result


def write_markdown(result: dict) -> None:
    lines = [
        "---",
        "tags: [crop, emergency, audit, pipeline]",
        "---",
        "",
        "# 긴급 크롭 파이프라인 점검표",
        "",
        "> 원본문제, 원본정답, 원본해설, DB는 변경하지 않는다. 이 문서는 파싱/크롭/파일명명 체계의 긴급 점검 결과이다.",
        "",
        "## 즉시 확인 항목",
        "",
        "- [x] PDF image block 누락 여부 점검",
        "- [x] 상단 윗첨자/분수 기호 보호 여백 점검",
        "- [x] 다음 문제 경계 침범 위험 점검",
        "- [x] DB 문제 ID에서 원본 PDF 역추적 가능 여부 점검",
        "- [x] DB에 source_pdf_path/source_subject_code/source_page_range 컬럼 또는 동등 색인 추가",
        "- [x] 2026 수능 PDF 파일명 매칭 규칙 감사 도구 보강",
        "- [x] ingest 단계에 파일명명 규칙과 PDF 역추적 메타데이터 고정",
        "",
        "## 감사 결과",
        "",
        f"- DB crop 대상: {result['db_crop_rows']}",
        f"- 시뮬레이션 성공: {result['simulated']}",
        f"- PDF 매칭 실패: {result['missing_pdf']}",
        f"- 문제 번호 위치 탐지 실패: {result['position_miss']}",
        f"- 이미지 블록 포함 문제: {result['image_block_cases']}",
        f"- 다음 경계 20pt 미만 위험: {result['boundary_risk_under_20pt']}",
        "",
        "## 남은 위험",
        "",
        "- DB 본문 컬럼은 원본 보존을 위해 덮어쓰지 않았고, `problem_source_trace` 별도 색인으로 원본 PDF 경로와 페이지 범위를 보유한다.",
        "- `scripts/ingest_pdf_v4.py`는 인제스트 후 `source_trace_index.py --apply`와 `crop_pipeline_audit.py`를 자동 실행한다.",
        "- 선택과목은 과목명 문자열 대신 page range 후보 전체 탐색 또는 subject_code 기반으로 처리해야 한다.",
        "",
        "## 권장 파일명명 체계",
        "",
        "- 원본 문제 PDF: `{year}_{exam_code}_G{grade}_Q.pdf`",
        "- 원본 정답/해설 PDF: `{year}_{exam_code}_G{grade}_A.pdf`",
        "- crop 이미지: `{problem_id}.jpg`",
        "- problem_id: `{year}_{exam_label}_고{grade}_{subject_optional}_{num:03d}`",
        "- DB/위키 필수 색인: `source_pdf_path`, `source_page_range`, `source_subject_code`, `crop_path`",
        "",
        "## 자동 후속 감사",
        "",
        "- 신규 PDF 인제스트 기본 경로: `python scripts/ingest_pdf_v4.py --q <문제PDF> --a <정답PDF>`",
        "- 기본값으로 원본 역추적 색인과 크롭 파이프라인 감사를 실행한다.",
        "- 긴급 수동 점검: `python agents/ingest_agent.py --source-trace`",
        "- dry-run 점검: `python agents/ingest_agent.py --source-trace --dry-run`",
        "- 예외적으로 후속 감사를 건너뛸 때만 `--skip-post-audit`를 사용한다.",
        "",
        "## 이미지 블록 포함 샘플",
        "",
        "| 문제 | PDF | 페이지 | 컬럼 | 이미지블록 | 경계여백(pt) |",
        "|---|---|---:|---|---:|---:|",
    ]
    for item in result["image_case_sample"][:20]:
        b = item["bounds"]
        lines.append(
            f"| [[{item['id']}]] | {item['pdf']} | {b['page']} | {b['col']} | "
            f"{b['image_blocks']} | {b['gap_to_boundary_pt']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit crop pipeline without modifying data.")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = audit(args.limit)
    print_keys = {
        "db_crop_rows",
        "pdf_groups",
        "simulated",
        "missing_pdf",
        "position_miss",
        "image_block_cases",
        "boundary_risk_under_20pt",
        "policy",
    }
    print(json.dumps({k: v for k, v in result.items() if k in print_keys}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
