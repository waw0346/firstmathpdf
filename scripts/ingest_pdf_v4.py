#!/usr/bin/env python3
"""
ingest_pdf_v4.py — PDF 자동 인제스트 파이프라인 v4.0
수학의 지름길 학원

사용법:
  python3 scripts/ingest_pdf_v4.py --q 문제.pdf --a 정답.pdf
  python3 scripts/ingest_pdf_v4.py --q 문제.pdf --a 정답.pdf --year 2026 --month 11 --source SU
  python3 scripts/ingest_pdf_v4.py --q 문제.pdf  (정답 나중에)

처리 순서:
  1. PDF 자동 분석 (연도·월·출처 감지)
  2. v4.0 파일명 생성
  3. 원본 보존 + 정규 이름으로 복사
  4. 정답 추출 (정답 PDF 있을 경우)
  5. 문제 크롭 이미지 생성
  6. DB 등록
  7. Obsidian 동기화
"""
import sys, re, shutil, json, argparse, sqlite3, io, subprocess, tempfile
from pathlib import Path
from datetime import datetime
import fitz

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE/'scripts'))
from id_manager_v4 import (make_exam_id, make_school_id, SOURCE_CODES,
                            SUBJECT_CODES, MONTH_NAMES)

# ── 상수 ───────────────────────────────────────────────────────
SOURCES_DIR = BASE / "sources"
CROPS_DIR   = BASE / "sources" / "crops"
DB_PATH     = BASE / "db" / "problems.db"
TMP_DB      = Path(tempfile.gettempdir()) / "ingest_v4.db"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CHAR_MAP = {'':'1','':'2','':'3','':'4','':'5',
            '':'6','':'7','':'8','':'9','':'0'}
def decode(s): return ''.join(CHAR_MAP.get(c,c) for c in s)

SUBJ_PAGES = {'확통':(8,11),'미적분':(12,15),'기하':(16,19)}
DIFF_MAP   = {
    1:'하',2:'하',3:'하',4:'하',5:'하',6:'중하',7:'중',
    8:'중하',9:'중',10:'중',11:'중',12:'중',13:'중',
    14:'중상',15:'중상',16:'중',17:'중상',18:'중상',
    19:'중상',20:'상',21:'상',22:'최상',
    23:'중',24:'중',25:'중상',26:'중상',27:'상',28:'상',
    29:'상',30:'최상',
}
DOMAIN_MAP = {
    1:("수와연산","지수와 로그"), 2:("함수","미분"),
    3:("수와연산","등비수열"),   4:("함수","함수의 연속"),
    5:("함수","미분"),           6:("삼각함수","삼각함수"),
    7:("함수","접선"),           8:("수와연산","로그"),
    9:("함수","속도와 위치"),    10:("삼각함수","삼각함수 그래프"),
    11:("함수","정적분"),        12:("수열","수열의 합"),
    13:("함수","정적분과 넓이"), 14:("기하","삼각형과 원"),
    15:("함수","함수의 극값"),   16:("수와연산","단답형"),
    17:("함수","단답형 미분"),   18:("함수","단답형 정적분"),
    19:("수열","단답형 수열"),   20:("함수","단답형 함수"),
    21:("함수","단답형 킬러"),   22:("수열","단답형 킬러"),
}
SUBJ_DOMAIN = {
    '확통':  ("확률과통계","확통 종합"),
    '미적분': ("함수","미적분 종합"),
    '기하':  ("기하","기하 종합"),
}


# ══════════════════════════════════════════════════════════════
# PDF 자동 분석
# ══════════════════════════════════════════════════════════════

