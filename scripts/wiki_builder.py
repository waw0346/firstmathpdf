#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Math Problem Wiki — Wiki Index Builder
수학 문제 위키 — 위키 인덱스 자동 빌더

사용법:
  python wiki_builder.py --all        # 전체 인덱스 재생성
  python wiki_builder.py --school     # 학교별 인덱스만
  python wiki_builder.py --topic      # 단원별 인덱스만
  python wiki_builder.py --year       # 연도별 인덱스만
============================================================
"""

import json, sqlite3, argparse, shutil, tempfile, sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import yaml

BASE_DIR = Path(__file__).parent.parent
CONFIG   = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))
TMP_DIR  = Path(tempfile.gettempdir())

# db_helper 임포트 (VirtioFS 안전 패턴)
sys.path.insert(0, str(BASE_DIR / "scripts"))
try:
    from db_helper import get_db as _db_helper_get_db
    _USE_DB_HELPER = True
except ImportError:
    _USE_DB_HELPER = False

DIFF_ICON = {"하": "🟢", "중": "🟡", "상": "🔴", "최상": "⚫"}
DIFF_ORDER = {"하": 0, "중": 1, "상": 2, "최상": 3}


def get_conn():
    """Windows/Linux 호환 — db_helper 스마트 폴백 사용"""
    if _USE_DB_HELPER:
        conn, _ = _db_helper_get_db()
        return conn
    # 폴백: 직접 복사
    db_src = BASE_DIR / CONFIG["database"]["path"]
    tmp_db = TMP_DIR / "wiki_builder_work.db"
    shutil.copy(db_src, tmp_db)
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────
# 메인 인덱스
# ──────────────────────────────────────────────────────────────
def build_main_index(conn):
    """wiki/index.md 생성"""
    total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    schools = conn.execute("SELECT COUNT(DISTINCT school) FROM problems").fetchone()[0]
    years   = conn.execute("SELECT COUNT(DISTINCT year) FROM problems").fetchone()[0]
    topics  = conn.execute("SELECT COUNT(DISTINCT topic) FROM problems").fetchone()[0]

    by_domain = conn.execute(
        "SELECT domain, COUNT(*) as cnt FROM problems GROUP BY domain ORDER BY cnt DESC"
    ).fetchall()

    by_diff = conn.execute(
        "SELECT difficulty, COUNT(*) as cnt FROM problems GROUP BY difficulty"
    ).fetchall()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    content = f"""# 📚 수학 문제 위키 — 메인 인덱스

> 마지막 업데이트: {now}

## 📊 현황 요약

| 항목 | 수치 |
|------|------|
| 총 문제 수 | **{total:,}개** |
| 학교/기관 수 | {schools}곳 |
| 수록 연도 | {years}개 연도 |
| 단원 수 | {topics}개 |

---

## 📁 인덱스 탐색

- 📂 [영역·단원별](topics/index.md) — 수와연산, 문자와식, 함수, 기하, 확률과통계
- 🏫 [학교·기관별](schools/index.md)
- 📅 [연도별](years/index.md)
- 🎯 [난이도별](difficulty/index.md)

---

## 영역별 현황

"""
    for row in by_domain:
        domain, cnt = row["domain"], row["cnt"]
        pct = cnt / total * 100 if total else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        content += f"- **{domain}**: {cnt}개 ({pct:.1f}%) `{bar}`\n"

    content += "\n## 난이도별 현황\n\n"
    for row in sorted(by_diff, key=lambda r: DIFF_ORDER.get(r["difficulty"], 99)):
        d, cnt = row["difficulty"], row["cnt"]
        icon = DIFF_ICON.get(d, "")
        content += f"- {icon} **{d}**: {cnt}개\n"

    content += f"""
---

## 🔍 빠른 검색

```bash
# 유사문제 검색
python scripts/search.py --similar <문제ID>

# 키워드 검색
python scripts/search.py --query "이차방정식" --grade 중3

# 학교+연도 필터
python scripts/search.py --school 분당중학교 --year 2023

# 단원+난이도
python scripts/search.py --topic 피타고라스 --difficulty 상

# 전체 통계
python scripts/search.py --stats
```

---

## 🌐 대시보드

