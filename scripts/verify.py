#!/usr/bin/env python3
"""
verify.py — 수학 문제 DB 자동 검증 시스템
수학의 지름길 학원 | 신뢰도 100% 달성 도구

실행: python3 scripts/verify.py
결과: wiki/VERIFY_REPORT.md  (자동 수정 불가 항목 목록)
"""
import sqlite3, shutil, json, sys, re
from pathlib import Path
from datetime import datetime
from PIL import Image

BASE     = Path(__file__).parent.parent
DB_SRC   = BASE / "db" / "problems.db"
TMP_DB   = Path("/tmp/verify_main.db")
CROPS    = BASE / "sources" / "crops"
REPORT   = BASE / "wiki" / "VERIFY_REPORT.md"

# ── 자동 검사 항목 정의 ───────────────────────────────────────
CHECKS = {
    "IMG_MISSING":  "🔴 이미지 파일 없음",
    "IMG_TINY":     "🟠 이미지 너무 작음 (<120px)",
    "IMG_WIDE":     "🟠 이미지 전체너비(크롭 미적용)",
    "ANS_MISSING":  "🔴 정답 없음",
    "ANS_FORMAT":   "🟡 정답 형식 이상",
    "TEXT_MISSING": "🟡 문제 텍스트 없음",
    "TOPIC_MISSING":"🟡 단원/영역 없음",
    "DIFF_MISSING": "🟡 난이도 없음",
    "YEAR_MISSING": "🔴 연도 없음",
    "SIMILAR_ZERO": "⚪ 유사문제 없음",
}

SEVERITY = {
    "IMG_MISSING": 3, "ANS_MISSING": 3, "YEAR_MISSING": 3,
    "IMG_TINY": 2, "IMG_WIDE": 2, "ANS_FORMAT": 2,
    "TEXT_MISSING": 1, "TOPIC_MISSING": 1, "DIFF_MISSING": 1,
    "SIMILAR_ZERO": 0,
}

def auto_check(row: dict, similar_count: int) -> list:
    """한 문제에 대한 자동 검사 → 문제 코드 리스트 반환"""
    issues = []
    crop = row.get("crop_path", "") or ""
    
    # 이미지 검사
    if not crop:
        issues.append("IMG_MISSING")
    else:
        img_path = BASE / crop
        if not img_path.exists():
            issues.append("IMG_MISSING")
        else:
            try:
                img = Image.open(img_path)
                w, h = img.size
                if h < 120:
                    issues.append("IMG_TINY")
                if w > 2000:
                    issues.append("IMG_WIDE")
            except Exception:
                issues.append("IMG_MISSING")
    
    # 정답 검사
    ans = (row.get("answer") or "").strip()
    if not ans:
        issues.append("ANS_MISSING")
    elif not re.search(r'[①②③④⑤①-⑤\d]', ans):
        issues.append("ANS_FORMAT")
    
    # 텍스트 검사
    txt = (row.get("raw_text") or "").strip()
    if not txt or txt in ("None", "null", "없음"):
        issues.append("TEXT_MISSING")
    
    # 메타데이터 검사
    if not (row.get("topic") or "").strip():
        issues.append("TOPIC_MISSING")
    if not (row.get("difficulty") or "").strip():
        issues.append("DIFF_MISSING")
    if not row.get("year"):
        issues.append("YEAR_MISSING")
    if similar_count == 0:
        issues.append("SIMILAR_ZERO")
    
    return issues

