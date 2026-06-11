#!/usr/bin/env python3
"""
obsidian_sync.py — DB → Obsidian 마크다운 동기화 스크립트
수학의 지름길 학원 LLM-Wiki v3.1
"""
import sqlite3
import json
import shutil
import sys
import tempfile
import re
from pathlib import Path
from datetime import datetime

# ─── 경로 설정 ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "db" / "problems.db"
WIKI_DIR = BASE_DIR / "wiki"
PROB_DIR = WIKI_DIR / "problems"
INTEGRITY_AUDIT_PATH = BASE_DIR / "logs" / "agents" / "integrity_guard_audit.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── DB 안전 읽기 (VirtioFS 대응: tmp 복사) ─────────────────
def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists() or DB_PATH.stat().st_size < 10_000:
        raise RuntimeError(f"유효하지 않은 DB 파일: {DB_PATH}")
    tmp = Path(tempfile.gettempdir()) / "mathwiki_obs_read.db"
    shutil.copy(str(DB_PATH), str(tmp))
    conn = sqlite3.connect(str(tmp))
    conn.row_factory = sqlite3.Row
    return conn

# ─── 난이도 이모지 ────────────────────────────────────────────
DIFF_EMOJI = {"최하": "⚪", "하": "🟢", "중하": "🔵", "중": "🟡", "중상": "🟠", "상": "🔴", "최상": "⭐"}

def diff_emoji(d: str) -> str:
    return DIFF_EMOJI.get(d, "❓")

# ─── 유사문제 목록 조회 ────────────────────────────────────────
def get_similar_ids(cur, prob_id: str) -> list:
    cur.execute("""
        SELECT similar_id FROM similar_problems WHERE problem_id = ?
        UNION
        SELECT problem_id FROM similar_problems WHERE similar_id = ?
        ORDER BY 1
    """, (prob_id, prob_id))
    return [r[0] for r in cur.fetchall()]

def file_id_from_new_id(new_id: str) -> str:
    if not new_id:
        return ""
    base = re.sub(r"-(?:Q|S)\d+$", "", new_id)
    return base.split("_")[0]

def get_source_refs(cur) -> dict:
    try:
        cur.execute("""
            SELECT file_id, file_path_q, file_path_a, file_path_s
            FROM file_registry
            WHERE file_type = 'exam'
        """)
    except sqlite3.OperationalError:
        return {}
    return {r["file_id"]: dict(r) for r in cur.fetchall()}

