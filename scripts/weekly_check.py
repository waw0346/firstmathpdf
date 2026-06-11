#!/usr/bin/env python3
"""
weekly_check.py — 주간 필수 관리 점검 스크립트
수학의 지름길 학원 LLM-Wiki

매주 실행: python3 scripts/weekly_check.py
또는: 주간점검.bat 더블클릭

점검 항목:
  1. DB 스냅샷 생성
  2. 유사문제 그룹 갱신
  3. 이미지 품질 점검 (인턴 에이전트)
  4. 검수 진행률 확인
  5. 새 PDF 탐지
  6. ADMINLOG 갱신
  7. Obsidian 동기화
  8. 외부 백업 알림
"""
import sqlite3, shutil, subprocess, json
from pathlib import Path
from datetime import datetime
from PIL import Image

BASE   = Path(__file__).parent.parent
DB_SRC = BASE / "db" / "problems.db"
SNAP   = BASE / "db" / "snapshots"
NOW    = datetime.now().strftime("%Y-%m-%d %H:%M")
TODAY  = datetime.now().strftime("%Y-%m-%d")
WEEK   = datetime.now().strftime("%Y-W%W")

print(f"\n{'='*60}")
print(f"🔄 주간 필수 점검 — {TODAY}")
print(f"{'='*60}\n")

RESULTS = {}

# ──────────────────────────────────────────────────────────────
# 1. DB 스냅샷 생성
# ──────────────────────────────────────────────────────────────
print("[1/8] DB 스냅샷 생성...")
snap_name = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}_주간백업_{WEEK}.db"
snap_path = SNAP / snap_name
shutil.copy(str(DB_SRC), str(snap_path))
snap_size = snap_path.stat().st_size // 1024
print(f"  ✅ {snap_name} ({snap_size}KB)")
RESULTS["snapshot"] = snap_name

# ──────────────────────────────────────────────────────────────
# 2. 유사문제 그룹 갱신
# ──────────────────────────────────────────────────────────────
print("\n[2/8] 유사문제 그룹 갱신...")
r = subprocess.run(["python3","scripts/update_similar_groups.py"],
                   capture_output=True, text=True, cwd=str(BASE))
if r.returncode == 0:
    lines = [l for l in r.stdout.strip().split('\n') if '✅' in l]
    for l in lines: print(f"  {l.strip()}")
    RESULTS["similar"] = "ok"
else:
    print(f"  ⚠️  오류: {r.stderr[:80]}")
    RESULTS["similar"] = "error"

# ──────────────────────────────────────────────────────────────
# 3. 이미지 품질 점검
# ──────────────────────────────────────────────────────────────
print("\n[3/8] 이미지 품질 점검...")
crops = BASE / "sources" / "crops"
ok=0; bad=[]
for f in crops.glob("*.jpg"):
    if "H253" in f.name: continue
    try:
        img = Image.open(f)
        h = img.size[1]
        if h < 100 or h > 4500:
            bad.append(f"{f.name}:{h}px")
        else: ok += 1
    except: bad.append(f"{f.name}:읽기실패")
print(f"  ✅ 정상: {ok}개  ❌ 이상: {len(bad)}개")
if bad:
    for b in bad[:3]: print(f"     {b}")
    print(f"     → CODE: python3 scripts/crop_all.py 로 재크롭")
RESULTS["images"] = {"ok": ok, "bad": len(bad)}

# ──────────────────────────────────────────────────────────────
# 4. 검수 진행률 확인
# ──────────────────────────────────────────────────────────────
print("\n[4/8] 검수 진행률...")
shutil.copy(str(DB_SRC), "/tmp/wc_check.db")
import time; time.sleep(0.3)
conn = sqlite3.connect("/tmp/wc_check.db")
total   = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
s1_done = conn.execute("SELECT COUNT(*) FROM problems WHERE stage1_img='pass'").fetchone()[0]
s2_done = conn.execute("SELECT COUNT(*) FROM problems WHERE stage2_ans='pass'").fetchone()[0]
s3_done = conn.execute("SELECT COUNT(*) FROM problems WHERE stage3_sol='pass'").fetchone()[0]
a_grade = conn.execute("SELECT COUNT(*) FROM problems WHERE final_grade='A'").fetchone()[0]
mi_sign = conn.execute("SELECT COUNT(*) FROM problems WHERE sign_tr_final!='' AND sign_tr_final IS NOT NULL").fetchone()[0]
cp_sign = conn.execute("SELECT COUNT(*) FROM problems WHERE sign_cp_final!='' AND sign_cp_final IS NOT NULL").fetchone()[0]
tagged  = conn.execute("SELECT COUNT(*) FROM problems WHERE concept_tags!='' AND concept_tags IS NOT NULL").fetchone()[0]
sim_cnt = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]

# 새 문제 (이번 주 추가)
new_this_week = conn.execute(
    f"SELECT COUNT(*) FROM problems WHERE created_at >= date('{TODAY}','-7 days')"
).fetchone()[0]
conn.close()

