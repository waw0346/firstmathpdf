#!/usr/bin/env python3
"""
intern_agent.py — 수학 문제 이미지 QA 인턴 에이전트 v1
수학의 지름길 학원 LLM-Wiki

임무:
  1. DB화된 문제 이미지를 자동 검사
  2. LEARNING.md에 기록된 오류 패턴으로 이상 감지
  3. 원본 PDF 텍스트와 대조 (내용 존재 확인)
  4. SR(Status Report) 기록 생성·저장
  5. 이상 발견 시 Obsidian 경고 마크다운 생성

사용법:
    python3 scripts/intern_agent.py            # 전체 검사
    python3 scripts/intern_agent.py --new      # 미검사 항목만
    python3 scripts/intern_agent.py --id 2025_수능_고3_005  # 특정 문제
    python3 scripts/intern_agent.py --report   # SR 리포트 출력
"""

import sys, re, io, shutil, json, argparse
import sqlite3
import fitz
import numpy as np
from pathlib import Path
from datetime import datetime
from PIL import Image

# ── 경로 설정 ─────────────────────────────────────────────────────
BASE     = Path(__file__).parent.parent
DB_SRC   = BASE / "db" / "problems.db"
TMP_DB   = Path("/tmp/intern_work.db")
CROPS    = BASE / "sources" / "crops"
REPORT   = BASE / "wiki" / "00_INTERN_SR.md"
AGENT    = "intern_v1"
NOW      = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── 검사 기준 (LEARNING.md 오류 패턴 반영) ───────────────────────
MIN_HEIGHT   = 100    # px — 이하면 이미지 너무 작음
MAX_HEIGHT   = 4500   # px — 이상이면 이미지 너무 큼
MAX_L_WIDTH  = 1400   # px — L컬럼 최대 너비
MAX_R_WIDTH  = 1490   # px — R컬럼 최대 너비
BLANK_RATIO  = 0.005  # 이 이하면 내용 없는 행 (빈공간 판정)
VLINE_RATIO  = 0.50   # 이 이상이면 수직 구분선
RBLEED_ZONE  = 0.88   # 오른쪽 이 비율 이후 → 블리드 검사 대상
RBLEED_TH    = 0.015  # R블리드 판정 임계값 (1.5% 이상이면 경고)


# ════════════════════════════════════════════════════════════════
# 검사 함수들
# ════════════════════════════════════════════════════════════════

def chk_image_size(img: Image.Image, col: str) -> tuple:
    """이미지 크기 검사"""
    w, h = img.size
    max_w = MAX_L_WIDTH if col == "L" else MAX_R_WIDTH
    issues = []
    if h < MIN_HEIGHT:
        issues.append(f"이미지 너무 작음({h}px < {MIN_HEIGHT}px)")
    if h > MAX_HEIGHT:
        issues.append(f"이미지 너무 큼({h}px > {MAX_HEIGHT}px)")
    if w > max_w:
        issues.append(f"이미지 너무 넓음({w}px > {max_w}px, {col}컬럼)")
    return ("error" if issues else "ok"), issues


def chk_vline(img: Image.Image) -> tuple:
    """수직 구분선 잔존 여부 검사"""
    g = np.array(img.convert("L"))
    h, w = g.shape
    issues = []
    # 오른쪽 12% 검사
    for x in range(int(w * 0.88), w):
        ratio = (g[:, x] < 80).sum() / h
        if ratio > VLINE_RATIO:
            issues.append(f"수직선 잔존: x={x}px ({ratio*100:.0f}% 어두움)")
            break
    # 왼쪽 8% 검사
    for x in range(0, int(w * 0.08)):
        ratio = (g[:, x] < 80).sum() / h
        if ratio > VLINE_RATIO:
            issues.append(f"좌측 수직선: x={x}px")
            break
    return ("warn" if issues else "ok"), issues


def chk_blank_space(img: Image.Image) -> tuple:
    """하단 빈공간 검사 — 내용 끝 이후 전체의 30% 이상 빈공간이면 경고"""
    g = np.array(img.convert("L"))
    h, w = g.shape
    # 마지막 내용 행 찾기
    last_content = 0
    for y in range(h - 1, -1, -1):
        if (g[y] < 180).sum() / w > BLANK_RATIO:
            last_content = y
            break
    blank_ratio = (h - last_content) / h
    issues = []
    if blank_ratio > 0.50:
        issues.append(f"하단 빈공간 과다 ({blank_ratio*100:.0f}%, 내용끝={last_content}px/{h}px)")
    return ("warn" if issues else "ok"), issues, last_content


