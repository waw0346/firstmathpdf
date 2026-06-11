#!/usr/bin/env python3
"""
============================================================
Math Problem Wiki — Search & Query Interface
수학 문제 위키 — 검색 및 쿼리 인터페이스

사용법:
  python search.py --similar 2023_분당중_3_042
  python search.py --query "이차방정식 판별식" --grade 중3
  python search.py --filter domain=기하 difficulty=상 year=2023
  python search.py --school 분당중학교 --exam 1학기기말
  python search.py --topic 피타고라스 --limit 20
============================================================
"""

import json, sqlite3, argparse, sys
from pathlib import Path
from typing import Optional
import yaml

BASE_DIR = Path(__file__).parent.parent
CONFIG   = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────
# DB 연결
# ──────────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    db_path = BASE_DIR / CONFIG["database"]["path"]
    if not db_path.exists():
        print("❌ DB가 없습니다. 먼저 ingest.py를 실행하세요.")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────
# 유사문제 검색 (임베딩 기반)
# ──────────────────────────────────────────────────────────────
def find_similar(problem_id: str, top_k: int = 10) -> list[dict]:
    """특정 문제와 유사한 문제 검색"""
    conn = get_conn()
    try:
        # DB에서 사전 계산된 유사도 조회
        similar_rows = conn.execute("""
            SELECT sp.similar_id, sp.similarity,
                   p.title, p.grade, p.domain, p.topic,
                   p.difficulty, p.school, p.year, p.exam_type, p.answer
            FROM similar_problems sp
            JOIN problems p ON sp.similar_id = p.id
            WHERE sp.problem_id = ?
            ORDER BY sp.similarity DESC
            LIMIT ?
        """, (problem_id, top_k)).fetchall()

        if similar_rows:
            return [dict(r) for r in similar_rows]

        # 사전 계산 없으면 실시간 검색
        print("사전 계산된 유사도 없음. 실시간 검색 중...")
        return realtime_similar_search(problem_id, top_k, conn)
    finally:
        conn.close()


def realtime_similar_search(problem_id: str, top_k: int, conn) -> list[dict]:
    """ChromaDB로 실시간 유사도 검색"""
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        print("실시간 검색을 위해: pip install sentence-transformers chromadb")
        return []

    # 원문 문제 조회
    row = conn.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
    if not row:
        print(f"문제 ID '{problem_id}'를 찾을 수 없습니다.")
        return []
    row = dict(row)

    # 임베딩 모델 로드
    from embed import load_model, build_embed_text, get_chroma_collection
    model = load_model()
    collection = get_chroma_collection()

    text = build_embed_text(row)
    embedding = model.encode([text])[0].tolist()

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k + 1
    )

    similar = []
    for rid, dist in zip(results["ids"][0], results["distances"][0]):
        if rid == problem_id:
            continue
        p = conn.execute("SELECT * FROM problems WHERE id=?", (rid,)).fetchone()
        if p:
            p = dict(p)
            p["similarity"] = round(1 - dist, 3)
            similar.append(p)

    return similar[:top_k]


# ──────────────────────────────────────────────────────────────
# 텍스트 검색
# ──────────────────────────────────────────────────────────────
_ALLOWED_FILTER_COLUMNS = frozenset(
    {"domain", "topic", "grade", "difficulty", "school", "year", "exam_type", "source_type"}
)

def text_search(query: str, filters: dict = None, limit: int = 20) -> list[dict]:
    """키워드 + 필터 검색"""
    conn = get_conn()
    try:
        where_clauses = ["(raw_text LIKE ? OR title LIKE ? OR topic LIKE ? OR concept LIKE ?)"]
        params = [f"%{query}%"] * 4

        if filters:
            for key, val in filters.items():
                if key not in _ALLOWED_FILTER_COLUMNS:
                    continue
                where_clauses.append(f"{key} = ?")
                params.append(val)

        sql = f"""
            SELECT id, title, grade, domain, topic, difficulty,
                   school, year, exam_type, answer
            FROM problems
            WHERE {' AND '.join(where_clauses)}
            ORDER BY year DESC, school, exam_type
            LIMIT ?
        """
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# 필터 검색
# ──────────────────────────────────────────────────────────────
def filter_search(filters: dict, limit: int = 50) -> list[dict]:
    """조건 필터 검색"""
    conn = get_conn()
    try:
        where_clauses = []
        params = []

        filter_map = {
            "domain": "domain",
            "topic": "topic",
            "grade": "grade",
            "difficulty": "difficulty",
            "school": "school",
            "year": "year",
            "exam_type": "exam_type",
            "source_type": "source_type"
        }

        for key, val in filters.items():
            if key in filter_map:
                where_clauses.append(f"{filter_map[key]} = ?")
                params.append(val)

        sql = f"""
            SELECT id, title, grade, domain, topic, difficulty,
                   school, year, exam_type, answer
            FROM problems
            {('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''}
            ORDER BY year DESC, school, difficulty
            LIMIT ?
        """
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# 통계 조회
# ──────────────────────────────────────────────────────────────
def get_stats() -> dict:
    """전체 통계"""
    conn = get_conn()
    try:
        stats = {}
        stats["total"] = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        stats["by_domain"] = dict(conn.execute(
            "SELECT domain, COUNT(*) FROM problems GROUP BY domain ORDER BY COUNT(*) DESC"
        ).fetchall())
        stats["by_difficulty"] = dict(conn.execute(
            "SELECT difficulty, COUNT(*) FROM problems GROUP BY difficulty"
        ).fetchall())
        stats["by_year"] = dict(conn.execute(
            "SELECT year, COUNT(*) FROM problems GROUP BY year ORDER BY year DESC"
        ).fetchall())
        stats["by_school"] = dict(conn.execute(
            "SELECT school, COUNT(*) FROM problems GROUP BY school ORDER BY COUNT(*) DESC LIMIT 10"
        ).fetchall())
        stats["by_grade"] = dict(conn.execute(
            "SELECT grade, COUNT(*) FROM problems GROUP BY grade"
        ).fetchall())
        return stats
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────────────────────
DIFF_ICON = {"하": "🟢", "중": "🟡", "상": "🔴", "최상": "⚫"}

