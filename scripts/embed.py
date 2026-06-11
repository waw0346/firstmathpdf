#!/usr/bin/env python3
"""
============================================================
Math Problem Wiki — Embedding & Similarity Engine
수학 문제 위키 — 임베딩 및 유사문제 검색 엔진

사용법:
  python embed.py --build        # 전체 문제 임베딩 생성/업데이트
  python embed.py --update-new   # 새로 추가된 문제만 임베딩

요구사항:
  pip install sentence-transformers chromadb numpy
============================================================
"""

import os, sys, json, sqlite3, logging
from pathlib import Path
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
    import chromadb
    from chromadb.config import Settings
    import numpy as np
    import yaml
except ImportError as e:
    print(f"[오류] 패키지 미설치: {e}")
    print("pip install sentence-transformers chromadb numpy")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent
CONFIG   = yaml.safe_load((BASE_DIR / "config.yaml").read_text(encoding="utf-8"))

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 임베딩 모델 로드
# ──────────────────────────────────────────────────────────────
def load_model() -> SentenceTransformer:
    """한국어 특화 임베딩 모델 로드"""
    model_name = CONFIG["api"]["embedding"]["model"]
    print(f"임베딩 모델 로드 중: {model_name}")
    try:
        return SentenceTransformer(model_name)
    except Exception:
        fallback = CONFIG["api"]["embedding"]["fallback"]
        print(f"  → 대안 모델 사용: {fallback}")
        return SentenceTransformer(fallback)


# ──────────────────────────────────────────────────────────────
# ChromaDB 컬렉션
# ──────────────────────────────────────────────────────────────
def get_chroma_collection():
    """ChromaDB 컬렉션 반환"""
    chroma_path = str(BASE_DIR / CONFIG["database"]["chroma_path"])
    Path(chroma_path).mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_or_create_collection(
        name="math_problems",
        metadata={"hnsw:space": "cosine"}
    )
    return collection


# ──────────────────────────────────────────────────────────────
# 임베딩 텍스트 구성
# ──────────────────────────────────────────────────────────────
def build_embed_text(row: dict) -> str:
    """임베딩용 텍스트 구성 (문제 + 메타데이터 결합)"""
    concept = json.loads(row.get("concept", "[]")) if isinstance(row.get("concept"), str) else []
    return (
        f"[학년:{row.get('grade','')}] "
        f"[영역:{row.get('domain','')}] "
        f"[단원:{row.get('topic','')}] "
        f"[개념:{','.join(concept)}] "
        f"[난이도:{row.get('difficulty','')}] "
        f"{row.get('raw_text','')[:500]}"
    )


# ──────────────────────────────────────────────────────────────
# 전체 임베딩 빌드
# ──────────────────────────────────────────────────────────────
def build_embeddings(update_only: bool = False):
    """DB의 모든 문제에 대해 임베딩 생성"""
    model = load_model()
    collection = get_chroma_collection()

    db_path = BASE_DIR / CONFIG["database"]["path"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 처리할 문제 조회
    if update_only:
        existing_ids = set(collection.get()["ids"])
        if existing_ids:
            placeholders = ",".join(["?"] * len(existing_ids))
            rows = conn.execute(
                f"SELECT * FROM problems WHERE id NOT IN ({placeholders})",
                list(existing_ids)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM problems").fetchall()
    else:
        rows = conn.execute("SELECT * FROM problems").fetchall()

    if not rows:
        print("임베딩할 새 문제가 없습니다.")
        conn.close()
        return

    print(f"{len(rows)}개 문제 임베딩 생성 중...")

    batch_size = 32
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        texts = [build_embed_text(dict(r)) for r in batch]
        ids   = [r["id"] for r in batch]

        metadatas = [{
            "grade":      r["grade"] or "",
            "domain":     r["domain"] or "",
            "topic":      r["topic"] or "",
            "difficulty": r["difficulty"] or "",
            "school":     r["school"] or "",
            "year":       str(r["year"] or ""),
            "exam_type":  r["exam_type"] or ""
        } for r in batch]

        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        # ChromaDB upsert
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        print(f"  {min(i + batch_size, len(rows))}/{len(rows)} 완료")

    print(f"\n✅ 임베딩 완료! 총 {collection.count()}개 문제 인덱싱됨")

    # 유사문제 관계 DB 업데이트
    print("\n유사문제 관계 계산 중...")
    update_similar_relations(conn, collection, model)
    conn.close()


# ──────────────────────────────────────────────────────────────
# 유사문제 관계 업데이트
# ──────────────────────────────────────────────────────────────
def update_similar_relations(conn, collection, model, top_k: int = 5):
    """각 문제의 유사문제 top-k를 DB에 저장"""
    rows = conn.execute("SELECT id, raw_text, grade, domain, topic, difficulty, concept FROM problems").fetchall()

    for row in rows:
        row = dict(row)
        text = build_embed_text(row)
        embedding = model.encode([text])[0].tolist()

        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k + 1,  # 자기 자신 포함
            where={"domain": row["domain"]} if row.get("domain") and row["domain"] != "미분류" else None
        )

        similar = []
        for rid, dist in zip(results["ids"][0], results["distances"][0]):
            if rid == row["id"]:
                continue  # 자기 자신 제외
            similarity = 1 - dist  # cosine distance → similarity
            similar.append((row["id"], rid, float(similarity)))

        if similar:
            conn.executemany(
                "INSERT OR REPLACE INTO similar_problems VALUES (?,?,?)",
                similar
            )

        # 마크다운 파일의 similar_ids 업데이트
        md_row = conn.execute("SELECT md_path FROM problems WHERE id=?", (row["id"],)).fetchone()
        if md_row and md_row[0]:
            md_path = BASE_DIR / md_row[0]
            if md_path.exists():
                update_similar_in_markdown(md_path, [s[1] for s in similar[:top_k]])

    conn.commit()
    print(f"  유사문제 관계 업데이트 완료")


def update_similar_in_markdown(md_path: Path, similar_ids: list):
    """마크다운 파일의 similar_ids 프론트매터 업데이트"""
    import re
    content = md_path.read_text(encoding="utf-8")
    new_val = "[" + ", ".join(similar_ids) + "]"
    content = re.sub(
        r"^similar_ids:.*$",
        f"similar_ids: {new_val}",
        content,
        flags=re.MULTILINE
    )

    # 유사 문제 섹션도 업데이트
    links = "\n".join([f"- [{sid}](../problems/{sid}.md)" for sid in similar_ids])
    content = re.sub(
        r"(## 🔗 유사 문제\n\n).*?(\n---)",
        rf"\1{links}\n\2",
        content,
        flags=re.DOTALL
    )
    md_path.write_text(content, encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="수학 문제 임베딩 생성")
    parser.add_argument("--build",      action="store_true", help="전체 임베딩 재생성")
    parser.add_argument("--update-new", action="store_true", help="새 문제만 임베딩 추가")
    args = parser.parse_args()

    if args.build:
        build_embeddings(update_only=False)
    elif args.update_new:
        build_embeddings(update_only=True)
    else:
        parser.print_help()
