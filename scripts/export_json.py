#!/usr/bin/env python3
"""
대시보드(dashboard.html)에서 사용할 JSON 내보내기
python scripts/export_json.py
"""
import json, sqlite3, sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "db" / "problems.db"
OUT_PATH = BASE_DIR / "db" / "problems_export.json"

if not DB_PATH.exists():
    print("DB 없음. ingest.py를 먼저 실행하세요.")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 문제 목록
rows = conn.execute("""
    SELECT p.*, GROUP_CONCAT(sp.similar_id, '|') as similar_ids_str
    FROM problems p
    LEFT JOIN similar_problems sp ON p.id = sp.problem_id
    GROUP BY p.id
    ORDER BY p.year DESC, p.school
""").fetchall()

problems = []
for r in rows:
    d = dict(r)
    import json as _json
    d["concept"] = _json.loads(d.get("concept") or "[]")
    d["tags"]    = _json.loads(d.get("tags") or "[]")
    d["similar_ids"] = [x for x in (d.pop("similar_ids_str", "") or "").split("|") if x]
    # raw_text는 미리보기용으로 300자 제한
    d["raw_text_preview"] = (d.get("raw_text") or "")[:300]
    problems.append(d)

OUT_PATH.write_text(json.dumps(problems, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✅ {len(problems)}개 문제 내보내기 완료 → {OUT_PATH}")
print(f"   크기: {OUT_PATH.stat().st_size / 1024:.1f} KB")
