#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Math Problem Wiki — PDF 페이지 이미지 추출기
원본 PDF에서 300dpi 페이지 이미지 및 문제 크롭 이미지 생성

100% 정확도 아키텍처의 핵심:
  LLM은 메타데이터만 — 문제 자체는 원본 PDF 이미지로 표시

사용법:
  # 전체 PDF 처리 (pages/ + crops/)
  python scripts/render_pages.py --all

  # 특정 PDF만 처리
  python scripts/render_pages.py --pdf sources/2025/2025수능_수학문제.pdf

  # 페이지 이미지만 (크롭 없음)
  python scripts/render_pages.py --pages-only --pdf sources/2025/2025수능_수학문제.pdf

  # DB에 page_number 컬럼 추가
  python scripts/render_pages.py --migrate-db

출력:
  sources/pages/{year}/{pdf_stem}_p{page:02d}.jpg  — 전체 페이지 (150dpi)
  sources/crops/{problem_id}.jpg                   — 문제별 크롭 (300dpi)
============================================================
"""

import sqlite3, argparse, json, shutil, re, tempfile
from pathlib import Path
from datetime import datetime

TMP_DIR = Path(tempfile.gettempdir())

try:
    import fitz  # PyMuPDF
except ImportError:
    print("❌ PyMuPDF 필요: pip install PyMuPDF --break-system-packages")
    exit(1)

BASE_DIR   = Path(__file__).parent.parent
DB_SOURCE  = BASE_DIR / "db" / "problems.db"
PAGES_DIR  = BASE_DIR / "sources" / "pages"
CROPS_DIR  = BASE_DIR / "sources" / "crops"

# ──────────────────────────────────────────────────────────────
# 2025 수능 문제-페이지 매핑
# {problem_id: (pdf_filename, page_index_0based, [y_top_ratio, y_bottom_ratio])}
# y 비율: 페이지 높이 대비 (0.0=상단, 1.0=하단)
# ──────────────────────────────────────────────────────────────
PROBLEM_PAGE_MAP = {
    # ── 공통 (1~22번) ──────────────────────────────────────────
    "2025_수능_고3_001": ("2025수능_수학문제.pdf", 0, [0.08, 0.32]),
    "2025_수능_고3_002": ("2025수능_수학문제.pdf", 0, [0.32, 0.58]),
    "2025_수능_고3_003": ("2025수능_수학문제.pdf", 0, [0.58, 0.80]),
    "2025_수능_고3_004": ("2025수능_수학문제.pdf", 0, [0.80, 1.00]),

    "2025_수능_고3_005": ("2025수능_수학문제.pdf", 1, [0.05, 0.30]),
    "2025_수능_고3_006": ("2025수능_수학문제.pdf", 1, [0.30, 0.58]),
    "2025_수능_고3_007": ("2025수능_수학문제.pdf", 1, [0.58, 0.90]),

    "2025_수능_고3_008": ("2025수능_수학문제.pdf", 2, [0.05, 0.28]),
    "2025_수능_고3_009": ("2025수능_수학문제.pdf", 2, [0.28, 0.60]),
    "2025_수능_고3_010": ("2025수능_수학문제.pdf", 2, [0.60, 0.95]),

    "2025_수능_고3_011": ("2025수능_수학문제.pdf", 3, [0.05, 0.50]),
    "2025_수능_고3_012": ("2025수능_수학문제.pdf", 3, [0.50, 0.95]),

    "2025_수능_고3_013": ("2025수능_수학문제.pdf", 4, [0.05, 0.52]),
    "2025_수능_고3_014": ("2025수능_수학문제.pdf", 4, [0.52, 0.95]),

    "2025_수능_고3_015": ("2025수능_수학문제.pdf", 5, [0.05, 0.35]),
    "2025_수능_고3_016": ("2025수능_수학문제.pdf", 5, [0.35, 0.65]),
    "2025_수능_고3_017": ("2025수능_수학문제.pdf", 5, [0.65, 0.95]),

    "2025_수능_고3_018": ("2025수능_수학문제.pdf", 6, [0.05, 0.38]),
    "2025_수능_고3_019": ("2025수능_수학문제.pdf", 6, [0.38, 0.68]),
    "2025_수능_고3_020": ("2025수능_수학문제.pdf", 6, [0.68, 0.98]),

    "2025_수능_고3_021": ("2025수능_수학문제.pdf", 7, [0.05, 0.52]),
    "2025_수능_고3_022": ("2025수능_수학문제.pdf", 7, [0.52, 0.98]),

    # ── 확률과 통계 선택 ────────────────────────────────────────
    "2025_수능_고3_확통_023": ("2025수능_수학문제.pdf", 8,  [0.05, 0.45]),
    "2025_수능_고3_확통_028": ("2025수능_수학문제.pdf", 10, [0.45, 0.98]),

    # ── 미적분 선택 ─────────────────────────────────────────────
    "2025_수능_고3_미적_023": ("2025수능_수학문제.pdf", 12, [0.05, 0.45]),
    "2025_수능_고3_미적_028": ("2025수능_수학문제.pdf", 14, [0.45, 0.98]),

    # ── 기하 선택 ────────────────────────────────────────────────
    "2025_수능_고3_기하_023": ("2025수능_수학문제.pdf", 16, [0.05, 0.45]),
    "2025_수능_고3_기하_028": ("2025수능_수학문제.pdf", 18, [0.45, 0.98]),
}

# 문제별 페이지 번호 (1-based) 조회용
PROBLEM_PAGES_1BASED = {k: v[1]+1 for k, v in PROBLEM_PAGE_MAP.items()}


def get_db():
    """DB를 /tmp에 복사 후 작업 (VirtioFS 우회)"""
    tmp_db = TMP_DIR / "render_work.db"
    shutil.copy(DB_SOURCE, tmp_db)
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    return conn, tmp_db


def migrate_db():
    """DB에 page_number, crop_path 컬럼 추가"""
    conn, tmp_db = get_db()
    existing = [r[1] for r in conn.execute("PRAGMA table_info(problems)").fetchall()]

    added = []
    if "page_number" not in existing:
        conn.execute("ALTER TABLE problems ADD COLUMN page_number INTEGER")
        added.append("page_number")
    if "crop_path" not in existing:
        conn.execute("ALTER TABLE problems ADD COLUMN crop_path TEXT")
        added.append("crop_path")

    # 매핑에서 page_number 업데이트
    for pid, page_1b in PROBLEM_PAGES_1BASED.items():
        crop_rel = f"sources/crops/{pid}.jpg"
        conn.execute(
            "UPDATE problems SET page_number=?, crop_path=? WHERE id=?",
            (page_1b, crop_rel, pid)
        )

    conn.commit()
    conn.close()
    shutil.copy(tmp_db, DB_SOURCE)
    print(f"✅ DB 마이그레이션 완료: {added} 컬럼 추가, 매핑 업데이트")


# ──────────────────────────────────────────────────────────────
# 페이지 이미지 생성
# ──────────────────────────────────────────────────────────────
def render_pages(pdf_path: Path, dpi: int = 150) -> list[Path]:
    """PDF 전체 페이지를 JPG로 저장 (150dpi — 빠른 미리보기용)"""
    pdf_path = Path(pdf_path)
    year = pdf_path.parent.name
    out_dir = PAGES_DIR / year
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    saved = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    print(f"📄 {pdf_path.name}: {len(doc)}페이지 → {out_dir}/")
    for i, page in enumerate(doc):
        out_path = out_dir / f"{pdf_path.stem}_p{i+1:02d}.jpg"
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(out_path)
        saved.append(out_path)

    doc.close()
    print(f"   ✅ {len(saved)}장 저장 완료")
    return saved


# ──────────────────────────────────────────────────────────────
# 문제 크롭 이미지 생성
# ──────────────────────────────────────────────────────────────
def crop_problems(dpi: int = 200) -> dict[str, Path]:
    """문제별 크롭 이미지 생성 (200dpi — 인쇄 품질)"""
    CROPS_DIR.mkdir(parents=True, exist_ok=True)

    # PDF 파일별로 그룹화
    pdf_groups: dict[str, list[tuple]] = {}
    for pid, (pdf_name, page_idx, y_ratio) in PROBLEM_PAGE_MAP.items():
        if pdf_name not in pdf_groups:
            pdf_groups[pdf_name] = []
        pdf_groups[pdf_name].append((pid, page_idx, y_ratio))

    saved = {}
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    for pdf_name, items in pdf_groups.items():
        # PDF 위치 탐색
        pdf_path = None
        for src_dir in BASE_DIR.glob("sources/*/"):
            candidate = src_dir / pdf_name
            if candidate.exists():
                pdf_path = candidate
                break

        if not pdf_path:
            print(f"⚠️  PDF 없음: {pdf_name}")
            continue

        doc = fitz.open(pdf_path)
        print(f"✂️  크롭: {pdf_name}")

        for pid, page_idx, (y_top, y_bot) in items:
            if page_idx >= len(doc):
                print(f"   ⚠️  페이지 {page_idx+1} 없음 → {pid}")
                continue

            page = doc[page_idx]
            w, h = page.rect.width, page.rect.height

            # 전체 너비, y 비율로 크롭 영역 계산 (좌우 여백 조금 남김)
            margin_x = w * 0.03
            clip = fitz.Rect(
                margin_x,
                h * y_top,
                w - margin_x,
                h * y_bot
            )

            pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
            out_path = CROPS_DIR / f"{pid}.jpg"
            pix.save(out_path)
            saved[pid] = out_path
            size_kb = out_path.stat().st_size // 1024
            print(f"   ✅ {pid}.jpg  ({size_kb}KB, page {page_idx+1})")

        doc.close()

    print(f"\n✅ 크롭 완료: {len(saved)}개")
    return saved


# ──────────────────────────────────────────────────────────────
# 메타데이터 JSON 업데이트 (viewer용)
# ──────────────────────────────────────────────────────────────
def update_manifest():
    """sources/pages/manifest.json 생성 — viewer가 로드할 페이지 목록"""
    manifest = {}
    for pdf_name in set(v[0] for v in PROBLEM_PAGE_MAP.values()):
        year = "2025"  # TODO: PDF 이름에서 연도 파싱
        stem = pdf_name.replace(".pdf", "")
        pages_dir = PAGES_DIR / year
        if pages_dir.exists():
            files = sorted(pages_dir.glob(f"{stem}_p*.jpg"))
            manifest[pdf_name] = {
                "year": year,
                "pages": [str(f.relative_to(BASE_DIR)) for f in files]
            }

    out = BASE_DIR / "sources" / "pages" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ manifest.json 생성: {out}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF 페이지/크롭 이미지 생성기")
    parser.add_argument("--all",        action="store_true", help="전체 처리 (pages + crops + manifest)")
    parser.add_argument("--pdf",        help="특정 PDF 경로")
    parser.add_argument("--pages-only", action="store_true", help="페이지 이미지만 생성")
    parser.add_argument("--crops-only", action="store_true", help="크롭 이미지만 생성")
    parser.add_argument("--migrate-db", action="store_true", help="DB에 page_number/crop_path 컬럼 추가")
    parser.add_argument("--dpi",        type=int, default=200, help="크롭 해상도 (기본 200)")
    args = parser.parse_args()

    if args.migrate_db:
        migrate_db()

    if args.all or args.pages_only:
        # 모든 sources/*/*.pdf 처리
        if args.pdf:
            render_pages(Path(args.pdf), dpi=150)
        else:
            for pdf in sorted(BASE_DIR.glob("sources/**/*.pdf")):
                render_pages(pdf, dpi=150)
        update_manifest()

    if args.all or args.crops_only:
        crop_problems(dpi=args.dpi)
        migrate_db()

    if not any([args.all, args.pages_only, args.crops_only, args.migrate_db]):
        parser.print_help()
