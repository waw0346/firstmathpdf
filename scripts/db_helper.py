#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DB 헬퍼 — Windows VirtioFS 안전 패턴
======================================
VirtioFS(Windows 마운트)에서 sqlite3 직접 연결 시 disk I/O 오류 발생.
이 모듈은 항상 /tmp 작업 사본을 통해 DB에 안전하게 접근합니다.

사용법:
    from db_helper import get_db, save_db

    conn, tmp_path = get_db()          # 읽기/쓰기
    conn.execute("SELECT ...")
    save_db(tmp_path)                  # 변경사항을 원본에 반영
    conn.close()
"""
import sqlite3, shutil, tempfile, glob
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_SRC   = BASE_DIR / "db" / "problems.db"
TMP_DIR  = Path(tempfile.gettempdir())
TMP_MAIN = TMP_DIR / "mathwiki_main.db"


def _find_best_tmp_db() -> Path | None:
    """유효한 가장 큰 임시 DB 탐색"""
    candidates = []
    for p in TMP_DIR.glob("*.db"):
        try:
            sz = p.stat().st_size
            if sz < 10_000:          # 10KB 미만은 무시
                continue
            conn = sqlite3.connect(p)
            cnt = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
            conn.close()
            if cnt > 0:
                candidates.append((sz, p))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def get_db(readonly: bool = False) -> tuple:
    """
    안전한 DB 연결 반환.
    1) VirtioFS 원본 → TMP_MAIN 복사 시도
    2) 실패 시 가장 큰 유효 tmp DB 사용
    Returns: (conn, tmp_path)
    """
    # 1. 원본이 유효하면 복사
    src_ok = DB_SRC.exists() and DB_SRC.stat().st_size > 10_000
    if src_ok:
        try:
            shutil.copy(DB_SRC, TMP_MAIN)
        except Exception:
            src_ok = False

    # 2. 복사본 검증
    if TMP_MAIN.exists() and TMP_MAIN.stat().st_size > 10_000:
        try:
            conn = sqlite3.connect(TMP_MAIN)
            conn.execute("SELECT COUNT(*) FROM problems").fetchone()
            conn.row_factory = sqlite3.Row
            return conn, TMP_MAIN
        except Exception:
            pass

    # 3. 폴백: 가장 큰 유효 tmp DB 사용
    best = _find_best_tmp_db()
    if best:
        shutil.copy(best, TMP_MAIN)
        print(f"  ⚠️  DB 복구: {best.name} → {TMP_MAIN.name}")
        conn = sqlite3.connect(TMP_MAIN)
        conn.row_factory = sqlite3.Row
        return conn, TMP_MAIN

    raise RuntimeError("유효한 DB를 찾을 수 없습니다. Senior Engineer --fix db 실행 필요")


def save_db(tmp_path: Path = None):
    """tmp DB → VirtioFS 원본에 저장"""
    src = tmp_path or TMP_MAIN
    if not src.exists() or src.stat().st_size < 10_000:
        print(f"  ❌ 저장 취소: {src} 유효하지 않음")
        return False
    try:
        shutil.copy(src, DB_SRC)
        # 저장 후 크기 확인
        actual = DB_SRC.stat().st_size
        if actual < 10_000:
            print(f"  ⚠️  VirtioFS 저장 불안정 ({actual}B) — tmp에 안전하게 보관됨")
            return False
        print(f"  ✅ DB 저장: {src.name} → problems.db ({actual//1024}KB)")
        return True
    except Exception as e:
        print(f"  ⚠️  저장 오류 ({e}) — tmp 사본 유지됨")
        return False


def db_status() -> dict:
    """현재 DB 상태 요약"""
    info = {"src_size": 0, "tmp_size": 0, "problems": 0, "similar": 0, "years": {}}
    try:
        info["src_size"] = DB_SRC.stat().st_size if DB_SRC.exists() else 0
        conn, _ = get_db(readonly=True)
        info["problems"] = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        info["similar"]  = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]
        rows = conn.execute("SELECT year, COUNT(*) FROM problems GROUP BY year").fetchall()
        info["years"]    = {r[0]: r[1] for r in rows}
        info["tmp_size"] = TMP_MAIN.stat().st_size if TMP_MAIN.exists() else 0
        conn.close()
    except Exception as e:
        info["error"] = str(e)
    return info