`wiki/dashboard.html` 파일을 브라우저로 열면 시각적 검색 인터페이스를 사용할 수 있습니다.
"""
    out = BASE_DIR / "wiki" / "index.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"  ✓ 메인 인덱스: {out}")


# ──────────────────────────────────────────────────────────────
# 단원별 인덱스
# ──────────────────────────────────────────────────────────────
def build_topic_index(conn):
    """wiki/topics/ 단원별 페이지 생성"""
    rows = conn.execute("""
        SELECT domain, topic, grade, id, title, difficulty, school, year, exam_type, answer
        FROM problems
        ORDER BY domain, topic, year DESC
    """).fetchall()

    # domain → topic → problems
    tree = defaultdict(lambda: defaultdict(list))
    for r in rows:
        r = dict(r)
        tree[r["domain"]][r["topic"]].append(r)

    # 전체 단원 인덱스
    idx_content = "# 📂 영역·단원별 인덱스\n\n"
    for domain, topics in tree.items():
        idx_content += f"\n## {domain}\n\n"
        for topic, problems in topics.items():
            idx_content += f"- [{topic}]({domain}_{topic}.md) — {len(problems)}문제\n"

    out_idx = BASE_DIR / "wiki" / "topics" / "index.md"
    out_idx.parent.mkdir(parents=True, exist_ok=True)
    out_idx.write_text(idx_content, encoding="utf-8")

    # 각 단원 페이지
    for domain, topics in tree.items():
        for topic, problems in topics.items():
            content = f"# {domain} > {topic}\n\n"
            content += f"> 총 {len(problems)}문제\n\n"
            content += "| 문제ID | 제목 | 난이도 | 출처 | 연도 | 정답 |\n"
            content += "|--------|------|--------|------|------|------|\n"
            for p in sorted(problems, key=lambda x: (DIFF_ORDER.get(x["difficulty"], 99), x["year"]), reverse=True):
                icon = DIFF_ICON.get(p["difficulty"], "")
                link = f"[{p['id']}](../problems/{p['id']}.md)"
                content += (f"| {link} | {p['title'][:20]} | "
                            f"{icon}{p['difficulty']} | {p['school']} | "
                            f"{p['year']} | {p['answer']} |\n")

            safe_name = f"{domain}_{topic}".replace("/", "_").replace(" ", "")
            out = BASE_DIR / "wiki" / "topics" / f"{safe_name}.md"
            out.write_text(content, encoding="utf-8")

    print(f"  ✓ 단원 인덱스: {len(tree)}개 영역, {sum(len(v) for v in tree.values())}개 단원")


# ──────────────────────────────────────────────────────────────
# 학교별 인덱스
# ──────────────────────────────────────────────────────────────
def build_school_index(conn):
    """wiki/schools/ 학교별 페이지 생성"""
    schools = conn.execute(
        "SELECT DISTINCT school FROM problems ORDER BY school"
    ).fetchall()

    idx_content = "# 🏫 학교·기관별 인덱스\n\n"
    for s in schools:
        school = s[0]
        cnt = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE school=?", (school,)
        ).fetchone()[0]
        safe = school.replace(" ", "_")
        idx_content += f"- [{school}]({safe}.md) — {cnt}문제\n"

    out_idx = BASE_DIR / "wiki" / "schools" / "index.md"
    out_idx.parent.mkdir(parents=True, exist_ok=True)
    out_idx.write_text(idx_content, encoding="utf-8")

    for s in schools:
        school = s[0]
        rows = conn.execute("""
            SELECT id, title, grade, domain, topic, difficulty, year, exam_type, answer
            FROM problems WHERE school=?
            ORDER BY year DESC, exam_type, difficulty
        """, (school,)).fetchall()

        content = f"# 🏫 {school}\n\n> 총 {len(rows)}문제\n\n"
        # 연도별 섹션
        by_year = defaultdict(list)
        for r in rows:
            by_year[r["year"]].append(dict(r))

        for year in sorted(by_year.keys(), reverse=True):
            content += f"\n## {year}년\n\n"
            content += "| 문제ID | 제목 | 학년 | 단원 | 난이도 | 시험 |\n"
            content += "|--------|------|------|------|--------|------|\n"
            for p in by_year[year]:
                icon = DIFF_ICON.get(p["difficulty"], "")
                link = f"[{p['id']}](../problems/{p['id']}.md)"
                content += (f"| {link} | {p['title'][:18]} | {p['grade']} | "
                            f"{p['topic'][:10]} | {icon}{p['difficulty']} | "
                            f"{p['exam_type']} |\n")

        safe = school.replace(" ", "_")
        out = BASE_DIR / "wiki" / "schools" / f"{safe}.md"
        out.write_text(content, encoding="utf-8")

    print(f"  ✓ 학교 인덱스: {len(schools)}개 학교")


# ──────────────────────────────────────────────────────────────
# 연도별 인덱스
# ──────────────────────────────────────────────────────────────
def build_year_index(conn):
    """wiki/years/ 연도별 페이지 생성"""
    years = conn.execute(
        "SELECT DISTINCT year FROM problems ORDER BY year DESC"
    ).fetchall()

    idx_content = "# 📅 연도별 인덱스\n\n"
    for y in years:
        year = y[0]
        cnt  = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE year=?", (year,)
        ).fetchone()[0]
        idx_content += f"- [{year}년]({year}.md) — {cnt}문제\n"

    out_idx = BASE_DIR / "wiki" / "years" / "index.md"
    out_idx.parent.mkdir(parents=True, exist_ok=True)
    out_idx.write_text(idx_content, encoding="utf-8")

    for y in years:
        year = y[0]
        rows = conn.execute("""
            SELECT id, title, grade, domain, topic, difficulty, school, exam_type, answer
            FROM problems WHERE year=?
            ORDER BY school, exam_type, difficulty
        """, (year,)).fetchall()

        content = f"# 📅 {year}년 문제 목록\n\n> 총 {len(rows)}문제\n\n"
        content += "| 문제ID | 제목 | 학년 | 영역 | 단원 | 난이도 | 학교 | 시험 |\n"
        content += "|--------|------|------|------|------|--------|------|------|\n"

        for r in rows:
            r = dict(r)
            icon = DIFF_ICON.get(r["difficulty"], "")
            link = f"[{r['id']}](../problems/{r['id']}.md)"
            content += (f"| {link} | {r['title'][:16]} | {r['grade']} | "
                        f"{r['domain']} | {r['topic'][:10]} | "
                        f"{icon}{r['difficulty']} | {r['school']} | {r['exam_type']} |\n")

        out = BASE_DIR / "wiki" / "years" / f"{year}.md"
        out.write_text(content, encoding="utf-8")

    print(f"  ✓ 연도 인덱스: {len(years)}개 연도")


# ──────────────────────────────────────────────────────────────
# 난이도별 인덱스
# ──────────────────────────────────────────────────────────────
def build_difficulty_index(conn):
    """wiki/difficulty/ 난이도별 페이지 생성"""
    out_dir = BASE_DIR / "wiki" / "difficulty"
    out_dir.mkdir(parents=True, exist_ok=True)

    idx_content = "# 🎯 난이도별 인덱스\n\n"
    for diff in ["하", "중", "상", "최상"]:
        icon = DIFF_ICON.get(diff, "")
        cnt = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE difficulty=?", (diff,)
        ).fetchone()[0]
        idx_content += f"- {icon} [{diff}]({diff}.md) — {cnt}문제\n"

    (out_dir / "index.md").write_text(idx_content, encoding="utf-8")

    for diff in ["하", "중", "상", "최상"]:
        rows = conn.execute("""
            SELECT id, title, grade, domain, topic, school, year, exam_type, answer
            FROM problems WHERE difficulty=?
            ORDER BY domain, topic, year DESC
        """, (diff,)).fetchall()

        icon = DIFF_ICON.get(diff, "")
        content = f"# {icon} 난이도 '{diff}' 문제 목록\n\n> 총 {len(rows)}문제\n\n"
        content += "| 문제ID | 제목 | 학년 | 영역 | 단원 | 학교 | 연도 |\n"
        content += "|--------|------|------|------|------|------|------|\n"

        for r in rows:
            r = dict(r)
            link = f"[{r['id']}](../problems/{r['id']}.md)"
            content += (f"| {link} | {r['title'][:18]} | {r['grade']} | "
                        f"{r['domain']} | {r['topic'][:10]} | "
                        f"{r['school']} | {r['year']} |\n")

        (out_dir / f"{diff}.md").write_text(content, encoding="utf-8")

    print(f"  ✓ 난이도 인덱스 생성 완료")


# ──────────────────────────────────────────────────────────────
# 전체 업데이트 (ingest.py에서 호출)
# ──────────────────────────────────────────────────────────────
def update_indices(conn=None, meta: dict = None):
    """인제스트 후 인덱스 빠른 업데이트"""
    if conn is None:
        conn = get_conn()
    build_main_index(conn)
    build_topic_index(conn)
    build_school_index(conn)
    build_year_index(conn)
    build_difficulty_index(conn)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="위키 인덱스 빌더")
    parser.add_argument("--all",        action="store_true", help="전체 인덱스 재생성")
    parser.add_argument("--school",     action="store_true")
    parser.add_argument("--topic",      action="store_true")
    parser.add_argument("--year",       action="store_true")
    parser.add_argument("--difficulty", action="store_true")
    args = parser.parse_args()

    conn = get_conn()
    print("위키 인덱스 빌드 중...\n")

    if args.all or not any([args.school, args.topic, args.year, args.difficulty]):
        build_main_index(conn)
        build_topic_index(conn)
        build_school_index(conn)
        build_year_index(conn)
        build_difficulty_index(conn)
    else:
        if args.school:     build_school_index(conn)
        if args.topic:      build_topic_index(conn)
        if args.year:       build_year_index(conn)
        if args.difficulty: build_difficulty_index(conn)

    print("\n✅ 인덱스 빌드 완료!")