def run_verification():
    shutil.copy(str(DB_SRC), str(TMP_DB))
    conn = sqlite3.connect(str(TMP_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM problems ORDER BY year, problem_number")
    all_rows = [dict(r) for r in cur.fetchall()]
    
    total = len(all_rows)
    results = []
    severity_counts = {0:0, 1:0, 2:0, 3:0}
    
    for row in all_rows:
        pid = row["id"]
        cur.execute(
            "SELECT COUNT(*) FROM similar_problems WHERE problem_id=? OR similar_id=?",
            (pid, pid)
        )
        sim_cnt = cur.fetchone()[0]
        
        issues = auto_check(row, sim_cnt)
        max_sev = max((SEVERITY[c] for c in issues), default=-1)
        
        # 상태 결정
        if not issues:
            status = "pass"
        elif max_sev >= 3:
            status = "critical"
        elif max_sev >= 2:
            status = "warning"
        else:
            status = "info"
        
        # DB 업데이트
        check_json = json.dumps(issues, ensure_ascii=False)
        verify_st = "pass" if not issues else "needs_review"
        cur.execute(
            "UPDATE problems SET auto_check_result=?, verify_status=? WHERE id=?",
            (check_json, verify_st, pid)
        )
        
        for c in issues:
            severity_counts[SEVERITY[c]] = severity_counts.get(SEVERITY[c], 0) + 1
        
        results.append({
            "id": pid,
            "num": row.get("problem_number", 0),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "source": row.get("source_type", ""),
            "issues": issues,
            "status": status,
            "sim_cnt": sim_cnt,
        })
    
    conn.commit()
    conn.close()
    shutil.copy(str(TMP_DB), str(DB_SRC))
    
    # ── 리포트 생성 ───────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pass_cnt = sum(1 for r in results if r["status"] == "pass")
    critical_cnt = sum(1 for r in results if r["status"] == "critical")
    warn_cnt = sum(1 for r in results if r["status"] == "warning")
    info_cnt = sum(1 for r in results if r["status"] == "info")
    
    pct = round(pass_cnt / total * 100, 1) if total else 0
    
    lines = [
        "---",
        "tags: [verify, quality-check]",
        f"updated: {now}",
        "---",
        "",
        "# 🔍 수학 문제 DB 검증 리포트",
        "",
        f"> **검증 시각**: {now}",
        f"> **총 문제**: {total}개",
        f"> **통과**: ✅ {pass_cnt}개 ({pct}%) | 🔴 Critical: {critical_cnt} | 🟠 Warning: {warn_cnt} | 🟡 Info: {info_cnt}",
        "",
        "---",
        "",
    ]
    
    # Critical 먼저
    for label, status_key, emoji in [
        ("🔴 즉시 수정 필요 (Critical)", "critical", "🔴"),
        ("🟠 검토 권장 (Warning)",       "warning",  "🟠"),
        ("🟡 참고 사항 (Info)",           "info",     "🟡"),
    ]:
        group = [r for r in results if r["status"] == status_key]
        if not group:
            continue
        lines += [f"## {label} — {len(group)}개", ""]
        lines += ["| 문제 ID | 번호 | 출처 | 문제점 |",
                  "|---------|------|------|--------|"]
        for r in group:
            issue_str = " / ".join(CHECKS[c] for c in r["issues"])
            lines.append(f"| {r['id']} | {r['num']}번 | {r['year']}{r['source']} | {issue_str} |")
        lines += [""]
    
    # 통과 목록
    lines += [
        "## ✅ 검증 통과 목록",
        "",
        "| 문제 ID | 유사문제 수 |",
        "|---------|------------|",
    ]
    for r in results:
        if r["status"] == "pass":
            lines.append(f"| {r['id']} | {r['sim_cnt']} |")
    
    lines += [
        "",
        "---",
        "",
        "## 📋 수동 검토 가이드",
        "",
        "1. `wiki/verify_dashboard.html` 열기 → 각 문제 이미지 직접 확인",
        "2. 문제 이상 발견 시 → **수정 필요** 버튼 클릭 → 메모 입력",
        "3. 검토 완료 시 → **확인 완료** 버튼 클릭",
        "4. `python3 scripts/verify.py` 재실행 → 리포트 업데이트",
        "",
        f"*자동 생성: {now}*",
        "",
    ]
    
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    
    print(f"\n{'='*50}")
    print(f"📊 검증 결과: {total}개 문제")
    print(f"  ✅ 통과:    {pass_cnt}개 ({pct}%)")
    print(f"  🔴 Critical: {critical_cnt}개")
    print(f"  🟠 Warning:  {warn_cnt}개")
    print(f"  🟡 Info:     {info_cnt}개")
    print(f"\n리포트: wiki/VERIFY_REPORT.md")
    print(f"대시보드: wiki/verify_dashboard.html")
    
    return results

if __name__ == "__main__":
    run_verification()