pct = lambda n: f"{n}/{total} ({n*100//total}%)"
print(f"  총 문제:      {total}개  (이번주 신규: {new_this_week}개)")
print(f"  1단계 이미지: {pct(s1_done)}")
print(f"  2단계 정답:   {pct(s2_done)}")
print(f"  3단계 해설:   {pct(s3_done)}")
print(f"  A등급 완료:   {pct(a_grade)}")
print(f"  Mi 서명:      {pct(mi_sign)}")
print(f"  cp 서명:      {pct(cp_sign)}")
print(f"  개념 태깅:    {pct(tagged)}")
print(f"  유사문제 쌍:  {sim_cnt}쌍")
RESULTS["review"] = {"total":total,"a_grade":a_grade,"tagged":tagged,"similar":sim_cnt}

# ──────────────────────────────────────────────────────────────
# 5. 새 PDF 탐지
# ──────────────────────────────────────────────────────────────
print("\n[5/8] 새 PDF 탐지...")
sources = BASE / "sources"
all_pdfs = list(sources.rglob("*.pdf"))
# DB에 등록된 파일 목록 (file_registry)
shutil.copy(str(DB_SRC), "/tmp/wc_pdf.db")
time.sleep(0.3)
conn2 = sqlite3.connect("/tmp/wc_pdf.db")
registered = set(r[0] for r in conn2.execute("SELECT file_path_q FROM file_registry WHERE file_path_q!=''").fetchall())
conn2.close()
new_pdfs = [p for p in all_pdfs if str(p.relative_to(BASE)) not in registered
            and "정답" not in p.name and "해설" not in p.name]
if new_pdfs:
    print(f"  ⚠️  미등록 PDF {len(new_pdfs)}개 발견:")
    for p in new_pdfs[:3]:
        print(f"     {p.relative_to(BASE)}")
    print(f"     → DB: python3 scripts/ingest_pdf_v4.py --q <파일>")
else:
    print(f"  ✅ 미등록 PDF 없음 (총 {len(all_pdfs)}개 파일)")
RESULTS["new_pdfs"] = len(new_pdfs)

# ──────────────────────────────────────────────────────────────
# 6. ADMINLOG 주간 갱신
# ──────────────────────────────────────────────────────────────
print("\n[6/8] ADMINLOG 갱신...")
admin = BASE / "ADMINLOG.md"
content = admin.read_text(encoding="utf-8")
weekly_note = f"""

---

## 📅 주간 점검 — {TODAY} ({WEEK})

| 항목 | 현황 |
|------|------|
| 총 문제 | {total}개 |
| A등급 완료 | {a_grade}개 ({a_grade*100//total}%) |
| 유사문제 쌍 | {sim_cnt}쌍 |
| 개념 태깅 | {tagged}개 ({tagged*100//total}%) |
| 이미지 이상 | {len(bad)}개 |
| 스냅샷 | {snap_name} |
"""
# 오늘 날짜 항목이 없을 때만 추가
if f"주간 점검 — {TODAY}" not in content:
    admin.write_text(content.rstrip() + weekly_note, encoding="utf-8")
    print(f"  ✅ ADMINLOG 갱신")
else:
    print(f"  - 오늘 이미 갱신됨")

# ──────────────────────────────────────────────────────────────
# 7. Obsidian 동기화
# ──────────────────────────────────────────────────────────────
print("\n[7/8] Obsidian 동기화...")
r2 = subprocess.run(["python3","scripts/obsidian_sync.py"],
                    capture_output=True, text=True, cwd=str(BASE))
if r2.returncode == 0:
    print(f"  ✅ 동기화 완료")
    RESULTS["obsidian"] = "ok"
else:
    print(f"  ⚠️  {r2.stderr[:80]}")
    RESULTS["obsidian"] = "error"

# ──────────────────────────────────────────────────────────────
# 8. 외부 백업 알림
# ──────────────────────────────────────────────────────────────
print("\n[8/8] 외부 백업 확인...")
snaps = sorted(SNAP.glob("snap_*.db"), reverse=True)
print(f"  스냅샷 {len(snaps)}개 보관 중")
print(f"  최신: {snaps[0].name if snaps else '없음'}")
print(f"""
  ⚠️  수동 백업 필요:
     math_llm/ 폴더 전체를 외부 드라이브 또는
     OneDrive/Google Drive에 복사하세요!
""")

# ──────────────────────────────────────────────────────────────
# 최종 리포트
# ──────────────────────────────────────────────────────────────
print(f"{'='*60}")
print(f"📊 주간 점검 완료 — {NOW}")
print(f"{'='*60}")
all_ok = RESULTS.get("similar")=="ok" and RESULTS.get("obsidian")=="ok" and RESULTS["images"]["bad"]==0
status = "✅ 정상" if all_ok else "⚠️  주의 필요"
print(f"\n  최종 상태: {status}")
print(f"  A등급 진행: {a_grade}/{total} ({a_grade*100//total}%)")
print(f"  다음 목표: {'Mi·cp 서명 완료 → 100% A등급' if a_grade < total else '🏆 완료!'}")
print(f"\n  Obsidian에서 Ctrl+R 눌러 새로고침하세요\n")
