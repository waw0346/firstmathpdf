#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Math Problem Wiki — 연도별 자료 추가 파이프라인
새 연도(예: 2026)의 수능/모의고사 PDF를 추가하는 원클릭 도구

사용법:
  # 1단계: 준비 확인 (PDF 놓기 전에 먼저 실행)
  python scripts/add_year.py --year 2026 --check

  # 2단계: PDF 놓은 후 전체 파이프라인 실행
  python scripts/add_year.py --year 2026 --pdf sources/2026/2026수능_수학문제.pdf

  # 특정 단계만 실행
  python scripts/add_year.py --year 2026 --step ingest   # DB 저장
  python scripts/add_year.py --year 2026 --step render   # 크롭 이미지
  python scripts/add_year.py --year 2026 --step embed    # 유사문제 계산
  python scripts/add_year.py --year 2026 --step wiki     # 위키 업데이트
  python scripts/add_year.py --year 2026 --step all      # 전체

  # 크롭 좌표 템플릿 출력 (처음 추가 시)
  python scripts/add_year.py --year 2026 --template

파일 네이밍 규칙 (자동 인식):
  sources/{year}/{year}수능_수학문제.pdf        ← 수능
  sources/{year}/{year}_3월모의_수학문제.pdf    ← 3월 모의
  sources/{year}/{year}_6월모의_수학문제.pdf    ← 6월 모의
  sources/{year}/{year}_9월모의_수학문제.pdf    ← 9월 모의
  sources/{year}/{year}_분당중_3학년_기말.pdf   ← 학교시험
============================================================
"""

import sys, os, json, shutil, sqlite3, argparse, subprocess, tempfile
from pathlib import Path
from datetime import datetime

# Windows/Linux 공통 임시 디렉토리
TMP_DIR = Path(tempfile.gettempdir())

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

# ──────────────────────────────────────────────────────────────
# 색상 출력 (터미널)
# ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✅{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠️ {RESET} {msg}")
def err(msg):  print(f"  {RED}❌{RESET} {msg}")
def info(msg): print(f"  {CYAN}ℹ️ {RESET} {msg}")
def head(msg): print(f"\n{BOLD}{'='*55}{RESET}\n{BOLD}  {msg}{RESET}\n{'='*55}")


# ──────────────────────────────────────────────────────────────
# 1. 준비 상태 점검
# ──────────────────────────────────────────────────────────────
def check_prerequisites(year: str) -> bool:
    head(f"📋 {year}년 추가 준비 점검")
    all_ok = True

    # 1) sources/{year}/ 폴더
    year_dir = BASE_DIR / "sources" / year
    if year_dir.exists():
        ok(f"sources/{year}/ 폴더 존재")
    else:
        year_dir.mkdir(parents=True)
        warn(f"sources/{year}/ 폴더 생성됨 — PDF를 여기에 놓으세요")

    # 2) PDF 파일
    pdfs = list(year_dir.glob("*.pdf"))
    if pdfs:
        for pdf in pdfs:
            ok(f"PDF 발견: {pdf.name} ({pdf.stat().st_size//1024}KB)")
    else:
        err(f"PDF 없음 — sources/{year}/ 에 PDF를 복사하세요")
        print(f"\n  📁 위치: {year_dir}")
        print(f"  📝 예시 파일명: {year}수능_수학문제.pdf")
        all_ok = False

    # 3) DB 존재
    db = BASE_DIR / "db" / "problems.db"
    if db.exists() and db.stat().st_size > 0:
        tmp = TMP_DIR / "check_year.db"
        shutil.copy(db, tmp)
        conn = sqlite3.connect(tmp)
        count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        conn.close()
        ok(f"DB 정상 ({count}개 기존 문제)")
    else:
        err("DB 손상 또는 없음 — Senior Engineer 복구 실행 필요")
        all_ok = False

    # 4) ANTHROPIC_API_KEY
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        ok(f"ANTHROPIC_API_KEY 설정됨 ({api_key[:8]}...)")
    else:
        warn("ANTHROPIC_API_KEY 없음 — --manual 모드로 인제스트 가능")
        print(f"\n  🔑 API 키 설정 방법:")
        print(f"     Windows: set ANTHROPIC_API_KEY=sk-ant-...")
        print(f"     혹은 .env 파일에: ANTHROPIC_API_KEY=sk-ant-...")

    # 5) crop_map_{year}.py 존재?
    crop_map = BASE_DIR / "sources" / year / f"crop_map_{year}.py"
    if crop_map.exists():
        ok(f"crop_map_{year}.py 존재 (크롭 좌표 정의됨)")
    else:
        warn(f"crop_map_{year}.py 없음")
        print(f"  → python scripts/add_year.py --year {year} --template 로 템플릿 생성")

    print(f"\n{'─'*55}")
    if all_ok:
        ok(f"{year}년 추가 준비 완료! --step all 로 실행하세요")
    else:
        warn("위 항목을 먼저 해결하세요")
    return all_ok


# ──────────────────────────────────────────────────────────────
# 2. 크롭 좌표 템플릿 생성
# ──────────────────────────────────────────────────────────────
def generate_crop_template(year: str):
    """sources/{year}/crop_map_{year}.py 생성"""
    head(f"📐 {year}년 크롭 좌표 템플릿 생성")

    out_path = BASE_DIR / "sources" / year / f"crop_map_{year}.py"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    template = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{year}년 수능 수학문제 — 문제별 PDF 페이지·크롭 좌표 정의
============================================================
작성 방법:
  1. PDF를 열어 각 문제가 몇 페이지에 있는지 확인
  2. page_idx: 0-based (1페이지 = 0, 2페이지 = 1, ...)
  3. y_top, y_bot: 해당 페이지 높이 대비 비율 (0.0~1.0)
     - 0.0 = 페이지 맨 위  /  1.0 = 페이지 맨 아래
     - 예) 페이지 위쪽 절반 = [0.05, 0.52]
     - 예) 페이지 아래쪽 절반 = [0.52, 0.98]

팁: PDF 뷰어에서 문제 위치를 확인한 후 좌표를 조정하세요.
    처음엔 대략 입력하고 render_pages.py 실행 후 이미지 확인!
============================================================
"""

