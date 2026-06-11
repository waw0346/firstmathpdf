#!/usr/bin/env python3
"""
============================================================
Math Problem Wiki — Marp 슬라이드 생성기
수업용 문제 슬라이드를 마크다운(Marp) 형식으로 자동 생성

사용법:
  # 특정 문제 ID로 슬라이드 생성
  python scripts/marp_export.py --ids 2025_수능_고3_001 2025_수능_고3_005

  # 필터로 슬라이드 생성
  python scripts/marp_export.py --domain 함수 --difficulty 상 --limit 10

  # 수업 세트 생성 (쉬운→어려운 순)
  python scripts/marp_export.py --topic 수열 --class-mode

  # 출력 파일 지정
  python scripts/marp_export.py --domain 기하 --output slides/기하_수업.md
============================================================
"""

import sqlite3, argparse, yaml, json, tempfile
from pathlib import Path
from datetime import datetime

TMP_DIR = Path(tempfile.gettempdir())

BASE_DIR = Path(__file__).parent.parent
CONFIG   = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))

DIFF_ICON  = {"하": "🟢", "중": "🟡", "상": "🔴", "최상": "⚫"}
DIFF_COLOR = {"하": "#27ae60", "중": "#f39c12", "상": "#e74c3c", "최상": "#2c3e50"}
DIFF_ORDER = {"하": 0, "중": 1, "상": 2, "최상": 3}


def get_conn():
    """Windows/Linux 호환: 임시 폴더에 복사 후 연결"""
    import shutil
    db_src = BASE_DIR / CONFIG["database"]["path"]
    tmp_db = TMP_DIR / "marp_work.db"
    shutil.copy(db_src, tmp_db)
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_problems(ids=None, filters=None, limit=20, class_mode=False):
    """문제 목록 조회"""
    conn = get_conn()

    if ids:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM problems WHERE id IN ({placeholders})", ids
        ).fetchall()
    else:
        where_parts = []
        params = []
        if filters:
            for k, v in filters.items():
                where_parts.append(f"{k} = ?")
                params.append(v)

        sql = "SELECT * FROM problems"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        if class_mode:
            sql += " ORDER BY CASE difficulty WHEN '하' THEN 1 WHEN '중' THEN 2 WHEN '상' THEN 3 WHEN '최상' THEN 4 END"
        else:
            sql += " ORDER BY year DESC, problem_number ASC"

        sql += f" LIMIT {limit}"
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]


def get_similar_info(problem_id, conn=None):
    """유사문제 정보 조회"""
    if conn is None:
        conn = get_conn()
    rows = conn.execute("""
        SELECT sp.similar_id, sp.similarity, p.title, p.difficulty, p.year, p.school
        FROM similar_problems sp
        JOIN problems p ON sp.similar_id = p.id
        WHERE sp.problem_id = ?
        ORDER BY sp.similarity DESC
        LIMIT 3
    """, (problem_id,)).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────
# Marp 슬라이드 생성
# ──────────────────────────────────────────────────────────────
def build_marp_header(title: str, theme: str = "default") -> str:
    """Marp 프론트매터"""
    return f"""---
marp: true
theme: {theme}
paginate: true
backgroundColor: #fafafa
color: #2c3e50
header: "수학의 지름길 학원 | {title}"
footer: "© 분당 정자동 수학의 지름길 | waw0346@gmail.com"
style: |
  section {{
    font-family: 'Noto Sans KR', sans-serif;
    font-size: 22px;
  }}
  h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 8px; }}
  h2 {{ color: #34495e; }}
  .diff-하   {{ color: #27ae60; font-weight: bold; }}
  .diff-중   {{ color: #f39c12; font-weight: bold; }}
  .diff-상   {{ color: #e74c3c; font-weight: bold; }}
  .diff-최상 {{ color: #8e44ad; font-weight: bold; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #3498db; color: white; padding: 6px; }}
  td {{ padding: 6px; border: 1px solid #ddd; }}
---
"""


def build_title_slide(title: str, problems: list) -> str:
    """표지 슬라이드"""
    domains = list(set(p["domain"] for p in problems))
    difficulties = list(set(p["difficulty"] for p in problems))
    today = datetime.now().strftime("%Y년 %m월 %d일")

    return f"""
# 📚 {title}

---

| 항목 | 내용 |
|------|------|
| 총 문제 수 | **{len(problems)}문제** |
| 영역 | {", ".join(domains)} |
| 난이도 | {", ".join(difficulties)} |
| 생성일 | {today} |

> 🏫 **수학의 지름길 학원** — 분당 정자동

---
"""


