#!/usr/bin/env python3
"""
sync_from_obsidian.py — Obsidian 마크다운 검수 결과 → DB 반영
사용법: python3 scripts/sync_from_obsidian.py

Obsidian에서 frontmatter를 직접 수정한 내용을 DB에 저장합니다.
"""
import sqlite3, shutil, re, tempfile
from pathlib import Path
from datetime import datetime

BASE     = Path(__file__).parent.parent
PROB_DIR = BASE / "wiki" / "problems"
DB_SRC   = BASE / "db" / "problems.db"
TMP_DB   = Path(tempfile.gettempdir()) / "sync_obs.db"

def parse_frontmatter(md_text):
    """마크다운 frontmatter YAML 파싱"""
    m = re.match(r'^---\n(.*?)\n---', md_text, re.DOTALL)
    if not m: return {}
    fm = {}
    for line in m.group(1).split('\n'):
        kv = re.match(r'^(\w+):\s*(.*)$', line)
        if kv:
            k, v = kv.group(1), kv.group(2).strip()
            # 따옴표 제거
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            fm[k] = v
    return fm

def run():
    if not DB_SRC.exists() or DB_SRC.stat().st_size < 10_000:
        raise RuntimeError(f"유효하지 않은 DB 파일: {DB_SRC}")
    shutil.copy(str(DB_SRC), str(TMP_DB))
    conn = sqlite3.connect(str(TMP_DB))
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")

    md_files = sorted(PROB_DIR.glob("*.md"))
    updated = 0; skipped = 0; ignored = 0

    for f in md_files:
        try:
            text = f.read_text(encoding='utf-8')
            fm   = parse_frontmatter(text)
            pid  = fm.get('id', '')
            if not pid: continue
            current = cur.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
            if not current:
                ignored += 1
                continue

            def val(key, column, default=''):
                if key in fm:
                    return fm.get(key, default)
                return current[column] if current[column] is not None else default

            s1   = val('stage1_img', 'stage1_img', 'pending')
            s1n  = val('stage1_note', 'stage1_note', '')
            s2   = val('stage2_ans', 'stage2_ans', 'pending')
            s2n  = val('stage2_note', 'stage2_note', '')
            af   = val('answer_fixed', 'stage2_answer_fixed', '')
            s3   = val('stage3_sol', 'stage3_sol', 'pending')
            s3n  = val('stage3_note', 'stage3_note', '')
            sol  = val('stage3_solution', 'stage3_solution', '')
            fg   = val('final_grade', 'final_grade', 'pending')
            trf  = val('sign_tr', 'sign_tr_final', '')
            cpf  = val('sign_cp', 'sign_cp_final', '')
            ans  = val('answer', 'answer', '')
            concept_tags = val('concept_tags', 'concept_tags', '')

            # 자동 등급 계산
            if s1=='pass' and (s2=='pass' or s2=='fixed') and s3=='pass':
                fg = 'A'
            elif s1=='pass' and (s2=='pass' or s2=='fixed'):
                fg = 'B'
            elif s1=='fail' or s2=='fail' or s3=='fail':
                fg = 'C'

            # verify_status
            if fg == 'A':
                vs = 'verified' if (trf and cpf) else 'pass'
            elif fg == 'C':
                vs = 'fix_required'
            elif fg in ('B','pending') and s1 != 'pending':
                vs = 'needs_review'
            else:
                vs = 'pending'

            # 수정 정답 반영
            final_ans = af if af else ans

            cur.execute("""UPDATE problems SET
                stage1_img=?, stage1_note=?,
                stage2_ans=?, stage2_note=?, stage2_answer_fixed=?,
                stage3_sol=?, stage3_note=?, stage3_solution=?,
                final_grade=?, verify_status=?,
                sign_tr_final=?, sign_cp_final=?,
                answer=?, concept_tags=?
                WHERE id=?""",
                (s1, s1n, s2, s2n, af, s3, s3n, sol,
                 fg, vs, trf, cpf, final_ans, concept_tags, pid))

            if cur.rowcount:
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ⚠️ {f.name}: {e}")

    conn.commit()
    conn.close()
    shutil.copy(str(TMP_DB), str(DB_SRC))

    # 통계
    shutil.copy(str(DB_SRC), str(TMP_DB))
    c2 = sqlite3.connect(str(TMP_DB))
    A  = c2.execute("SELECT COUNT(*) FROM problems WHERE final_grade='A'").fetchone()[0]
    B  = c2.execute("SELECT COUNT(*) FROM problems WHERE final_grade='B'").fetchone()[0]
    C  = c2.execute("SELECT COUNT(*) FROM problems WHERE final_grade='C'").fetchone()[0]
    sg = c2.execute("SELECT COUNT(*) FROM problems WHERE sign_tr_final!='' AND sign_cp_final!=''").fetchone()[0]
    tt = c2.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    c2.close()

    print(f"\n✅ Obsidian → DB 동기화 완료 ({now})")
    print(f"   업데이트: {updated}개 | 스킵: {skipped}개 | DB 외 노트 무시: {ignored}개")
    print(f"   A등급: {A} | B등급: {B} | C등급: {C} | 서명완료: {sg}/{tt}")

if __name__ == "__main__":
    run()
