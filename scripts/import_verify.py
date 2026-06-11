#!/usr/bin/env python3
"""
import_verify.py — 검수 대시보드 결과를 DB에 반영
사용법: python3 scripts/import_verify.py verify_results_2026-05-30.json
"""
import json, sqlite3, shutil, sys
from pathlib import Path
from datetime import datetime

BASE   = Path(__file__).parent.parent
DB_SRC = BASE / "db" / "problems.db"
TMP    = Path("/tmp/import_verify.db")

def run(json_path: str):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    shutil.copy(str(DB_SRC), str(TMP))
    conn = sqlite3.connect(str(TMP))
    cur  = conn.cursor()
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")

    updated = 0
    for item in data:
        pid = item.get("id")
        if not pid: continue
        final = item.get("final","pending")
        # 2단계에서 정답 수정된 경우 answer도 업데이트
        ans_fix = item.get("ans_fix","").strip()
        
        cur.execute("""UPDATE problems SET
            stage1_img=?, stage1_note=?,
            stage2_ans=?, stage2_note=?, stage2_answer_fixed=?,
            stage3_sol=?, stage3_note=?, stage3_solution=?,
            final_grade=?, verify_status=?, checked_at=?
            WHERE id=?""",
            (item.get("s1","pending"), item.get("s1note",""),
             item.get("s2","pending"), item.get("s2note",""), ans_fix,
             item.get("s3","pending"), item.get("s3note",""), item.get("sol",""),
             final,
             "verified" if final=="A" else "needs_review" if final=="C" else "pass",
             now, pid))
        
        # 수정 정답 반영
        if ans_fix and item.get("s2") == "fixed":
            cur.execute("UPDATE problems SET answer=? WHERE id=?", (ans_fix, pid))
            print(f"  🔧 정답 수정: {pid} → {ans_fix}")
        
        if cur.rowcount: updated += 1

    conn.commit()
    conn.close()
    shutil.copy(str(TMP), str(DB_SRC))
    
    a = sum(1 for i in data if i.get("final")=="A")
    b = sum(1 for i in data if i.get("final")=="B")
    c = sum(1 for i in data if i.get("final")=="C")
    print(f"\n✅ DB 반영 완료: {updated}개")
    print(f"  A등급(완전): {a}개 | B등급(부분): {b}개 | C등급(재작업): {c}개")
    print(f"\n다음 단계:")
    print(f"  python3 scripts/verify.py        # 검증 리포트 갱신")
    print(f"  python3 scripts/obsidian_sync.py  # Obsidian 마크다운 갱신")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 scripts/import_verify.py <json파일>")
        sys.exit(1)
    run(sys.argv[1])