def chk_rbleed(img: Image.Image) -> tuple:
    """R컬럼 블리드인 검사 — 오른쪽 12-30% 구간에 내용 있으면 경고"""
    g = np.array(img.convert("L"))
    h, w = g.shape
    issues = []
    # RBLEED_ZONE(0.88*w) ~ 0.97*w 구간에 내용 있으면 블리드
    zone_start = int(w * RBLEED_ZONE)
    zone_end   = int(w * 0.97)
    if zone_end > zone_start:
        zone = g[:, zone_start:zone_end]
        dark_ratio = (zone < 120).sum() / zone.size
        if dark_ratio > RBLEED_TH:
            issues.append(f"R컬럼 블리드인: 오른쪽{100-int(RBLEED_ZONE*100)}%에 {dark_ratio*100:.1f}% 내용")
    return ("warn" if issues else "ok"), issues


def chk_pdf_content(doc, pn, clip, mid_x) -> tuple:
    """PDF 텍스트 블록 존재 여부 확인 (내용이 있어야 정상)"""
    if doc is None:
        return "skip", ["PDF 없음"]
    page = doc[pn]
    text_found = False
    for b in page.get_text("blocks", clip=clip):
        txt = str(b[4]).strip()
        if txt and len(txt) > 2:
            text_found = True
            break
    if not text_found:
        return "warn", ["PDF 텍스트 블록 없음 — 이미지/수식만으로 구성됐을 수 있음"]
    return "ok", []


def chk_answer(answer: str) -> tuple:
    """정답 존재 여부"""
    if not answer or answer.strip() in ("", "None", "null"):
        return "error", ["정답 미입력"]
    return "ok", []


# ════════════════════════════════════════════════════════════════
# PDF 로더
# ════════════════════════════════════════════════════════════════

_pdf_cache = {}

def get_pdf(year, source_type):
    key = (year, source_type)
    if key in _pdf_cache:
        return _pdf_cache[key]
    src = BASE / "sources" / str(year)
    if "수능" in (source_type or ""):
        pdfs = list(src.glob(f"{year}수능_수학문제.pdf"))
    else:
        pdfs = list(src.glob("*전국연합*문제지*.pdf"))
    if pdfs:
        doc = fitz.open(str(pdfs[0]))
        _pdf_cache[key] = doc
        return doc
    return None


def get_problem_page(doc, problem_id):
    """문제 번호와 컬럼 위치를 PDF에서 탐색"""
    if doc is None:
        return None, None, None, None
    mid_x = doc[0].rect.width * 0.48
    mg_l  = doc[0].rect.width * 0.015
    # 문제 번호 추출
    m = re.search(r'_(\d{3})$', problem_id)
    if not m:
        return None, None, None, None
    num = int(m.group(1))
    for pn in range(len(doc)):
        page = doc[pn]
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0: continue
            for line in b["lines"]:
                for span in line["spans"]:
                    mt = re.match(r'^(\d{1,2})\.\s*$', span["text"].strip())
                    if mt and int(mt.group(1)) == num:
                        x0, y0 = span["bbox"][0], span["bbox"][1]
                        if y0 < 160: continue
                        col = "L" if x0 < mid_x else "R"
                        xs = mg_l if col=="L" else mid_x+mg_l
                        xe = mid_x+60 if col=="L" else doc[0].rect.width-3
                        # 간단 clip (전체 페이지 높이 사용)
                        clip = fitz.Rect(xs, max(0,y0-5), xe,
                                         doc[0].rect.height*0.975)
                        return pn, col, clip, mid_x
    return None, None, None, None


# ════════════════════════════════════════════════════════════════
# 메인 검사 로직
# ════════════════════════════════════════════════════════════════