# {year}수능 수학문제.pdf 기준
# 형식: "문제_ID": ("PDF파일명.pdf", page_idx, [y_top, y_bot])
PROBLEM_PAGE_MAP_{year} = {{
    # ── 공통 (1~15번) ──────────────────────────────────────────
    "{year}_수능_고3_001": ("{year}수능_수학문제.pdf", 0, [0.08, 0.32]),
    "{year}_수능_고3_002": ("{year}수능_수학문제.pdf", 0, [0.32, 0.58]),
    "{year}_수능_고3_003": ("{year}수능_수학문제.pdf", 0, [0.58, 0.80]),
    "{year}_수능_고3_004": ("{year}수능_수학문제.pdf", 0, [0.80, 1.00]),

    "{year}_수능_고3_005": ("{year}수능_수학문제.pdf", 1, [0.05, 0.30]),
    "{year}_수능_고3_006": ("{year}수능_수학문제.pdf", 1, [0.30, 0.58]),
    "{year}_수능_고3_007": ("{year}수능_수학문제.pdf", 1, [0.58, 0.90]),

    "{year}_수능_고3_008": ("{year}수능_수학문제.pdf", 2, [0.05, 0.28]),
    "{year}_수능_고3_009": ("{year}수능_수학문제.pdf", 2, [0.28, 0.60]),
    "{year}_수능_고3_010": ("{year}수능_수학문제.pdf", 2, [0.60, 0.95]),

    "{year}_수능_고3_011": ("{year}수능_수학문제.pdf", 3, [0.05, 0.50]),
    "{year}_수능_고3_012": ("{year}수능_수학문제.pdf", 3, [0.50, 0.95]),

    "{year}_수능_고3_013": ("{year}수능_수학문제.pdf", 4, [0.05, 0.52]),
    "{year}_수능_고3_014": ("{year}수능_수학문제.pdf", 4, [0.52, 0.95]),

    "{year}_수능_고3_015": ("{year}수능_수학문제.pdf", 5, [0.05, 0.35]),

    # ── 공통 단답형 (16~22번) ──────────────────────────────────
    "{year}_수능_고3_016": ("{year}수능_수학문제.pdf", 5, [0.35, 0.65]),
    "{year}_수능_고3_017": ("{year}수능_수학문제.pdf", 5, [0.65, 0.95]),

    "{year}_수능_고3_018": ("{year}수능_수학문제.pdf", 6, [0.05, 0.38]),
    "{year}_수능_고3_019": ("{year}수능_수학문제.pdf", 6, [0.38, 0.68]),
    "{year}_수능_고3_020": ("{year}수능_수학문제.pdf", 6, [0.68, 0.98]),

    "{year}_수능_고3_021": ("{year}수능_수학문제.pdf", 7, [0.05, 0.52]),
    "{year}_수능_고3_022": ("{year}수능_수학문제.pdf", 7, [0.52, 0.98]),

    # ── 확률과 통계 선택 (23~30번) ─────────────────────────────
    "{year}_수능_고3_확통_023": ("{year}수능_수학문제.pdf", 8,  [0.05, 0.45]),
    "{year}_수능_고3_확통_024": ("{year}수능_수학문제.pdf", 8,  [0.45, 0.98]),
    "{year}_수능_고3_확통_025": ("{year}수능_수학문제.pdf", 9,  [0.05, 0.45]),
    "{year}_수능_고3_확통_026": ("{year}수능_수학문제.pdf", 9,  [0.45, 0.98]),
    "{year}_수능_고3_확통_027": ("{year}수능_수학문제.pdf", 10, [0.05, 0.45]),
    "{year}_수능_고3_확통_028": ("{year}수능_수학문제.pdf", 10, [0.45, 0.98]),
    "{year}_수능_고3_확통_029": ("{year}수능_수학문제.pdf", 11, [0.05, 0.52]),
    "{year}_수능_고3_확통_030": ("{year}수능_수학문제.pdf", 11, [0.52, 0.98]),

    # ── 미적분 선택 (23~30번) ───────────────────────────────────
    "{year}_수능_고3_미적_023": ("{year}수능_수학문제.pdf", 12, [0.05, 0.45]),
    "{year}_수능_고3_미적_024": ("{year}수능_수학문제.pdf", 12, [0.45, 0.98]),
    "{year}_수능_고3_미적_025": ("{year}수능_수학문제.pdf", 13, [0.05, 0.45]),
    "{year}_수능_고3_미적_026": ("{year}수능_수학문제.pdf", 13, [0.45, 0.98]),
    "{year}_수능_고3_미적_027": ("{year}수능_수학문제.pdf", 14, [0.05, 0.45]),
    "{year}_수능_고3_미적_028": ("{year}수능_수학문제.pdf", 14, [0.45, 0.98]),
    "{year}_수능_고3_미적_029": ("{year}수능_수학문제.pdf", 15, [0.05, 0.52]),
    "{year}_수능_고3_미적_030": ("{year}수능_수학문제.pdf", 15, [0.52, 0.98]),

    # ── 기하 선택 (23~30번) ─────────────────────────────────────
    "{year}_수능_고3_기하_023": ("{year}수능_수학문제.pdf", 16, [0.05, 0.45]),
    "{year}_수능_고3_기하_024": ("{year}수능_수학문제.pdf", 16, [0.45, 0.98]),
    "{year}_수능_고3_기하_025": ("{year}수능_수학문제.pdf", 17, [0.05, 0.45]),
    "{year}_수능_고3_기하_026": ("{year}수능_수학문제.pdf", 17, [0.45, 0.98]),
    "{year}_수능_고3_기하_027": ("{year}수능_수학문제.pdf", 18, [0.05, 0.45]),
    "{year}_수능_고3_기하_028": ("{year}수능_수학문제.pdf", 18, [0.45, 0.98]),
    "{year}_수능_고3_기하_029": ("{year}수능_수학문제.pdf", 19, [0.05, 0.52]),
    "{year}_수능_고3_기하_030": ("{year}수능_수학문제.pdf", 19, [0.52, 0.98]),
}}

