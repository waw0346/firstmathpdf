#!/usr/bin/env python3
"""
update_similar_groups.py — 유사문제 그룹 자동 갱신
매주 실행 권장: 새 문제 추가 후 그룹 재계산

사용법: python3 scripts/update_similar_groups.py
"""
import sqlite3, shutil, json, tempfile, sys
from pathlib import Path
from PIL import Image
import numpy as np
from datetime import datetime

BASE   = Path(__file__).parent.parent
DB_SRC = BASE / "db" / "problems.db"
TMP    = Path(tempfile.gettempdir()) / "update_sim.db"
CROPS  = BASE / "sources" / "crops"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def img_fingerprint(img_path, size=(32,32)):
    try:
        img = Image.open(img_path).convert('L').resize(size, Image.LANCZOS)
        arr = np.array(img).flatten().astype(float)
        arr = (arr - arr.mean()) / (arr.std() + 1e-8)
        return arr
    except:
        return None

def cosine_sim(a, b):
    return np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-8)

def run():
    if not DB_SRC.exists() or DB_SRC.stat().st_size < 10_000:
        raise RuntimeError(f"유효하지 않은 DB 파일: {DB_SRC}")
    shutil.copy(str(DB_SRC), str(TMP))
    import time; time.sleep(0.3)
    conn = sqlite3.connect(str(TMP))
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"🔄 유사문제 그룹 갱신 시작 ({now})")

    # 1. similar_groups 자동 재생성
    cur.execute("DELETE FROM similar_groups WHERE group_type='auto'")
    groups_q = cur.execute("""
        SELECT topic, difficulty, COUNT(*) cnt, GROUP_CONCAT(id) ids
        FROM problems WHERE topic!='' AND topic IS NOT NULL
        GROUP BY topic, difficulty HAVING cnt>=2
    """).fetchall()
    for g in groups_q:
        cur.execute("""INSERT OR IGNORE INTO similar_groups
            (group_name, group_type, topic, difficulty, member_ids, created_by)
            VALUES(?,?,?,?,?,?)""",
            (f"{g['topic']}_{g['difficulty']}", 'auto',
             g['topic'], g['difficulty'],
             json.dumps(g['ids'].split(',')[:10]), 'system'))

    # 2. 이미지 유사도 갱신
    rows = cur.execute("SELECT id, crop_path FROM problems WHERE crop_path!=''").fetchall()
    fps = {}
    for r in rows:
        p = BASE / r['crop_path']
        if p.exists():
            fp = img_fingerprint(p)
            if fp is not None: fps[r['id']] = fp

    existing = set()
    for r in cur.execute("SELECT problem_id, similar_id FROM similar_problems").fetchall():
        existing.add((r[0],r[1])); existing.add((r[1],r[0]))

    new_pairs = 0
    tg = cur.execute("SELECT topic, GROUP_CONCAT(id) ids FROM problems WHERE topic!='' GROUP BY topic").fetchall()
    for g in tg:
        pids = g['ids'].split(',')
        for i in range(len(pids)):
            for j in range(i+1, len(pids)):
                if (pids[i],pids[j]) in existing: continue
                if pids[i] not in fps or pids[j] not in fps: continue
                sim = cosine_sim(fps[pids[i]], fps[pids[j]])
                if sim >= 0.85:
                    cur.execute("INSERT OR IGNORE INTO similar_problems(problem_id,similar_id,similarity) VALUES(?,?,?)",
                               (pids[i],pids[j],round(float(sim),3)))
                    new_pairs += 1

    # 3. 태깅된 concept_tags 기반 그룹 보강
    tagged = cur.execute("""
        SELECT concept_tags, GROUP_CONCAT(id) ids, COUNT(*) cnt
        FROM problems WHERE concept_tags!='' AND concept_tags IS NOT NULL
        GROUP BY concept_tags HAVING cnt>=2
    """).fetchall()
    tag_groups = 0
    for t in tagged:
        cur.execute("""INSERT OR IGNORE INTO similar_groups
            (group_name, group_type, topic, member_ids, created_by)
            VALUES(?,?,?,?,?)""",
            (f"TAG_{t['concept_tags']}", 'teacher',
             t['concept_tags'], json.dumps(t['ids'].split(',')[:10]), 'Mi'))
        tag_groups += 1

    conn.commit()
    total_g = conn.execute("SELECT COUNT(*) FROM similar_groups").fetchone()[0]
    total_p = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]
    conn.close()
    shutil.copy(str(TMP), str(DB_SRC))

    print(f"✅ similar_groups: {total_g}개 ({tag_groups}개 태그기반 추가)")
    print(f"✅ similar_problems: {total_p}쌍 ({new_pairs}개 신규)")

if __name__ == "__main__":
    run()