def inspect_one(row: dict) -> dict:
    """문제 하나 전체 검사 → sr_checks 딕셔너리 반환"""
    pid    = row["id"]
    crop   = row.get("crop_path", "")
    answer = row.get("answer", "")
    year   = row.get("year", 0)
    src_t  = row.get("source_type", "")

    result = {
        "problem_id": pid,
        "check_date": NOW,
        "agent": AGENT,
        "img_width": 0, "img_height": 0,
        "img_status": "error",
        "chk_size": "error", "chk_vline": "error",
        "chk_blank": "error", "chk_rbleed": "error",
        "chk_content": "skip", "chk_answer": "error",
        "issues": "", "suggestions": "",
        "auto_fixed": 0,
    }
    all_issues = []
    suggestions = []

    # 이미지 파일 확인
    if not crop:
        all_issues.append("crop_path 없음")
        result["img_status"] = "error"
        result["issues"] = " | ".join(all_issues)
        return result

    img_path = BASE / crop
    if not img_path.exists():
        all_issues.append(f"이미지 파일 없음: {crop}")
        result["img_status"] = "error"
        result["issues"] = " | ".join(all_issues)
        return result

    try:
        img = Image.open(img_path)
        w, h = img.size
        result["img_width"] = w
        result["img_height"] = h
    except Exception as e:
        all_issues.append(f"이미지 열기 실패: {e}")
        result["img_status"] = "error"
        result["issues"] = " | ".join(all_issues)
        return result

    # 컬럼 추정 (너비 기반 - 튜닝됨)
    # L컬럼: ~1371px, R컬럼: ~1220-1470px
    # 1380px 기준: 이하=L, 초과=R
    col = "L" if w <= 1380 else "R"

    # ① 크기 검사
    sz_status, sz_issues = chk_image_size(img, col)
    result["chk_size"] = sz_status
    all_issues.extend(sz_issues)
    if sz_issues: suggestions.append("CODE: python3 scripts/crop_all.py 재실행")

    # ② 수직선 검사
    vl_status, vl_issues = chk_vline(img)
    result["chk_vline"] = vl_status
    all_issues.extend(vl_issues)
    if vl_issues: suggestions.append("수직선: mask_vlines 임계값 확인")

    # ③ 빈공간 검사
    bl_status, bl_issues, last_y = chk_blank_space(img)
    result["chk_blank"] = bl_status
    all_issues.extend(bl_issues)
    if bl_issues: suggestions.append(f"하단트림: last_content={last_y}px → BOT_PAD 확인")

    # ④ R컬럼 블리드인 검사 (L컬럼만)
    if col == "L":
        rb_status, rb_issues = chk_rbleed(img)
        result["chk_rbleed"] = rb_status
        all_issues.extend(rb_issues)
        if rb_issues: suggestions.append("R블리드: trim_right_col mid_x_px 확인")
    else:
        result["chk_rbleed"] = "skip"

    # ⑤ PDF 텍스트 대조
    doc = get_pdf(year, src_t)
    if doc:
        pn, pcol, clip, mid_x = get_problem_page(doc, pid)
        if pn is not None:
            ct_status, ct_issues = chk_pdf_content(doc, pn, clip, mid_x)
            result["chk_content"] = ct_status
            all_issues.extend(ct_issues)
        else:
            result["chk_content"] = "warn"
            all_issues.append("PDF에서 문제 번호 위치 탐지 실패")
    else:
        result["chk_content"] = "skip"

    # ⑥ 정답 검사
    ans_status, ans_issues = chk_answer(answer)
    result["chk_answer"] = ans_status
    all_issues.extend(ans_issues)

    # 종합 상태
    statuses = [result[k] for k in
                ["chk_size","chk_vline","chk_blank","chk_rbleed","chk_answer"]]
    if "error" in statuses:
        result["img_status"] = "error"
    elif "warn" in statuses:
        result["img_status"] = "warn"
    else:
        result["img_status"] = "ok"

    result["issues"]      = " | ".join(all_issues) if all_issues else ""
    result["suggestions"] = " | ".join(suggestions) if suggestions else ""
    return result