# 이 파일은 scripts/add_year.py --step render 가 자동으로 읽어 사용합니다
# 좌표 조정 후 다시 실행하면 크롭 이미지가 재생성됩니다
'''

    out_path.write_text(template, encoding="utf-8")
    ok(f"템플릿 생성: {out_path}")
    print(f"\n  📝 {out_path} 를 열어 PDF 실제 좌표로 수정하세요")
    print(f"  💡 PDF를 Adobe Reader / 브라우저로 열어서 각 문제 위치 확인 후 y값 조정")


# ──────────────────────────────────────────────────────────────
# 3. STEP 1 — 인제스트 (DB 저장)
# ──────────────────────────────────────────────────────────────
def step_ingest(year: str, pdf_path: Path = None, manual: bool = False):
    head(f"📥 STEP 1: {year}년 인제스트 (DB 저장)")

    year_dir = BASE_DIR / "sources" / year
    pdfs = [pdf_path] if pdf_path else list(year_dir.glob("*.pdf"))

    if not pdfs:
        err(f"sources/{year}/ 에 PDF 없음")
        return False

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    for pdf in pdfs:
        info(f"처리: {pdf.name}")

        if not api_key or manual:
            # API 키 없으면 --dry-run 으로 문제 수 파악만
            warn("ANTHROPIC_API_KEY 없음 → dry-run 미리보기 실행")
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "scripts" / "ingest.py"),
                 "--pdf", str(pdf), "--dry-run"],
                capture_output=True, text=True, cwd=BASE_DIR,
                env={**os.environ}
            )
            print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
            if result.returncode != 0:
                warn(f"ingest 오류 (dry-run): {result.stderr[:300]}")
            warn("실제 저장을 위해 ANTHROPIC_API_KEY 환경변수를 설정하세요:")
            print(f"     Windows CMD: set ANTHROPIC_API_KEY=sk-ant-...")
            print(f"     PowerShell:  $env:ANTHROPIC_API_KEY='sk-ant-...'")
        else:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "scripts" / "ingest.py"),
                 "--pdf", str(pdf)],
                capture_output=True, text=True, cwd=BASE_DIR,
                env={**os.environ}
            )
            if result.returncode == 0:
                ok(f"{pdf.name} 인제스트 완료")
                print(result.stdout[-1500:])
            else:
                err(f"인제스트 실패: {result.stderr[:500]}")
                return False

    return True


# ──────────────────────────────────────────────────────────────
# 4. STEP 2 — 렌더 (PDF → 크롭 이미지)
# ──────────────────────────────────────────────────────────────
def step_render(year: str, dpi: int = 200):
    head(f"🖼️  STEP 2: {year}년 크롭 이미지 생성")

    # crop_map_{year}.py 로드
    crop_map_path = BASE_DIR / "sources" / year / f"crop_map_{year}.py"
    if not crop_map_path.exists():
        warn(f"crop_map_{year}.py 없음 → 템플릿 자동 생성")
        generate_crop_template(year)
        warn("crop_map 파일의 좌표를 실제 PDF 기준으로 수정 후 다시 실행하세요")
        return False

    # 동적 임포트
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"crop_map_{year}", crop_map_path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    problem_map = getattr(mod, f"PROBLEM_PAGE_MAP_{year}", None)

    if not problem_map:
        err(f"PROBLEM_PAGE_MAP_{year} 변수를 crop_map_{year}.py 에서 찾을 수 없음")
        return False

    info(f"{len(problem_map)}개 문제 매핑 로드됨")

    # render_pages.py 직접 호출 (동적 맵 주입)
    try:
        import fitz
    except ImportError:
        err("PyMuPDF 미설치: pip install PyMuPDF --break-system-packages")
        return False

    crops_dir = BASE_DIR / "sources" / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = BASE_DIR / "sources" / "pages" / year
    pages_dir.mkdir(parents=True, exist_ok=True)
    mat_crop  = fitz.Matrix(dpi / 72, dpi / 72)
    mat_page  = fitz.Matrix(150 / 72, 150 / 72)

    # PDF 그룹화
    pdf_groups: dict = {}
    for pid, (pdf_name, page_idx, y_ratio) in problem_map.items():
        pdf_groups.setdefault(pdf_name, []).append((pid, page_idx, y_ratio))

    saved_crops, saved_pages = 0, 0

    for pdf_name, items in pdf_groups.items():
        pdf_path = BASE_DIR / "sources" / year / pdf_name
        if not pdf_path.exists():
            err(f"PDF 없음: {pdf_path}")
            continue

        doc = fitz.open(pdf_path)
        info(f"처리: {pdf_name} ({len(doc)}페이지)")

        # 페이지 이미지
        for i, page in enumerate(doc):
            out = pages_dir / f"{pdf_path.stem}_p{i+1:02d}.jpg"
            pix = page.get_pixmap(matrix=mat_page, alpha=False)
            pix.save(out)
            saved_pages += 1

        # 크롭 이미지
        for pid, page_idx, (y_top, y_bot) in items:
            if page_idx >= len(doc):
                warn(f"페이지 {page_idx+1} 없음 → {pid}")
                continue
            page = doc[page_idx]
            w, h = page.rect.width, page.rect.height
            margin_x = w * 0.03
            clip = fitz.Rect(margin_x, h*y_top, w-margin_x, h*y_bot)
            pix  = page.get_pixmap(matrix=mat_crop, clip=clip, alpha=False)
            out  = crops_dir / f"{pid}.jpg"
            pix.save(out)
            size_kb = out.stat().st_size // 1024
            print(f"    ✅ {pid}.jpg  ({size_kb}KB, page {page_idx+1})")
            saved_crops += 1

        doc.close()

    # DB에 crop_path, page_number 업데이트
    _update_db_crop_paths(problem_map)

    ok(f"페이지 이미지 {saved_pages}장, 크롭 {saved_crops}개 저장 완료")
    return True


def _update_db_crop_paths(problem_map: dict):
    """DB crops/page_number 컬럼 업데이트"""
    db_src = BASE_DIR / "db" / "problems.db"
    if not db_src.exists() or db_src.stat().st_size == 0:
        warn("DB 없음 — crop_path 업데이트 건너뜀")
        return
    tmp = TMP_DIR / "add_year_work.db"
    shutil.copy(db_src, tmp)
    conn = sqlite3.connect(tmp)
    # 컬럼 추가 (없을 때만)
    existing = [r[1] for r in conn.execute("PRAGMA table_info(problems)").fetchall()]
    for col in ["page_number INTEGER", "crop_path TEXT"]:
        if col.split()[0] not in existing:
            conn.execute(f"ALTER TABLE problems ADD COLUMN {col}")
    updated = 0
    for pid, (_, page_idx, _) in problem_map.items():
        conn.execute(
            "UPDATE problems SET page_number=?, crop_path=? WHERE id=?",
            (page_idx+1, f"sources/crops/{pid}.jpg", pid)
        )
        updated += 1
    conn.commit()
    conn.close()
    shutil.copy(tmp, db_src)
    info(f"DB crop_path 업데이트: {updated}건")


# ──────────────────────────────────────────────────────────────
# 5. STEP 3 — 임베딩 (유사문제 재계산)
# ──────────────────────────────────────────────────────────────
def step_embed():
    head("🔍 STEP 3: 유사문제 재계산 (전체)")

    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "embed_simple.py"), "--build"],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if result.returncode == 0:
        ok("유사문제 임베딩 완료")
        # 결과 요약 출력
        lines = result.stdout.strip().split("\n")
        for line in lines[-10:]:
            print(f"  {line}")
    else:
        err(f"임베딩 실패: {result.stderr[:400]}")
        return False
    return True


# ──────────────────────────────────────────────────────────────
# 6. STEP 4 — 위키 업데이트
# ──────────────────────────────────────────────────────────────
def step_wiki(year: str):
    head(f"📚 STEP 4: {year}년 위키 페이지 생성/업데이트")

    result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "wiki_builder.py"), "--all"],
        capture_output=True, text=True, cwd=BASE_DIR
    )
    if result.returncode == 0:
        ok("위키 업데이트 완료")
        lines = result.stdout.strip().split("\n")
        for line in lines[-8:]:
            print(f"  {line}")
    else:
        warn(f"위키 빌더 오류 (무시 가능): {result.stderr[:300]}")
    return True


# ──────────────────────────────────────────────────────────────
# 7. 최종 요약
# ──────────────────────────────────────────────────────────────
def print_summary(year: str):
    head(f"📊 {year}년 추가 완료 — 최종 현황")

    db = BASE_DIR / "db" / "problems.db"
    if not db.exists() or db.stat().st_size == 0:
        err("DB 없음")
        return

    tmp = TMP_DIR / "summary_check.db"
    shutil.copy(db, tmp)
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row

    total   = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    yr_cnt  = conn.execute(
        "SELECT COUNT(*) FROM problems WHERE year=?", (int(year),)
    ).fetchone()[0]
    similar = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]
    conn.close()

    crops  = len(list((BASE_DIR / "sources" / "crops").glob("*.jpg")))
    wikis  = len(list((BASE_DIR / "wiki" / "problems").glob("*.md")))

    print(f"  {'─'*45}")
    print(f"  전체 문제:       {total}개 (기존 + {yr_cnt}개 신규)")
    print(f"  유사관계:        {similar}쌍")
    print(f"  크롭 이미지:     {crops}개")
    print(f"  위키 .md:        {wikis}개")
    print(f"  {'─'*45}")
    ok("모든 단계 완료!")
    print(f"\n  🌐 뷰어 열기: {BASE_DIR / 'wiki' / 'problem_viewer.html'}")
    print(f"  📊 대시보드:  {BASE_DIR / 'wiki' / 'agent_dashboard.html'}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="연도별 수학 문제 추가 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/add_year.py --year 2026 --check
  python scripts/add_year.py --year 2026 --template
  python scripts/add_year.py --year 2026 --pdf sources/2026/2026수능_수학문제.pdf
  python scripts/add_year.py --year 2026 --step all
  python scripts/add_year.py --year 2026 --step render --dpi 300
        """
    )
    parser.add_argument("--year",     required=True, help="추가할 연도 (예: 2026)")
    parser.add_argument("--pdf",      type=Path, help="특정 PDF 파일 경로")
    parser.add_argument("--check",    action="store_true", help="준비 상태 점검만")
    parser.add_argument("--template", action="store_true", help="크롭 좌표 템플릿 생성")
    parser.add_argument("--step",     choices=["ingest","render","embed","wiki","all"],
                                      help="실행할 단계")
    parser.add_argument("--dpi",      type=int, default=200, help="크롭 해상도 (기본 200)")
    parser.add_argument("--manual",   action="store_true", help="API 없이 dry-run 미리보기")
    args = parser.parse_args()

    year = args.year

    if args.check:
        check_prerequisites(year)

    elif args.template:
        generate_crop_template(year)

    elif args.step or args.pdf:
        step = args.step or "all"

        if step in ("ingest", "all"):
            step_ingest(year, args.pdf, args.manual)

        if step in ("render", "all"):
            step_render(year, args.dpi)

        if step in ("embed", "all"):
            step_embed()

        if step in ("wiki", "all"):
            step_wiki(year)

        if step == "all":
            print_summary(year)

    else:
        parser.print_help()
