#!/usr/bin/env python3
"""
============================================================
Math Problem Wiki — 경량 임베딩 (numpy TF-IDF 기반)
sentence-transformers 없이 바로 실행 가능한 유사문제 계산기

의존성: numpy (기본 설치됨), sqlite3 (표준 라이브러리)

사용법:
  python scripts/embed_simple.py --build    # 전체 유사도 계산
  python scripts/embed_simple.py --similar 2025_수능_고3_022

고급 버전 (embed.py) 사용시:
  pip install sentence-transformers chromadb
  python scripts/embed.py --build
============================================================
"""

import sqlite3, json, math, argparse, shutil, tempfile
from pathlib import Path
from collections import Counter
import numpy as np

BASE_DIR = Path(__file__).parent.parent
DB_SOURCE = BASE_DIR / "db" / "problems.db"
TMP_DIR   = Path(tempfile.gettempdir())


def get_db():
    """DB를 임시 폴더에 복사해서 작업 (Windows/Linux 호환)"""
    tmp_db = TMP_DIR / "embed_work.db"
    shutil.copy(DB_SOURCE, tmp_db)
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    return conn, tmp_db


def build_text(row: dict) -> str:
    """임베딩용 텍스트 구성"""
    concepts = " ".join(json.loads(row.get("concept") or "[]"))
    tags = " ".join(json.loads(row.get("tags") or "[]"))
    parts = [
        row.get("grade", "") * 3,
        row.get("domain", "") * 3,
        row.get("topic", "") * 3,
        concepts * 2,
        row.get("difficulty", ""),
        tags,
        (row.get("raw_text") or row.get("title", ""))[:300],
    ]
    return " ".join(filter(None, parts))


# ──────────────────────────────────────────────────────────────
# TF-IDF 임베딩 (numpy only)
# ──────────────────────────────────────────────────────────────
def tokenize(text: str) -> list[str]:
    """한국어 간단 토크나이저 (2-3글자 n-gram)"""
    text = text.replace(" ", "").replace("\n", "")
    tokens = []
    for n in (2, 3):
        tokens += [text[i:i+n] for i in range(len(text)-n+1)]
    return tokens


def build_tfidf_matrix(texts: list[str]):
    """TF-IDF 행렬 계산"""
    # 토크나이즈
    tokenized = [tokenize(t) for t in texts]

    # 전체 어휘 구축
    vocab = {}
    for toks in tokenized:
        for tok in set(toks):
            if tok not in vocab:
                vocab[tok] = len(vocab)

    n_docs = len(texts)
    n_vocab = len(vocab)
    print(f"  어휘 크기: {n_vocab}개 토큰")

    # TF 행렬
    tf = np.zeros((n_docs, n_vocab), dtype=np.float32)
    for i, toks in enumerate(tokenized):
        cnt = Counter(toks)
        total = max(len(toks), 1)
        for tok, c in cnt.items():
            if tok in vocab:
                tf[i, vocab[tok]] = c / total

    # IDF 계산
    doc_freq = np.zeros(n_vocab, dtype=np.float32)
    for i in range(n_docs):
        nz = tf[i] > 0
        doc_freq[nz] += 1

    idf = np.log((n_docs + 1) / (doc_freq + 1)) + 1.0

    # TF-IDF
    tfidf = tf * idf

    # L2 정규화
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    tfidf_norm = tfidf / norms

    return tfidf_norm


def cosine_similarity_matrix(mat: np.ndarray) -> np.ndarray:
    """정규화된 행렬의 코사인 유사도 (= 내적)"""
    return mat @ mat.T


# ──────────────────────────────────────────────────────────────
# 규칙 기반 보너스 (같은 단원/영역/학년이면 유사도 +)
# ──────────────────────────────────────────────────────────────
def rule_bonus(p1: dict, p2: dict) -> float:
    bonus = 0.0
    if p1["domain"] == p2["domain"]:
        bonus += 0.15
    if p1["topic"] == p2["topic"]:
        bonus += 0.20
    if p1["grade"] == p2["grade"]:
        bonus += 0.05
    if p1["difficulty"] == p2["difficulty"]:
        bonus += 0.05
    # 개념 겹침
    c1 = set(json.loads(p1.get("concept") or "[]"))
    c2 = set(json.loads(p2.get("concept") or "[]"))
    if c1 and c2:
        overlap = len(c1 & c2) / len(c1 | c2)
        bonus += overlap * 0.15
    return min(bonus, 0.40)  # 보너스 최대 0.4