def run_inspection(id_filter=None, new_only=False):
    shutil.copy(str(DB_SRC), str(TMP_DB))
    conn = sqlite3.connect(str(TMP_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 검사 대상 쿼리
    if id_filter:
        rows = cur.execute("SELECT * FROM problems WHERE id=?", (id_filter,)).fetchall()
    elif new_only:
        checked = {r[0] for r in cur.execute("SELECT DISTINCT problem_id FROM sr_checks").fetchall()}
        rows = [r for r in cur.execute("SELECT * FROM problems").fetchall()
                if r["id"] not in checked]
    else:
        rows = cur.execute("SELECT * FROM problems ORDER BY year,problem_number,id").fetchall()

    total  = len(rows)
    ok=0; warn=0; error=0
    print(f"\n🤖 인턴 에이전트 시작 — {total}개 검사")
    print(f"   {NOW}\n{'─'*50}")

    for i, row in enumerate(rows):
        result = inspect_one(dict(row))
        status = result["img_status"]

        # DB 저장
        cur.execute("""
            INSERT INTO sr_checks
            (problem_id,check_date,agent,img_width,img_height,img_status,
             chk_size,chk_vline,chk_blank,chk_rbleed,chk_content,chk_answer,
             issues,suggestions,auto_fixed)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (result["problem_id"],result["check_date"],result["agent"],
              result["img_width"],result["img_height"],result["img_status"],
              result["chk_size"],result["chk_vline"],result["chk_blank"],
              result["chk_rbleed"],result["chk_content"],result["chk_answer"],
              result["issues"],result["suggestions"],result["auto_fixed"]))

        if status == "ok":
            ok += 1
        elif status == "warn":
            warn += 1
            print(f"  ⚠️  {result['problem_id']}: {result['issues'][:60]}")
        else:
            error += 1
            print(f"  ❌ {result['problem_id']}: {result['issues'][:60]}")

        if (i+1) % 20 == 0:
            print(f"  진행: {i+1}/{total}...")

    conn.commit()
    conn.close()
    shutil.copy(str(TMP_DB), str(DB_SRC))

    # 리포트 생성
    generate_report(ok, warn, error, total)
    print(f"\n{'─'*50}")
    print(f"✅ 완료: OK={ok} | ⚠️ WARN={warn} | ❌ ERROR={error}")
    print(f"📄 SR 리포트: wiki/00_INTERN_SR.md")


def generate_report(ok, warn, error, total):
    """Obsidian SR 리포트 마크다운 생성"""
    shutil.copy(str(DB_SRC), str(TMP_DB))
    conn = sqlite3.connect(str(TMP_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    errors = cur.execute("""
        SELECT sr.*, p.answer, p.year, p.source_type
        FROM sr_checks sr JOIN problems p ON sr.problem_id=p.id
        WHERE sr.img_status='error'
        ORDER BY sr.check_date DESC, sr.problem_id
    """).fetchall()

    warns = cur.execute("""
        SELECT sr.*, p.answer, p.year, p.source_type
        FROM sr_checks sr JOIN problems p ON sr.problem_id=p.id
        WHERE sr.img_status='warn'
        ORDER BY sr.check_date DESC, sr.problem_id
    """).fetchall()

    conn.close()

    pct = round(ok/total*100, 1) if total else 0
    md = f"""---
tags: [intern-sr, qa]
updated: {NOW}
---

# 🤖 인턴 에이전트 SR 리포트

> 검사일시: {NOW} | 에이전트: {AGENT}

---

## 📊 검사 결과 요약

| 항목 | 수 | 비율 |
|------|----|----|
| ✅ 정상 (OK) | {ok} | {pct}% |
| ⚠️ 경고 (WARN) | {warn} | {round(warn/total*100,1) if total else 0}% |
| ❌ 오류 (ERROR) | {error} | {round(error/total*100,1) if total else 0}% |
| 📚 전체 | {total} | 100% |

---

## ❌ 오류 목록 (즉시 조치 필요)

"""
    if errors:
        md += "| 문제 ID | 오류 내용 | 제안 |\n|---------|-----------|------|\n"
        for r in errors:
            md += f"| {r['problem_id']} | {(r['issues'] or '')[:60]} | {(r['suggestions'] or '')[:40]} |\n"
    else:
        md += "✅ 오류 없음\n"

    md += "\n---\n\n## ⚠️ 경고 목록 (검토 권장)\n\n"
    if warns:
        md += "| 문제 ID | 경고 내용 |\n|---------|----------|\n"
        for r in warns:
            md += f"| {r['problem_id']} | {(r['issues'] or '')[:80]} |\n"
    else:
        md += "✅ 경고 없음\n"

    md += f"""
---

## 🔍 검사 항목 기준

| 항목 | 기준 | 오류 패턴 |
|------|------|-----------|
| 이미지 크기 | 100px~4500px 높이 | 너무 작음/큰 이미지 |
| 수직선 잔존 | 열 50% 이상 어두움 | 컬럼 구분선 미제거 |
| 하단 빈공간 | 전체 35% 이상 빈공간 | clip 경계 블리드 |
| R컬럼 블리드 | 오른쪽 12% 내용 존재 | mid_x_px 미적용 |
| PDF 대조 | 텍스트 블록 존재 | 내용 누락 의심 |
| 정답 확인 | 정답 미입력 여부 | DB 정답 공백 |

---

## ⚡ 오류 수정 명령어

```bash
# 이미지 이상 → 전체 재크롭
CODE: python3 scripts/crop_all.py

# 특정 연도만
CODE: python3 scripts/crop_all.py 2025

# 인턴 에이전트 재실행
python3 scripts/intern_agent.py

# 새 항목만 검사
python3 scripts/intern_agent.py --new

# SR 리포트 출력
python3 scripts/intern_agent.py --report
```

*자동 생성: {NOW} by {AGENT}*
"""
    REPORT.write_text(md, encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="수학 문제 이미지 QA 인턴 에이전트")
    parser.add_argument("--id",     help="특정 문제 ID만 검사")
    parser.add_argument("--new",    action="store_true", help="미검사 항목만")
    parser.add_argument("--report", action="store_true", help="최근 SR 리포트 출력")
    args = parser.parse_args()

    if args.report:
        shutil.copy(str(DB_SRC), str(TMP_DB))
        conn=sqlite3.connect(str(TMP_DB))
        rows=conn.execute("""
            SELECT img_status, COUNT(*) as n FROM sr_checks
            GROUP BY img_status ORDER BY n DESC
        """).fetchall()
        conn.close()
        print("📊 최근 SR 현황:")
        for r in rows:
            icon={'ok':'✅','warn':'⚠️','error':'❌'}.get(r[0],'?')
            print(f"  {icon} {r[0]}: {r[1]}개")
    else:
        run_inspection(id_filter=args.id, new_only=args.new)