def source_integrity_status() -> str:
    if not INTEGRITY_AUDIT_PATH.exists():
        return "pending"
    try:
        data = json.loads(INTEGRITY_AUDIT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return "pending"
    return "pass" if data.get("status") == "PASS" else "blocked"

# ─── 문제 한 페이지 생성 ──────────────────────────────────────
def render_problem_page(row: dict, similar_ids: list, source_refs: dict = None) -> str:
    prob_id   = row["id"]
    title     = row["title"] or "제목없음"
    grade     = row["grade"] or ""
    domain    = row["domain"] or ""
    topic     = row["topic"] or ""
    difficulty= row["difficulty"] or "중"
    source    = row["source_type"] or ""
    year      = row["year"] or ""
    school    = row["school"] or ""
    answer    = row["answer"] or ""
    num       = row["problem_number"] or 0
    raw_text  = row["raw_text"] or ""
    if raw_text in ("None", "null", "없음", "문제 텍스트 없음"):
        raw_text = ""
    crop_path = row["crop_path"] or ""
    created   = row["created_at"] or datetime.now().strftime("%Y-%m-%d %H:%M")
    new_id    = row["new_id"] or ""
    month     = row["month"] or ""
    source_code = row["source_code"] or ""
    verify_status = row["verify_status"] or "pending"
    stage1_img = row["stage1_img"] or "pending"
    stage1_note = row["stage1_note"] or ""
    stage2_ans = row["stage2_ans"] or "pending"
    stage2_note = row["stage2_note"] or ""
    answer_fixed = row["stage2_answer_fixed"] or ""
    stage3_sol = row["stage3_sol"] or "pending"
    stage3_note = row["stage3_note"] or ""
    stage3_solution = row["stage3_solution"] or ""
    final_grade = row["final_grade"] or "pending"
    sign_tr = row["sign_tr_final"] or ""
    sign_cp = row["sign_cp_final"] or ""
    concept_tags = row["concept_tags"] or ""
    source_refs = source_refs or {}
    file_id = file_id_from_new_id(new_id)
    source_ref = source_refs.get(file_id, {})
    original_problem_ref = source_ref.get("file_path_q", "")
    original_answer_ref = source_ref.get("file_path_a", "")
    original_solution_ref = source_ref.get("file_path_s", "") or original_answer_ref
    additional_solution_path = WIKI_DIR / "solutions" / "additional_drafts" / f"{prob_id}.md"
    additional_solution_ref = ""
    if additional_solution_path.exists():
        additional_solution_ref = f"wiki/solutions/additional_drafts/{prob_id}.md"
    integrity_status = source_integrity_status()

    # concept/tags JSON 파싱
    try:
        concepts = json.loads(row["concept"] or "[]")
    except Exception:
        concepts = [row["concept"]] if row["concept"] else []

    try:
        tags = json.loads(row["tags"] or "[]")
    except Exception:
        tags = []

    # YAML frontmatter
    similar_yaml = json.dumps(similar_ids, ensure_ascii=False)
    concept_yaml = json.dumps(concepts, ensure_ascii=False)
    tags_yaml    = json.dumps(tags, ensure_ascii=False)

    # 이미지 경로: Obsidian 첨부 폴더(sources/crops) 기준 wikilink가 가장 안정적이다.
    img_rel = crop_path if crop_path else ""
    img_embed = f"![[{Path(crop_path).name}|700]]" if crop_path else ""

    lines = [
        "---",
        f"id: {prob_id}",
        f"new_id: {new_id}",
        f'title: "{title}"',
        f"grade: {grade}",
        f"domain: {domain}",
        f"topic: {topic}",
        f"concept: {concept_yaml}",
        f"concept_tags: {concept_tags}",
        f"difficulty: {difficulty}",
        f"source_type: {source}",
        f"source_code: {source_code}",
        f"year: {year}",
        f"month: {month}",
        f"school: {school}",
        f'answer: "{answer}"',
        f'answer_fixed: "{answer_fixed}"',
        f"problem_number: {num}",
        f"tags: {tags_yaml}",
        f"similar_ids: {similar_yaml}",
        f"crop_path: {crop_path}",
        f"verify_status: {verify_status}",
        f"stage1_img: {stage1_img}",
        f'stage1_note: "{stage1_note}"',
        f"stage2_ans: {stage2_ans}",
        f'stage2_note: "{stage2_note}"',
        f"stage3_sol: {stage3_sol}",
        f'stage3_note: "{stage3_note}"',
        f'stage3_solution: "{stage3_solution}"',
        f'original_problem_ref: "{original_problem_ref}"',
        f'original_answer_ref: "{original_answer_ref}"',
        f'original_solution_ref: "{original_solution_ref}"',
        f'additional_solution_ref: "{additional_solution_ref}"',
        'solution_index_status: "indexed"',
        'math_expert_review: "pending"',
        'teacher_review: "pending"',
        f'source_integrity: "{integrity_status}"',
        f"final_grade: {final_grade}",
        f'sign_tr: "{sign_tr}"',
        f'sign_cp: "{sign_cp}"',
        f"created_at: {created}",
        "---",
        "",
        f"# {num}번. {title}",
        "",
        f"{diff_emoji(difficulty)} **난이도**: {difficulty} | 📚 **단원**: {topic} | 🏫 **출처**: {year}{source} | 🎓 **학년**: {grade}",
        "",
        "---",
        "",
        "## 📝 문제",
        "",
        raw_text,
        "",
    ]

    if img_rel:
        lines += [
            "## 🖼️ 문제 이미지",
            "",
            img_embed,
            "",
        ]

    lines += [
        "## ✅ 정답",
        "",
        f"> **{answer}**",
        "",
        "---",
        "",
        "## 🔗 유사문제",
        "",
    ]

    if similar_ids:
        for sid in similar_ids:
            lines.append(f"- [[{sid}]]")
    else:
        lines.append("- 유사문제 없음")

    lines += [
        "",
        "---",
        "",
        f"*📁 영역: [[{domain}]] | 단원: [[{topic}]] | 🗓️ {year}년 {source}*",
        "",
    ]

    return "\n".join(lines)

# ─── DB 상태 요약 (00_DB_STATUS.md용) ────────────────────────
def get_db_stats(conn) -> dict:
    cur = conn.cursor()
    stats = {}

    cur.execute("SELECT COUNT(*) FROM problems")
    stats["total"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM similar_problems")
    stats["similar_pairs"] = cur.fetchone()[0]

    cur.execute("SELECT year, COUNT(*) as cnt FROM problems GROUP BY year ORDER BY year")
    stats["by_year"] = [(r["year"], r["cnt"]) for r in cur.fetchall()]

    cur.execute("SELECT domain, COUNT(*) as cnt FROM problems GROUP BY domain ORDER BY cnt DESC")
    stats["by_domain"] = [(r["domain"], r["cnt"]) for r in cur.fetchall()]

    cur.execute("SELECT difficulty, COUNT(*) as cnt FROM problems GROUP BY difficulty ORDER BY cnt DESC")
    stats["by_difficulty"] = [(r["difficulty"], r["cnt"]) for r in cur.fetchall()]

    cur.execute("SELECT source_type, COUNT(*) as cnt FROM problems GROUP BY source_type ORDER BY cnt DESC")
    stats["by_source"] = [(r["source_type"], r["cnt"]) for r in cur.fetchall()]

    cur.execute("SELECT grade, COUNT(*) as cnt FROM problems GROUP BY grade ORDER BY cnt DESC")
    stats["by_grade"] = [(r["grade"], r["cnt"]) for r in cur.fetchall()]

    # 이미지 존재 여부
    cur.execute("SELECT crop_path FROM problems WHERE crop_path IS NOT NULL AND crop_path != ''")
    crop_rows = [r["crop_path"] for r in cur.fetchall()]
    base = Path(__file__).parent.parent
    existing = sum(1 for p in crop_rows if (base / p).exists())
    stats["image_total"]    = len(crop_rows)
    stats["image_existing"] = existing

    return stats

# ─── 00_DB_STATUS.md 생성 ─────────────────────────────────────
def render_db_status(stats: dict, sync_time: str) -> str:
    db_size_kb = DB_PATH.stat().st_size // 1024 if DB_PATH.exists() else 0

    lines = [
        "---",
        "tags: [dashboard, db-status]",
        f"updated: {sync_time}",
        "---",
        "",
        "# 📊 수학 위키 DB 현황 대시보드",
        "",
        f"> **마지막 동기화**: {sync_time}",
        f"> **DB 파일**: `db/problems.db` ({db_size_kb} KB)",
        f"> **총 문제 수**: {stats['total']}문제 | **유사문제 쌍**: {stats['similar_pairs']}쌍",
        f"> **이미지**: {stats['image_existing']}/{stats['image_total']} 연결됨",
        "",
        "---",
        "",
        "## 📅 연도별 현황",
        "",
        "| 연도 | 문제 수 |",
        "|------|---------|",
    ]
    for year, cnt in stats["by_year"]:
        lines.append(f"| {year} | {cnt} |")

    lines += [
        "",
        "## 📐 영역별 현황",
        "",
        "| 영역 | 문제 수 |",
        "|------|---------|",
    ]
    for domain, cnt in stats["by_domain"]:
        lines.append(f"| {domain} | {cnt} |")

    lines += [
        "",
        "## 🎯 난이도별 현황",
        "",
        "| 난이도 | 문제 수 |",
        "|--------|---------|",
    ]
    for diff, cnt in stats["by_difficulty"]:
        emoji = DIFF_EMOJI.get(diff, "❓")
        lines.append(f"| {emoji} {diff} | {cnt} |")

    lines += [
        "",
        "## 📚 출처별 현황",
        "",
        "| 출처 | 문제 수 |",
        "|------|---------|",
    ]
    for src, cnt in stats["by_source"]:
        lines.append(f"| {src} | {cnt} |")

    lines += [
        "",
        "## 🎓 학년별 현황",
        "",
        "| 학년 | 문제 수 |",
        "|------|---------|",
    ]
    for grade, cnt in stats["by_grade"]:
        lines.append(f"| {grade} | {cnt} |")

    lines += [
        "",
        "---",
        "",
        "## 🔍 Dataview 쿼리 (Obsidian Dataview 플러그인 필요)",
        "",
        "### 최근 추가된 문제 10개",
        "",
        "```dataview",
        "TABLE title, difficulty, domain, topic, year",
        "FROM \"wiki/problems\"",
        "SORT created_at DESC",
        "LIMIT 10",
        "```",
        "",
        "### 난이도 상 문제 목록",
        "",
        "```dataview",
        "TABLE title, topic, year, answer",
        "FROM \"wiki/problems\"",
        "WHERE difficulty = \"상\"",
        "SORT year DESC",
        "```",
        "",
        "### 영역별 그룹",
        "",
        "```dataview",
        "TABLE rows.file.link, rows.difficulty, rows.year",
        "FROM \"wiki/problems\"",
        "GROUP BY domain",
        "```",
        "",
        "### 유사문제 있는 문제",
        "",
        "```dataview",
        "TABLE title, length(similar_ids) as \"유사문제 수\", topic",
        "FROM \"wiki/problems\"",
        "WHERE similar_ids",
        "SORT length(similar_ids) DESC",
        "LIMIT 20",
        "```",
        "",
        "---",
        "",
        f"*🤖 `scripts/obsidian_sync.py`로 자동 생성됨 — {sync_time}*",
        "",
    ]

    return "\n".join(lines)

# ─── 메인 동기화 ──────────────────────────────────────────────
def sync():
    if not DB_PATH.exists():
        print(f"❌ DB 파일 없음: {DB_PATH}")
        sys.exit(1)

    print(f"📂 DB 연결: {DB_PATH}")
    conn = get_connection()
    cur  = conn.cursor()

    # 문제 디렉토리 생성
    PROB_DIR.mkdir(parents=True, exist_ok=True)

    cur.execute("SELECT * FROM problems ORDER BY year, problem_number")
    rows = [dict(r) for r in cur.fetchall()]
    source_refs = get_source_refs(cur)
    print(f"📚 총 {len(rows)}개 문제 동기화 시작...")

    synced = 0
    skipped = 0
    for row in rows:
        prob_id   = row["id"]
        similar   = get_similar_ids(cur, prob_id)
        content   = render_problem_page(row, similar, source_refs)
        out_path  = PROB_DIR / f"{prob_id}.md"

        # 기존 파일과 내용이 같으면 스킵
        if out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            if existing == content:
                skipped += 1
                continue

        out_path.write_text(content, encoding="utf-8")
        synced += 1

    print(f"  ✅ 신규/갱신: {synced}개, 스킵: {skipped}개")

    # DB 상태 대시보드 생성
    stats     = get_db_stats(conn)
    now_str   = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_md = render_db_status(stats, now_str)
    status_path = WIKI_DIR / "00_DB_STATUS.md"
    status_path.write_text(status_md, encoding="utf-8")
    print(f"  📊 DB 상태 대시보드 → {status_path}")

    conn.close()
    print(f"\n🎉 동기화 완료! ({now_str})")
    t = stats["total"]; sp = stats["similar_pairs"]; ie = stats["image_existing"]; it = stats["image_total"]
    print(f"   총 문제: {t} | 유사쌍: {sp} | 이미지: {ie}/{it}")

if __name__ == "__main__":
    sync()