# ──────────────────────────────────────────────────────────────
# 메인: 유사도 계산 & DB 저장
# ──────────────────────────────────────────────────────────────
def build_similarities(top_k: int = 5):
    print("🔄 유사문제 계산 시작 (TF-IDF + 규칙 기반)")
    conn, tmp_db = get_db()

    rows = conn.execute("SELECT * FROM problems ORDER BY id").fetchall()
    problems = [dict(r) for r in rows]
    n = len(problems)
    print(f"  총 {n}개 문제 로드")

    # 텍스트 벡터화
    texts = [build_text(p) for p in problems]
    print("  TF-IDF 행렬 계산 중...")
    tfidf = build_tfidf_matrix(texts)

    # 코사인 유사도
    sim_matrix = cosine_similarity_matrix(tfidf)

    # 규칙 기반 보너스 적용
    print("  규칙 기반 보너스 적용 중...")
    for i in range(n):
        for j in range(n):
            if i != j:
                bonus = rule_bonus(problems[i], problems[j])
                sim_matrix[i, j] = min(sim_matrix[i, j] + bonus, 1.0)

    # DB에 저장
    conn.execute("DELETE FROM similar_problems")

    pairs = []
    for i in range(n):
        sims = sim_matrix[i].copy()
        sims[i] = -1  # 자기 자신 제외
        top_indices = np.argsort(sims)[::-1][:top_k]
        for j in top_indices:
            sim_val = float(sims[j])
            if sim_val > 0.1:
                pairs.append((problems[i]["id"], problems[j]["id"], round(sim_val, 4)))

    conn.executemany(
        "INSERT OR REPLACE INTO similar_problems (problem_id, similar_id, similarity) VALUES (?,?,?)",
        pairs
    )
    conn.commit()

    print(f"  ✅ {len(pairs)}쌍 유사관계 저장")

    # 마크다운 파일의 similar_ids 업데이트
    update_markdown_similar(problems, sim_matrix, top_k)

    # DB 다시 복사
    conn.close()
    shutil.copy(tmp_db, DB_SOURCE)
    print(f"  ✅ DB 저장 완료: {DB_SOURCE}")

    return problems, sim_matrix


def update_markdown_similar(problems: list, sim_matrix: np.ndarray, top_k: int):
    """마크다운 파일의 similar_ids 업데이트"""
    wiki_dir = BASE_DIR / "wiki" / "problems"
    updated = 0
    for i, p in enumerate(problems):
        sims = sim_matrix[i].copy()
        sims[i] = -1
        top_idx = np.argsort(sims)[::-1][:top_k]
        similar_ids = [problems[j]["id"] for j in top_idx if sims[j] > 0.1]

        md_path = wiki_dir / f"{p['id']}.md"
        if md_path.exists():
            content = md_path.read_text(encoding="utf-8")
            old_line = f"similar_ids: {json.loads(p.get('similar_ids_json') or '[]')}"
            # YAML 프론트매터에서 similar_ids 교체
            import re
            content = re.sub(
                r'^similar_ids:.*$',
                f"similar_ids: {similar_ids}",
                content,
                flags=re.MULTILINE
            )
            md_path.write_text(content, encoding="utf-8")
            updated += 1
    print(f"  ✅ {updated}개 마크다운 similar_ids 업데이트")


def show_similar(problem_id: str, problems: list, sim_matrix: np.ndarray, top_k: int = 5):
    """특정 문제의 유사문제 출력"""
    idx_map = {p["id"]: i for i, p in enumerate(problems)}
    if problem_id not in idx_map:
        print(f"❌ '{problem_id}' 없음")
        return

    i = idx_map[problem_id]
    p = problems[i]
    sims = sim_matrix[i].copy()
    sims[i] = -1
    top_indices = np.argsort(sims)[::-1][:top_k]

    print(f"\n🔍 '{p['title']}' ({p['difficulty']}) 유사문제 TOP {top_k}")
    print(f"   영역: {p['domain']} | 단원: {p['topic']}")
    print()
    print(f"{'순위':<4} {'ID':<25} {'제목':<22} {'영역':<8} {'단원':<10} {'난이도':<5} {'유사도':>6}")
    print("-" * 88)
    for rank, j in enumerate(top_indices, 1):
        sim = sims[j]
        if sim <= 0.05:
            break
        q = problems[j]
        diff_icons = {"하": "🟢", "중": "🟡", "상": "🔴", "최상": "⚫"}
        icon = diff_icons.get(q["difficulty"], "")
        print(f"{rank:<4} {q['id']:<25} {q['title'][:20]:<22} {q['domain']:<8} "
              f"{q['topic'][:10]:<10} {icon}{q['difficulty']:<4} {sim:.3f}")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="경량 임베딩 유사문제 계산기")
    parser.add_argument("--build",   action="store_true", help="전체 유사도 계산 및 DB 저장")
    parser.add_argument("--similar", metavar="ID",        help="특정 문제 유사문제 출력")
    parser.add_argument("--top-k",   type=int, default=5, help="유사문제 개수")
    args = parser.parse_args()

    if args.build or args.similar:
        problems, sim_matrix = build_similarities(top_k=args.top_k)
        if args.similar:
            show_similar(args.similar, problems, sim_matrix, top_k=args.top_k)
    else:
        parser.print_help()