def print_results(results: list[dict], title: str = "검색 결과"):
    """결과 테이블 출력"""
    try:
        from rich.table import Table
        from rich.console import Console
        console = Console()

        table = Table(title=f"📚 {title} ({len(results)}건)", show_header=True)
        table.add_column("ID", style="dim", width=22)
        table.add_column("제목", width=24)
        table.add_column("학년", width=4)
        table.add_column("단원", width=12)
        table.add_column("난이도", width=5)
        table.add_column("출처", width=10)
        table.add_column("연도", width=5)
        table.add_column("정답", width=8)
        if "similarity" in (results[0] if results else {}):
            table.add_column("유사도", width=6)

        for r in results:
            diff = r.get("difficulty", "")
            row_data = [
                r.get("id", ""),
                r.get("title", "")[:22],
                r.get("grade", ""),
                r.get("topic", "")[:10],
                f"{DIFF_ICON.get(diff, '')} {diff}",
                r.get("school", "")[:8],
                str(r.get("year", "")),
                str(r.get("answer", ""))[:6],
            ]
            if "similarity" in r:
                row_data.append(f"{r['similarity']:.2f}")
            table.add_row(*row_data)

        console.print(table)
    except ImportError:
        # rich 없으면 기본 출력
        print(f"\n=== {title} ({len(results)}건) ===")
        for r in results:
            sim = f" [유사도:{r.get('similarity', ''):.2f}]" if "similarity" in r else ""
            print(f"  {r.get('id','')} | {r.get('title','')[:20]} | "
                  f"{r.get('grade','')} | {r.get('topic','')} | "
                  f"{r.get('difficulty','')} | {r.get('school','')} {r.get('year','')}{sim}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="수학 문제 위키 검색",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python search.py --similar 2023_분당중_3_042
  python search.py --query "이차방정식" --grade 중3 --difficulty 상
  python search.py --filter domain=기하 school=분당중학교
  python search.py --school 분당중학교 --year 2023
  python search.py --topic 피타고라스 --limit 20
  python search.py --stats
        """
    )
    parser.add_argument("--similar",    metavar="ID",    help="유사문제 검색")
    parser.add_argument("--query",      metavar="TEXT",  help="키워드 검색")
    parser.add_argument("--topic",      metavar="TOPIC", help="단원명 검색")
    parser.add_argument("--school",     metavar="NAME",  help="학교명 필터")
    parser.add_argument("--year",       metavar="YEAR",  help="연도 필터")
    parser.add_argument("--grade",      metavar="GRADE", help="학년 필터 (예: 중3)")
    parser.add_argument("--difficulty", metavar="DIFF",  help="난이도 (하/중/상/최상)")
    parser.add_argument("--domain",     metavar="DOM",   help="영역 필터")
    parser.add_argument("--exam",       metavar="EXAM",  help="시험 종류 필터")
    parser.add_argument("--filter",     nargs="+",       help="key=value 형태 필터")
    parser.add_argument("--limit",      type=int, default=20, help="결과 수 (기본 20)")
    parser.add_argument("--stats",      action="store_true", help="전체 통계 출력")
    args = parser.parse_args()

    if args.stats:
        stats = get_stats()
        print(f"\n📊 수학 문제 위키 통계")
        print(f"  총 문제 수: {stats['total']}개")
        print(f"\n  영역별:")
        for d, c in stats["by_domain"].items():
            print(f"    {d}: {c}개")
        print(f"\n  난이도별:")
        for d, c in stats["by_difficulty"].items():
            icon = DIFF_ICON.get(d, "")
            print(f"    {icon} {d}: {c}개")
        print(f"\n  연도별:")
        for y, c in stats["by_year"].items():
            print(f"    {y}: {c}개")
        print(f"\n  학교별 (상위 10):")
        for s, c in stats["by_school"].items():
            print(f"    {s}: {c}개")

    elif args.similar:
        results = find_similar(args.similar, top_k=args.limit)
        print_results(results, f"'{args.similar}' 유사문제")

    else:
        # 필터 조합
        filters = {}
        if args.grade:      filters["grade"] = args.grade
        if args.difficulty: filters["difficulty"] = args.difficulty
        if args.domain:     filters["domain"] = args.domain
        if args.school:     filters["school"] = args.school
        if args.year:       filters["year"] = args.year
        if args.exam:       filters["exam_type"] = args.exam
        if args.topic:      filters["topic"] = args.topic
        if args.filter:
            for kv in args.filter:
                k, v = kv.split("=", 1)
                filters[k] = v

        if args.query:
            results = text_search(args.query, filters, args.limit)
            print_results(results, f"'{args.query}' 검색결과")
        elif filters:
            results = filter_search(filters, args.limit)
            label = " + ".join(f"{k}={v}" for k, v in filters.items())
            print_results(results, label)
        else:
            parser.print_help()