def detect_pdf_info(pdf_path: Path) -> dict:
    """PDF 첫 페이지에서 연도·월·출처·학년 자동 감지"""
    doc = fitz.open(str(pdf_path))
    text = doc[0].get_text()
    doc.close()

    info = {"year": None, "month": None, "source": None, "grade": 3}

    # 연도 감지
    m = re.search(r'(20\d{2})학년도|(\d{4})년', text)
    if m:
        info["year"] = int(m.group(1) or m.group(2))

    # 출처·월 감지
    patterns = [
        (r'대학수학능력시험.*11월|수학능력시험 문제', 11, 'SU'),
        (r'6월.*모의평가|모의평가.*6월',              6,  'NA'),
        (r'9월.*모의평가|모의평가.*9월',              9,  'NA'),
        (r'3월.*전국연합|전국연합.*3월',              3,  'NA'),
        (r'5월.*전국연합|전국연합.*5월',              5,  'NA'),
        (r'7월.*전국연합|전국연합.*7월',              7,  'NA'),
        (r'10월.*전국연합|전국연합.*10월',            10, 'NA'),
        (r'4월.*학력평가|학력평가.*4월',              4,  'NA'),
    ]
    for pattern, month, src in patterns:
        if re.search(pattern, text):
            info["month"] = month
            info["source"] = src
            break

    return info


# ══════════════════════════════════════════════════════════════
# 정답 추출
# ══════════════════════════════════════════════════════════════

def extract_answers(pdf_path: Path) -> dict:
    """정답 PDF에서 1-30번 + 선택과목 정답 추출"""
    doc = fitz.open(str(pdf_path))
    full = '\n'.join(doc[pn].get_text() for pn in range(len(doc)))
    doc.close()
    answers = {}

    # 형식1: "01. ② 02. ①" (6월·9월 모의평가)
    for num, ans in re.findall(r'(\d{1,2})\.\s*(①|②|③|④|⑤)', full):
        n = int(num)
        if 1 <= n <= 22 and n not in answers: answers[n] = ans

    # 형식2: 단답형 (16-22번)
    for num, ans in re.findall(r'(?:^|\s)(\d{1,2})\.\s+(\d{1,3})(?:\s|$)', full, re.M):
        n = int(num)
        if 16 <= n <= 22: answers[n] = ans

    # 형식3: 줄별 (5월·10월 전국연합)
    if len(answers) < 15:
        lines = full.split('\n'); cur_num = None
        for l in lines:
            s = l.strip()
            m = re.match(r'^(\d{1,2})$', s)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 22: cur_num = n
            elif s in ('①','②','③','④','⑤') and cur_num:
                if cur_num not in answers: answers[cur_num] = s
            elif re.match(r'^\d{1,3}$', s) and cur_num and 16 <= cur_num <= 22:
                if cur_num not in answers: answers[cur_num] = s
                cur_num = None

    # PUA 디코딩
    lines = full.split('\n'); cur_num = None
    for l in lines:
        s = l.strip()
        m = re.match(r'^(\d{1,2})$', s)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 22: cur_num = n
        elif s and all(c in '' for c in s) and cur_num:
            if cur_num not in answers: answers[cur_num] = decode(s)
            cur_num = None

    # 선택과목
    subj_answers = {}
    for kw, subj in [('확률과 통계','확통'),('확률과통계','확통'),
                     ('미적분','미적분'),('기하','기하')]:
        idx = full.find(kw)
        if idx > 0:
            sec = full[idx:idx+600]
            sa = {}
            for num,ans in re.findall(r'(\d{1,2})\.\s*(①|②|③|④|⑤)', sec):
                n = int(num)
                if 23 <= n <= 30: sa[n] = ans
            for num,ans in re.findall(r'(?:^|\s)(2[3-9]|30)\.\s+(\d{1,3})(?:\s|$)', sec, re.M):
                sa[int(num)] = ans
            cur2 = None
            for l in sec.split('\n'):
                s = l.strip()
                m = re.match(r'^(2[3-9]|30)$', s)
                if m: cur2 = int(m.group(1))
                elif s and all(c in '' for c in s) and cur2:
                    if cur2 not in sa: sa[cur2] = decode(s)
                    cur2 = None
            if sa and subj not in subj_answers:
                subj_answers[subj] = sa

    return answers, subj_answers


