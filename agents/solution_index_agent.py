#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Solution Index Agent

원본 문제지/정답/해설 PDF에 대한 접근 색인을 생성합니다.

절대 원칙:
  - 원본 PDF를 읽거나 수정하지 않는다.
  - 문제 본문과 기존 해설 본문을 변형하지 않는다.
  - 문제 노트에는 참조 경로와 추가 해설 노트 링크만 기록한다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
PROB_DIR = BASE_DIR / "wiki" / "problems"
INDEX_PATH = BASE_DIR / "wiki" / "00_ORIGINAL_SOLUTION_INDEX.md"
INTEGRITY_AUDIT_PATH = BASE_DIR / "logs" / "agents" / "integrity_guard_audit.json"


class SolutionIndexAgent(BaseAgent):
    def __init__(self):
        super().__init__("solution_index", "Solution Index Agent", tier=2)

    @staticmethod
    def file_id_from_new_id(new_id: str) -> str:
        if not new_id:
            return ""
        base = re.sub(r"-(?:Q|S)\d+$", "", new_id)
        return base.split("_")[0]

    @staticmethod
    def parse_frontmatter(text: str) -> tuple[dict, str, str]:
        match = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
        if not match:
            return {}, "", text
        fm_text = match.group(1)
        body = text[match.end():]
        data = {}
        for line in fm_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip().strip('"')
        return data, fm_text, body

    @staticmethod
    def upsert_frontmatter(fm_text: str, updates: dict) -> str:
        lines = fm_text.splitlines()
        seen = set()
        output = []
        for line in lines:
            if ":" not in line:
                output.append(line)
                continue
            key, _ = line.split(":", 1)
            key = key.strip()
            if key in updates:
                output.append(f'{key}: "{updates[key]}"')
                seen.add(key)
            else:
                output.append(line)
        for key, value in updates.items():
            if key not in seen:
                output.append(f'{key}: "{value}"')
        return "\n".join(output)

    def source_refs(self) -> dict:
        conn, _ = self.get_db()
        rows = [dict(r) for r in conn.execute("""
            SELECT file_id, file_path_q, file_path_a, file_path_s
            FROM file_registry
            WHERE file_type = 'exam'
            ORDER BY file_id
        """)]
        conn.close()
        return {r["file_id"]: r for r in rows}

    def problem_rows(self) -> list[dict]:
        conn, _ = self.get_db()
        rows = [dict(r) for r in conn.execute("""
            SELECT id, new_id, title, year, month, grade, source_type,
                   source_code, problem_number, topic, difficulty, answer
            FROM problems
            ORDER BY year, month, source_code, problem_number, id
        """)]
        conn.close()
        return rows

    def apply_to_problem_notes(self, refs: dict) -> dict:
        updated = 0
        missing_ref = []
        source_integrity = self.source_integrity_status()
        for md in sorted(PROB_DIR.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            fm, fm_text, body = self.parse_frontmatter(text)
            if not fm_text:
                missing_ref.append(md.name)
                continue
            file_id = self.file_id_from_new_id(fm.get("new_id", ""))
            ref = refs.get(file_id)
            if not ref:
                missing_ref.append(md.name)
                continue
            problem_id = fm.get("id", md.stem)
            draft = f"wiki/solutions/additional_drafts/{problem_id}.md"
            if not (BASE_DIR / draft).exists():
                draft = ""
            updates = {
                "original_problem_ref": ref.get("file_path_q") or "",
                "original_answer_ref": ref.get("file_path_a") or "",
                "original_solution_ref": ref.get("file_path_s") or ref.get("file_path_a") or "",
                "additional_solution_ref": draft,
                "solution_index_status": "indexed",
                "math_expert_review": fm.get("math_expert_review") or "pending",
                "teacher_review": fm.get("teacher_review") or "pending",
                "source_integrity": source_integrity,
            }
            new_fm = self.upsert_frontmatter(fm_text, updates)
            new_text = f"---\n{new_fm}\n---\n\n{body.lstrip()}"
            if new_text != text:
                md.write_text(new_text, encoding="utf-8")
                updated += 1
        return {"updated_problem_notes": updated, "missing_ref_count": len(missing_ref), "sample_missing_ref": missing_ref[:20]}

    @staticmethod
    def source_integrity_status() -> str:
        if not INTEGRITY_AUDIT_PATH.exists():
            return "pending"
        try:
            audit = json.loads(INTEGRITY_AUDIT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return "pending"
        return "pass" if audit.get("status") == "PASS" else "blocked"

    def write_index(self, refs: dict, rows: list[dict]) -> Path:
        grouped = {}
        for row in rows:
            file_id = self.file_id_from_new_id(row.get("new_id") or "")
            grouped.setdefault(file_id, []).append(row)

        lines = [
            "---",
            "tags: [solution-index, original-preservation, agents]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# 원본 해설 접근 색인",
            "",
            "> 이 문서는 원본 문제지·정답·해설 PDF의 접근 색인입니다. 원본 파일과 원본 해설 내용은 수정하지 않습니다.",
            "",
            "## 색인 원칙",
            "",
            "- 원본 문제, 원본 정답, 원본 해설은 변형하지 않는다.",
            "- 문제 노트에는 원본 PDF 경로와 추가 해설 초안 링크만 기록한다.",
            "- 추가 해설은 `wiki/solutions/additional_drafts/` 또는 별도 추가 해설 필드에만 작성한다.",
            "- 공식 해설 접근/교사 검수 전에는 `stage3_sol: pass`로 승격하지 않는다.",
            "",
            "## 시험지별 원본 해설 색인",
            "",
            "| file_id | 문제 수 | 원본 문제지 | 원본 정답 | 원본 해설 | 추가 초안 |",
            "|---|---:|---|---|---|---:|",
        ]
        for file_id in sorted(grouped):
            ref = refs.get(file_id, {})
            problems = grouped[file_id]
            draft_count = sum(1 for row in problems if (BASE_DIR / "wiki" / "solutions" / "additional_drafts" / f"{row['id']}.md").exists())
            lines.append(
                f"| {file_id or '미지정'} | {len(problems)} | "
                f"`{ref.get('file_path_q', '')}` | "
                f"`{ref.get('file_path_a', '')}` | "
                f"`{ref.get('file_path_s', '') or ref.get('file_path_a', '')}` | "
                f"{draft_count} |"
            )

        lines += [
            "",
            "## 문제별 접근 색인",
            "",
            "| 문제 | new_id | 정답 | 원본 해설 | 추가 해설 초안 |",
            "|---|---|---|---|---|",
        ]
        for row in rows:
            file_id = self.file_id_from_new_id(row.get("new_id") or "")
            ref = refs.get(file_id, {})
            solution_ref = ref.get("file_path_s") or ref.get("file_path_a") or ""
            draft_path = BASE_DIR / "wiki" / "solutions" / "additional_drafts" / f"{row['id']}.md"
            draft_link = f"[[solutions/additional_drafts/{row['id']}|추가 초안]]" if draft_path.exists() else ""
            lines.append(
                f"| [[{row['id']}]] | {row.get('new_id','')} | {row.get('answer','')} | "
                f"`{solution_ref}` | {draft_link} |"
            )

        INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return INDEX_PATH

    def build(self) -> dict:
        refs = self.source_refs()
        rows = self.problem_rows()
        note_result = self.apply_to_problem_notes(refs)
        index_path = self.write_index(refs, rows)
        result = {
            "timestamp": datetime.now().isoformat(),
            "exam_file_refs": len(refs),
            "problem_rows": len(rows),
            "index_path": str(index_path.relative_to(BASE_DIR)),
            **note_result,
            "policy": "원본 문제/정답/해설은 변형하지 않고 접근 색인만 추가한다.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "solution_index.json")
        return result

    def audit(self) -> dict:
        files = sorted(PROB_DIR.glob("*.md"))
        missing = []
        for md in files:
            fm, _, _ = self.parse_frontmatter(md.read_text(encoding="utf-8"))
            required = [
                "original_problem_ref", "original_answer_ref", "original_solution_ref",
                "solution_index_status", "math_expert_review", "teacher_review", "source_integrity",
            ]
            absent = [key for key in required if key not in fm]
            if absent:
                missing.append({"file": md.name, "missing": absent})
        result = {
            "timestamp": datetime.now().isoformat(),
            "problem_notes": len(files),
            "missing_index_fields": len(missing),
            "sample_missing": missing[:20],
            "index_exists": INDEX_PATH.exists(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "solution_index_audit.json")
        return result

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "audit":
            return self.audit()
        return self.build()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Solution Index Agent")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    agent = SolutionIndexAgent()
    if args.audit:
        agent.audit()
    else:
        agent.build()