def build_problem_slide(p: dict, show_answer: bool = False, show_similar: bool = True) -> str:
    """문제 슬라이드 1장"""
    diff = p.get("difficulty", "")
    icon = DIFF_ICON.get(diff, "")
    concept_str = ", ".join(json.loads(p.get("concept") or "[]"))
    tags_str = " ".join(f"`{t}`" for t in json.loads(p.get("tags") or "[]")[:4])

    slide = f"""
## {p.get('problem_number', '')}번. {p.get('title', '')}

{tags_str}

| 학년 | 영역 | 단원 | 난이도 | 출처 |
|------|------|------|--------|------|
| {p.get('grade','')} | {p.get('domain','')} | {p.get('topic','')} | {icon} **{diff}** | {p.get('school','')} {p.get('year','')} |

**핵심 개념**: {concept_str}

---

### 📝 문제

{p.get('raw_text', p.get('title', ''))[:500]}

"""

    if show_answer:
        slide += f"""
---

### ✅ 정답 및 해설

**정답**: **{p.get('answer', '')}**

{p.get('solution_hint', p.get('title', ''))}

"""

    if show_similar:
        conn = get_conn()
        similar = get_similar_info(p['id'], conn)
        if similar:
            slide += "\n### 🔗 유사 문제\n\n"
            for s in similar:
                slide += f"- `{s['similar_id']}` — {s['title']} ({s['difficulty']}, {s['year']})\n"
        slide += "\n"

    slide += "---\n"
    return slide


def build_answer_summary_slide(problems: list) -> str:
    """정답 일람표 슬라이드"""
    slide = "\n## 📋 정답 일람표\n\n"
    slide += "| 번호 | 제목 | 정답 | 난이도 |\n"
    slide += "|------|------|------|--------|\n"
    for p in problems:
        diff = p.get("difficulty", "")
        icon = DIFF_ICON.get(diff, "")
        slide += f"| {p.get('problem_number','')} | {p.get('title','')[:20]} | **{p.get('answer','')}** | {icon} {diff} |\n"
    slide += "\n---\n"
    return slide


def generate_slides(problems: list, title: str, output_path: Path,
                    show_answers: bool = False, class_mode: bool = False):
    """전체 슬라이드 생성"""
    content = build_marp_header(title)
    content += build_title_slide(title, problems)

    for p in problems:
        content += build_problem_slide(p, show_answer=show_answers, show_similar=True)

    # 정답 일람 (문제 슬라이드에 정답 없을 때 마지막에 추가)
    if not show_answers:
        content += build_answer_summary_slide(problems)

    # 마무리 슬라이드
    content += f"""
## 🎯 마무리

> 오늘 다룬 {len(problems)}문제를 복습하고,
> 유사문제를 추가로 풀어보세요.

```bash
# 유사문제 검색
python scripts/search.py --similar <문제ID>

# 단원별 추가 문제
python scripts/search.py --topic <단원명> --difficulty 상
```

---

# 수고하셨습니다! 🙌

**수학의 지름길 학원**
분당 정자동 | waw0346@gmail.com
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"✅ 슬라이드 생성 완료: {output_path}")
    print(f"   문제 수: {len(problems)}개")
    print(f"   Marp 변환: npx @marp-team/marp-cli {output_path.name} --pdf")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Marp 수업 슬라이드 생성기")
    parser.add_argument("--ids",        nargs="+", help="문제 ID 목록")
    parser.add_argument("--domain",     help="영역 필터")
    parser.add_argument("--topic",      help="단원 필터")
    parser.add_argument("--grade",      help="학년 필터")
    parser.add_argument("--difficulty", help="난이도 필터")
    parser.add_argument("--year",       help="연도 필터")
    parser.add_argument("--school",     help="학교 필터")
    parser.add_argument("--limit",      type=int, default=15, help="최대 문제 수")
    parser.add_argument("--class-mode", action="store_true", help="쉬운→어려운 순 정렬")
    parser.add_argument("--with-answers", action="store_true", help="각 문제에 정답 포함")
    parser.add_argument("--output",     help="출력 파일 경로")
    parser.add_argument("--title",      default="수학 수업 자료", help="슬라이드 제목")
    args = parser.parse_args()

    # 문제 조회
    if args.ids:
        problems = fetch_problems(ids=args.ids)
    else:
        filters = {}
        if args.domain:     filters["domain"] = args.domain
        if args.topic:      filters["topic"] = args.topic
        if args.grade:      filters["grade"] = args.grade
        if args.difficulty: filters["difficulty"] = args.difficulty
        if args.year:       filters["year"] = args.year
        if args.school:     filters["school"] = args.school
        problems = fetch_problems(filters=filters, limit=args.limit, class_mode=args.class_mode)

    if not problems:
        print("❌ 조건에 맞는 문제가 없습니다.")
        exit(1)

    # 출력 경로
    if args.output:
        out_path = BASE_DIR / args.output
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        label = args.domain or args.topic or args.grade or "전체"
        out_path = BASE_DIR / "slides" / f"{ts}_{label}_수업.md"

    generate_slides(
        problems=problems,
        title=args.title,
        output_path=out_path,
        show_answers=args.with_answers,
        class_mode=args.class_mode
    )