# ══════════════════════════════════════════════════════════════
# 크롭 이미지 생성
# ══════════════════════════════════════════════════════════════

def crop_problems(pdf_path: Path, prefix: str,
                  page_range: tuple, num_filter=None,
                  subj: str = "", dpi: int = 250):
    """문제별 크롭 이미지 생성 (crop_all.py v19 로직 재사용)"""
    from crop_all import (get_problem_positions, crop_and_save,
                          SUBJ_PAGES as SP)
    import fitz as _fitz

    CROPS_DIR.mkdir(parents=True, exist_ok=True)
    doc = _fitz.open(str(pdf_path))
    probs = get_problem_positions(doc, page_range, num_filter)
    saved = crop_and_save(doc, probs, prefix, subj)
    doc.close()
    return saved


# ══════════════════════════════════════════════════════════════
# DB 등록
# ══════════════════════════════════════════════════════════════

def register_to_db(problems_data: list, file_id: str,
                   year: int, month: int, source: str):
    """문제 목록을 DB에 등록 (기존 ID 있으면 skip)"""
    shutil.copy(str(DB_PATH), str(TMP_DB))
    import time; time.sleep(0.3)
    conn = sqlite3.connect(str(TMP_DB))
    cur  = conn.cursor()
    now  = datetime.now().strftime('%Y-%m-%d %H:%M')
    inserted = 0

    for p in problems_data:
        pid   = p['id']
        new_id = p['new_id']
        num   = p['num']
        ans   = p.get('answer','')
        subj  = p.get('subj','')
        domain, topic = DOMAIN_MAP.get(num, ("기타","기타"))
        if subj: domain, topic = SUBJ_DOMAIN.get(subj, (domain, topic))
        diff  = DIFF_MAP.get(num,'중')
        crop  = p.get('crop_path','')

        cur.execute("SELECT id FROM problems WHERE id=?", (pid,))
        if cur.fetchone():
            cur.execute("""UPDATE problems SET answer=?, crop_path=?,
                new_id=?, month=?, source_code=?
                WHERE id=?""", (ans, crop, new_id, month, source, pid))
        else:
            cur.execute("""INSERT INTO problems
                (id, new_id, title, grade, domain, topic, difficulty,
                 source_type, year, month, school, exam_type, answer,
                 problem_number, crop_path, source_code,
                 verify_status, stage1_img, stage2_ans, final_grade, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'needs_review','pending','pending','pending',?)""",
                (pid, new_id, f"{num}번", '고3', domain, topic, diff,
                 '수능' if source=='SU' else '모의고사',
                 year, month,
                 '수능' if source=='SU' else f"{month}월모의",
                 '수능' if source=='SU' else '모의고사',
                 ans, num, crop, source, now))
            inserted += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    conn.close()
    shutil.copy(str(TMP_DB), str(DB_PATH))
    return inserted, total


