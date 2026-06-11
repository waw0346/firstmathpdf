#!/usr/bin/env python3
"""
============================================================
Math Problem Wiki — PDF Ingestion Pipeline
수학 문제 위키 — PDF 인제스트 파이프라인

사용법:
  python ingest.py --pdf sources/2023/분당중_3학년_1학기기말.pdf
  python ingest.py --dir sources/2023/   (폴더 전체 처리)
  python ingest.py --pdf <파일> --dry-run  (실제 저장 없이 미리보기)

요구사항:
  pip install pymupdf pdfplumber anthropic pyyaml rich tqdm
  pip install pillow pytesseract  # OCR 필요 시
  환경변수: ANTHROPIC_API_KEY
============================================================
"""

import os, sys, re, json, yaml, hashlib, sqlite3, argparse, logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

try:
    import fitz          # PyMuPDF
    import pdfplumber
    import anthropic
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from tqdm import tqdm
except ImportError as e:
    print(f"[오류] 패키지 미설치: {e}")
    print("다음 명령어로 설치하세요:")
    print("  pip install pymupdf pdfplumber anthropic pyyaml rich tqdm")
    sys.exit(1)

console = Console()
BASE_DIR = Path(__file__).parent.parent
SCHEMA   = yaml.safe_load((BASE_DIR / "schema.yaml").read_text(encoding="utf-8"))
CONFIG   = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))

# ─── 로깅 ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "logs" / "ingest.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 1. PDF 텍스트 추출
# ──────────────────────────────────────────────────────────────
def extract_pdf_text(pdf_path: Path) -> list[dict]:
    """PDF에서 페이지별 텍스트+이미지 추출"""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                # 표(테이블) 추출
                tables = page.extract_tables() or []
                pages.append({
                    "page_num": i + 1,
                    "text": text.strip(),
                    "tables": tables,
                    "has_image": False
                })
    except Exception as e:
        log.warning(f"pdfplumber 실패, PyMuPDF로 재시도: {e}")
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text("text")
            has_img = len(page.get_images()) > 0
            pages.append({
                "page_num": i + 1,
                "text": text.strip(),
                "tables": [],
                "has_image": has_img
            })
    return pages


# ──────────────────────────────────────────────────────────────
# 2. 문제 단위 분리
# ──────────────────────────────────────────────────────────────
def split_into_problems(pages: list[dict]) -> list[dict]:
    """페이지 텍스트를 개별 문제로 분리"""
    full_text = "\n".join(p["text"] for p in pages if p["text"])

    # 문제 구분자 패턴
    patterns = CONFIG["processing"]["problem_separator_patterns"]
    separator = re.compile(
        r"(?=(?:" + "|".join(patterns) + r"))",
        re.MULTILINE
    )

    raw_problems = separator.split(full_text)
    problems = []

    for idx, raw in enumerate(raw_problems):
        raw = raw.strip()
        if len(raw) < CONFIG["processing"]["min_problem_length"]:
            continue

        # 문제 번호 추출
        num_match = re.match(r"^[\[\(]?(\d+)[\]\).]?\s*", raw)
        prob_num = int(num_match.group(1)) if num_match else idx + 1

        problems.append({
            "raw_text": raw,
            "problem_number": prob_num,
            "char_hash": hashlib.md5(raw.encode()).hexdigest()[:8]
        })

    log.info(f"  → {len(problems)}개 문제 분리 완료")
    return problems


# ──────────────────────────────────────────────────────────────
# 3. Claude API로 메타데이터 추출 및 분류
# ──────────────────────────────────────────────────────────────
CLASSIFY_PROMPT = """당신은 수학 교육 전문가입니다. 다음 수학 문제를 분석하여 JSON 형식으로 정보를 추출하세요.

문제 텍스트:
{problem_text}

파일 정보:
- 학교/기관: {school}
- 연도: {year}
- 시험 종류: {exam_type}
- 학년: {grade_hint}

다음 JSON 형식으로 답변하세요 (JSON 외 다른 텍스트 없이):
{{
  "title": "문제 핵심을 20자 이내로 요약",
  "domain": "수와연산|문자와식|함수|기하|확률과통계 중 하나",
  "topic": "세부 단원명",
  "concept": ["핵심개념1", "핵심개념2"],
  "difficulty": "하|중|상|최상 중 하나",
  "answer": "정답 (보기 번호 또는 숫자/식)",
  "solution_outline": "풀이 핵심 과정을 3줄 이내로",
  "solution_steps": 풀이_단계_수,
  "tags": ["추가태그1", "추가태그2"],
  "grade": "중1|중2|중3|고1|고2|고3 중 하나"
}}"""