def run_post_ingest_audit() -> bool:
    """Apply source trace index and run crop audit after ingest.

    This step does not edit original PDFs, problem text, answers, or solutions.
    It only updates the separate problem_source_trace index and writes reports.
    """
    checks = [
        ("원본 역추적 색인", [sys.executable, "scripts/source_trace_index.py", "--apply"]),
        ("크롭 파이프라인 감사", [sys.executable, "scripts/crop_pipeline_audit.py"]),
    ]
    ok = True
    for label, cmd in checks:
        run = subprocess.run(
            cmd,
            cwd=str(BASE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if run.returncode == 0:
            print(f"  ✅ {label} 완료")
        else:
            ok = False
            detail = (run.stderr or run.stdout).strip().splitlines()
            print(f"  ⚠️  {label} 실패: {detail[-1] if detail else 'unknown error'}")
    return ok


# ══════════════════════════════════════════════════════════════
# 메인 파이프라인
# ══════════════════════════════════════════════════════════════

def run(q_path: Path, a_path=None,
        year=None, month=None, source=None,
        grade=1, region=None, school=None,
        post_audit=True):

    print(f"\n{'='*60}")
    print(f"📥 인제스트 시작: {q_path.name}")
    print(f"{'='*60}")

    # ── 1. PDF 자동 분석 ──────────────────────────────────────
    print("\n[1/7] PDF 자동 분석...")
    info = detect_pdf_info(q_path)
    if not year:   year   = info.get('year') or int(input("연도 입력: "))
    if not month:  month  = info.get('month') or int(input("월 입력 (1-12): "))
    if not source: source = info.get('source') or input("출처코드 (SU/NA 등): ").upper()

    print(f"  연도: {year}, 월: {month}, 출처: {source}({SOURCE_CODES.get(source,'?')})")

    # ── 2. v4.0 파일명 생성 ───────────────────────────────────
    print("\n[2/7] v4.0 파일명 생성...")
    if region and school:
        file_id = make_school_id(year, month, grade, region, school)
    else:
        file_id = make_exam_id(year, month, source)

    print(f"  파일 ID: {file_id}")
    print(f"  문제지:  {file_id}_Q.pdf")
    print(f"  정답지:  {file_id}_A.pdf")
    print(f"  해설지:  {file_id}_S.pdf")

    # ── 3. 원본 보존 + 정규 이름으로 복사 ────────────────────
    print("\n[3/7] 파일 복사 (원본 보존)...")
    year_dir = SOURCES_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    q_dest = year_dir / f"{file_id}_Q.pdf"
    if not q_dest.exists():
        shutil.copy(str(q_path), str(q_dest))
        print(f"  ✅ 문제지 복사: {q_dest.name}")
    else:
        print(f"  - 문제지 이미 존재: {q_dest.name}")

    if a_path and a_path.exists():
        a_dest = year_dir / f"{file_id}_A.pdf"
        if not a_dest.exists():
            shutil.copy(str(a_path), str(a_dest))
            print(f"  ✅ 정답지 복사: {a_dest.name}")

    # ── 4. 정답 추출 ──────────────────────────────────────────
    print("\n[4/7] 정답 추출...")
    common_ans, subj_ans = {}, {}
    if a_path and a_path.exists():
        common_ans, subj_ans = extract_answers(a_path)
        print(f"  공통 {len(common_ans)}개, 선택과목 {sum(len(v) for v in subj_ans.values())}개")
        for s, a in subj_ans.items():
            print(f"    {s}: {a}")
    else:
        print("  ⚠️  정답 파일 없음 (나중에 추가 가능)")

    # ── 5. 크롭 이미지 생성 ───────────────────────────────────
    print("\n[5/7] 문제 크롭 이미지 생성...")
    try:
        from crop_all import get_problem_positions, crop_and_save
        import fitz as _fitz
        doc = _fitz.open(str(q_path))

        # 공통 1-22번
        probs = get_problem_positions(doc, (0,7))
        saved_common = crop_and_save(doc, probs, f"{year}_{'수능' if source=='SU' else f'{month}월모의'}_고3")
        print(f"  공통: {len(saved_common)}개")

        # 선택과목 23-30번
        saved_subj = {}
        for subj, pages in SUBJ_PAGES.items():
            sp = get_problem_positions(doc, pages, num_filter=range(23,31))
            ss = crop_and_save(doc, sp,
                               f"{year}_{'수능' if source=='SU' else f'{month}월모의'}_고3",
                               subj)
            saved_subj[subj] = ss
            print(f"  {subj}: {len(ss)}개")
        doc.close()
    except Exception as e:
        print(f"  ⚠️  크롭 오류: {e} (수동 실행: python3 scripts/crop_all.py {year})")
        saved_common, saved_subj = {}, {}

    # ── 6. DB 등록 ────────────────────────────────────────────
    print("\n[6/7] DB 등록...")
    prefix = f"{year}_{'수능' if source=='SU' else f'{month}월모의'}_고3"
    problems_data = []

    # 공통
    for num in range(1, 23):
        pid    = f"{prefix}_{num:03d}"
        new_id = f"{file_id}-{'S' if num>=16 else 'Q'}{num:03d}"
        crop   = saved_common.get(num, f"sources/crops/{prefix}_{num:03d}.jpg")
        problems_data.append({"id":pid,"new_id":new_id,"num":num,
                               "answer":common_ans.get(num,''),"crop_path":crop})

    # 선택과목
    SUBJ_CODE = {'확통':'_SS','미적분':'_C1','기하':'_G'}
    for subj, ans_map in [('확통', subj_ans.get('확통',{})),
                           ('미적분', subj_ans.get('미적분',{})),
                           ('기하', subj_ans.get('기하',{}))]:
        sfx = SUBJ_CODE[subj]
        for num in range(23, 31):
            pid    = f"{prefix}_{subj}_{num:03d}"
            new_id = f"{file_id}{sfx}-{'S' if num>=29 else 'Q'}{num:03d}"
            crop   = saved_subj.get(subj,{}).get(num,
                     f"sources/crops/{prefix}_{subj}_{num:03d}.jpg")
            problems_data.append({"id":pid,"new_id":new_id,"num":num,
                                   "answer":ans_map.get(num,''),
                                   "subj":subj,"crop_path":crop})

    inserted, total = register_to_db(problems_data, file_id, year, month, source)
    print(f"  ✅ DB 등록: {inserted}개 신규 (전체 {total}개)")

    # ── 7. Obsidian 동기화 ────────────────────────────────────
    print("\n[7/7] Obsidian 동기화...")
    import subprocess
    r = subprocess.run(['python3','scripts/obsidian_sync.py'],
                      capture_output=True, text=True, cwd=str(BASE))
    if r.returncode == 0:
        print("  ✅ 동기화 완료")
    else:
        print(f"  ⚠️  동기화 오류: {r.stderr[:100]}")

    # ── 8. 후속 안전 감사 ────────────────────────────────────
    if post_audit:
        print("\n[8/8] 원본 역추적/크롭 안전 감사...")
        audit_ok = run_post_ingest_audit()
        if not audit_ok:
            print("  ⚠️  후속 감사에 실패했습니다. 원본/문제/정답/해설은 변경하지 않았습니다.")
    else:
        print("\n[8/8] 원본 역추적/크롭 안전 감사 건너뜀")

    print(f"\n{'='*60}")
    print(f"✅ 인제스트 완료!")
    print(f"   파일 ID: {file_id}")
    print(f"   문제 수: {len(problems_data)}개")
    print(f"   원본 위치: {q_path}")
    print(f"   정규 위치: {q_dest}")
    print(f"{'='*60}\n")
    return file_id


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="PDF 자동 인제스트 v4.0")
    parser.add_argument("--q",      required=True,   help="문제 PDF 경로")
    parser.add_argument("--a",      default=None,    help="정답 PDF 경로")
    parser.add_argument("--year",   type=int,        help="연도 (자동감지 실패시)")
    parser.add_argument("--month",  type=int,        help="월 (자동감지 실패시)")
    parser.add_argument("--source", default=None,    help="출처 코드 (SU/NA 등)")
    parser.add_argument("--grade",  type=int,default=3, help="학년 (기본:3)")
    parser.add_argument("--region", default=None,    help="지역 코드 (내신용)")
    parser.add_argument("--school", default=None,    help="학교명 (내신용)")
    parser.add_argument("--skip-post-audit", action="store_true", help="인제스트 후 원본 역추적/크롭 감사를 건너뜀")
    args = parser.parse_args()

    q = Path(args.q)
    a = Path(args.a) if args.a else None
    if not q.exists():
        print(f"❌ 파일 없음: {q}"); sys.exit(1)

    run(q, a, args.year, args.month, args.source,
        args.grade, args.region, args.school,
        post_audit=not args.skip_post_audit)


if __name__ == "__main__":
    main()