def classify_problem(
    client: anthropic.Anthropic,
    problem: dict,
    meta: dict,
    dry_run: bool = False
) -> dict:
    """Claude API로 문제 분류"""
    if dry_run:
        return {
            "title": f"문제 {problem['problem_number']} (미리보기)",
            "domain": "문자와식",
            "topic": "이차방정식",
            "concept": ["이차방정식의 근"],
            "difficulty": "중",
            "answer": "?",
            "solution_outline": "dry-run 모드",
            "solution_steps": 3,
            "tags": [],
            "grade": meta.get("grade", "중3")
        }

    prompt = CLASSIFY_PROMPT.format(
        problem_text=problem["raw_text"][:1500],  # 토큰 절약
        school=meta.get("school", "미상"),
        year=meta.get("year", "미상"),
        exam_type=meta.get("exam_type", "미상"),
        grade_hint=meta.get("grade", "미상")
    )

    try:
        response = client.messages.create(
            model=CONFIG["api"]["anthropic"]["model"],
            max_tokens=CONFIG["api"]["anthropic"]["max_tokens"],
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # JSON 파싱
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
            if match:
                text = match.group(1)
        return json.loads(text)
    except Exception as e:
        log.error(f"분류 실패 (문제 {problem['problem_number']}): {e}")
        return {
            "title": f"문제 {problem['problem_number']}",
            "domain": "미분류",
            "topic": "미분류",
            "concept": [],
            "difficulty": "중",
            "answer": "",
            "solution_outline": "",
            "solution_steps": 0,
            "tags": ["분류오류"],
            "grade": meta.get("grade", "")
        }


# ──────────────────────────────────────────────────────────────
# 4. 마크다운 위키 페이지 생성
# ──────────────────────────────────────────────────────────────
def generate_problem_id(meta: dict, seq: int) -> str:
    """고유 문제 ID 생성: {year}_{school_abbr}_{grade}_{seq:03d}"""
    year = meta.get("year", "0000")
    school = meta.get("school", "미상")
    # 학교명 약어 (앞 4글자)
    school_abbr = re.sub(r"[학교중고등\s]", "", school)[:4]
    grade = meta.get("grade", "?").replace("학년", "")
    return f"{year}_{school_abbr}_{grade}_{seq:03d}"


def build_markdown(problem_id: str, problem: dict, classified: dict, meta: dict) -> str:
    """문제 마크다운 페이지 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    concepts_str = ", ".join(classified.get("concept", []))
    tags_str = ", ".join([
        classified.get("domain", ""),
        classified.get("topic", ""),
        classified.get("difficulty", ""),
        meta.get("school", ""),
        str(meta.get("year", "")),
        meta.get("exam_type", ""),
        *classified.get("tags", [])
    ])

    # 난이도 이모지
    diff_emoji = {"하": "🟢", "중": "🟡", "상": "🔴", "최상": "⚫"}.get(
        classified.get("difficulty", "중"), "🟡"
    )

    content = f"""---
id: {problem_id}
title: "{classified.get('title', '')}"
grade: {classified.get('grade', meta.get('grade', ''))}
domain: {classified.get('domain', '')}
topic: {classified.get('topic', '')}
concept: [{concepts_str}]
difficulty: {classified.get('difficulty', '중')}
source_type: {meta.get('source_type', '학교시험')}
year: {meta.get('year', '')}
school: {meta.get('school', '')}
exam_type: {meta.get('exam_type', '')}
answer: "{classified.get('answer', '')}"
problem_number: {problem.get('problem_number', '')}
source_pdf: {meta.get('pdf_filename', '')}
solution_steps: {classified.get('solution_steps', 0)}
tags: [{tags_str}]
similar_ids: []
created_at: {now}
---

# {classified.get('title', f'문제 {problem.get("problem_number", "")}')}

{diff_emoji} **난이도**: {classified.get('difficulty', '중')} | 📚 **단원**: {classified.get('topic', '')} | 🏫 **출처**: {meta.get('school', '')} {meta.get('year', '')} {meta.get('exam_type', '')}

---

## 📝 문제

{problem['raw_text']}

---

## ✅ 정답

**{classified.get('answer', '?')}**

---

## 💡 풀이 해설

{classified.get('solution_outline', '(풀이 미생성)')}

---

## 🔗 유사 문제

> 유사 문제는 `python scripts/search.py --similar {problem_id}` 명령으로 검색하세요.
> 위키 업데이트 후 자동으로 채워집니다.

---

## 📎 메타데이터

| 항목 | 내용 |
|------|------|
| 문제 ID | `{problem_id}` |
| 학년 | {classified.get('grade', '')} |
| 대영역 | {classified.get('domain', '')} |
| 단원 | {classified.get('topic', '')} |
| 핵심 개념 | {concepts_str} |
| 난이도 | {classified.get('difficulty', '')} |
| 출처 | {meta.get('school', '')} |
| 연도 | {meta.get('year', '')} |
| 시험 종류 | {meta.get('exam_type', '')} |
| 원문 파일 | {meta.get('pdf_filename', '')} |
"""
    return content


# ──────────────────────────────────────────────────────────────
# 5. SQLite DB 저장
# ──────────────────────────────────────────────────────────────
def init_db(db_path: Path) -> sqlite3.Connection:
    """DB 초기화"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS problems (
            id TEXT PRIMARY KEY,
            title TEXT,
            grade TEXT,
            domain TEXT,
            topic TEXT,
            concept TEXT,          -- JSON array
            difficulty TEXT,
            source_type TEXT,
            year INTEGER,
            school TEXT,
            exam_type TEXT,
            answer TEXT,
            problem_number INTEGER,
            source_pdf TEXT,
            solution_steps INTEGER,
            tags TEXT,             -- JSON array
            raw_text TEXT,
            md_path TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS similar_problems (
            problem_id TEXT,
            similar_id TEXT,
            similarity REAL,
            PRIMARY KEY (problem_id, similar_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_domain ON problems(domain);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_topic ON problems(topic);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_school ON problems(school);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_year ON problems(year);
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_difficulty ON problems(difficulty);
    """)
    conn.commit()
    return conn


def save_to_db(conn: sqlite3.Connection, problem_id: str, problem: dict,
               classified: dict, meta: dict, md_path: str):
    """문제를 SQLite DB에 저장"""
    conn.execute("""
        INSERT OR REPLACE INTO problems VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        problem_id,
        classified.get("title", ""),
        classified.get("grade", meta.get("grade", "")),
        classified.get("domain", ""),
        classified.get("topic", ""),
        json.dumps(classified.get("concept", []), ensure_ascii=False),
        classified.get("difficulty", "중"),
        meta.get("source_type", "학교시험"),
        int(meta.get("year", 0)),
        meta.get("school", ""),
        meta.get("exam_type", ""),
        classified.get("answer", ""),
        problem.get("problem_number", 0),
        meta.get("pdf_filename", ""),
        classified.get("solution_steps", 0),
        json.dumps(classified.get("tags", []), ensure_ascii=False),
        problem["raw_text"],
        md_path,
        datetime.now().isoformat()
    ))
    conn.commit()


# ──────────────────────────────────────────────────────────────
# 6. 메인 파이프라인
# ──────────────────────────────────────────────────────────────
def parse_filename_meta(pdf_path: Path) -> dict:
    """
    파일명에서 메타데이터 추출
    형식 예: 2023_분당중학교_3학년_1학기기말.pdf
             2024_수능_전체.pdf
    """
    stem = pdf_path.stem
    parts = stem.split("_")

    meta = {
        "pdf_filename": pdf_path.name,
        "year": "",
        "school": "",
        "grade": "",
        "exam_type": "",
        "source_type": "학교시험"
    }

    if parts[0].isdigit() and len(parts[0]) == 4:
        meta["year"] = parts[0]
    if len(parts) > 1:
        meta["school"] = parts[1]
    if len(parts) > 2:
        meta["grade"] = parts[2]
    if len(parts) > 3:
        meta["exam_type"] = parts[3]

    # 수능/모의고사 감지
    if "수능" in stem:
        meta["source_type"] = "수능"
        meta["school"] = "수능"
    elif "모의" in stem or "모고" in stem:
        meta["source_type"] = "모의고사"

    return meta


def ingest_pdf(pdf_path: Path, dry_run: bool = False, force: bool = False):
    """단일 PDF 인제스트"""
    console.rule(f"[bold blue]📄 {pdf_path.name}")

    # API 클라이언트
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key and not dry_run:
        console.print("[red]❌ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")
        console.print("   Windows: set ANTHROPIC_API_KEY=sk-ant-...")
        console.print("   Mac/Linux: export ANTHROPIC_API_KEY=sk-ant-...")
        console.print("   저장 없이 미리보기만 하려면 --dry-run 옵션을 사용하세요.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key) if not dry_run else None

    # DB 초기화
    db_path = BASE_DIR / CONFIG["database"]["path"]
    conn = init_db(db_path)

    # 파일명 메타데이터
    meta = parse_filename_meta(pdf_path)
    console.print(f"  학교: [cyan]{meta['school']}[/]  연도: [cyan]{meta['year']}[/]  "
                  f"학년: [cyan]{meta['grade']}[/]  시험: [cyan]{meta['exam_type']}[/]")

    # 1. 텍스트 추출
    console.print("\n[1/4] PDF 텍스트 추출 중...")
    pages = extract_pdf_text(pdf_path)
    console.print(f"  → {len(pages)}페이지 추출")

    # 2. 문제 분리
    console.print("[2/4] 문제 단위 분리 중...")
    problems = split_into_problems(pages)

    if not problems:
        console.print("[red]  ⚠ 문제를 찾지 못했습니다. PDF 형식을 확인하세요.")
        return

    # 3. 분류 및 저장
    console.print(f"[3/4] {len(problems)}개 문제 분류 중 (Claude API)...")

    saved_count = 0
    with tqdm(problems, desc="  분류", unit="문제") as pbar:
        for seq, problem in enumerate(pbar, 1):
            # 이미 처리된 문제 건너뛰기
            prob_id = generate_problem_id(meta, seq)
            existing = conn.execute(
                "SELECT id FROM problems WHERE id = ?", (prob_id,)
            ).fetchone()
            if existing and not force:
                pbar.set_description(f"  건너뜀 {prob_id}")
                continue

            # Claude 분류
            classified = classify_problem(client, problem, meta, dry_run)

            # 마크다운 생성
            md_content = build_markdown(prob_id, problem, classified, meta)

            if not dry_run:
                # 파일 저장
                md_path = BASE_DIR / "wiki" / "problems" / f"{prob_id}.md"
                md_path.parent.mkdir(parents=True, exist_ok=True)
                md_path.write_text(md_content, encoding="utf-8")

                # DB 저장
                save_to_db(conn, prob_id, problem, classified, meta,
                           str(md_path.relative_to(BASE_DIR)))
                saved_count += 1
            else:
                # dry-run: 첫 3개만 미리보기 출력
                if seq <= 3:
                    console.print(f"\n[dim]─── 미리보기: {prob_id} ───[/]")
                    console.print(md_content[:800] + "...\n")

            pbar.set_description(f"  {prob_id} [{classified.get('difficulty','?')}]")

    # 4. 위키 인덱스 업데이트
    if not dry_run:
        console.print("[4/4] 위키 인덱스 업데이트 중...")
        from wiki_builder import update_indices
        update_indices(conn, meta)
        console.print(f"\n[bold green]✅ 완료! {saved_count}개 문제 저장됨[/]")
        console.print(f"   DB: {db_path}")
        console.print(f"   위키: {BASE_DIR / 'wiki' / 'problems'}")
    else:
        console.print(f"\n[yellow]🔍 Dry-run 완료. {len(problems)}개 문제 감지됨 (저장 없음)[/]")

    conn.close()


def ingest_directory(dir_path: Path, dry_run: bool = False):
    """폴더 내 모든 PDF 처리"""
    pdfs = sorted(dir_path.glob("**/*.pdf"))
    if not pdfs:
        console.print(f"[red]{dir_path}에서 PDF를 찾지 못했습니다.")
        return
    console.print(f"[bold]📁 {len(pdfs)}개 PDF 발견[/]\n")
    for pdf in pdfs:
        ingest_pdf(pdf, dry_run=dry_run)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="수학 문제 PDF 인제스트 파이프라인"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pdf",  type=Path, help="처리할 PDF 파일 경로")
    group.add_argument("--dir",  type=Path, help="처리할 폴더 (하위 PDF 전체)")
    parser.add_argument("--dry-run", action="store_true",
                        help="저장 없이 미리보기만")
    parser.add_argument("--force", action="store_true",
                        help="이미 처리된 문제도 재처리")
    args = parser.parse_args()

    if args.pdf:
        if not args.pdf.exists():
            console.print(f"[red]파일 없음: {args.pdf}")
            sys.exit(1)
        ingest_pdf(args.pdf, dry_run=args.dry_run, force=args.force)
    else:
        ingest_directory(args.dir, dry_run=args.dry_run)
