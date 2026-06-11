#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Answer Solution Curator Agent
정답·해설을 찾아 넣기 위한 큐를 관리합니다.

절대 원칙:
  - 원본 해설은 수정하지 않는다.
  - 공식/원본 해설에서 파생한 내용은 source attribution을 남긴다.
  - 추가 해설은 stage3_solution 또는 별도 additional_solution 필드/노트에만 기록한다.
"""

import argparse, json, re, sys
from datetime import datetime
from pathlib import Path
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def file_id_from_new_id(new_id: str) -> str:
    if not new_id:
        return ""
    base = re.sub(r"-(?:Q|S)\d+$", "", new_id)
    return base.split("_")[0]


class AnswerSolutionCuratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("answer_solution_curator", "Answer Solution Curator Agent", tier=3)

    def queue(self, limit: int = 50) -> dict:
        conn, _ = self.get_db()
        missing_solution = [dict(r) for r in conn.execute("""
            SELECT id, new_id, title, year, source_type, topic, difficulty, answer, crop_path
            FROM problems
            WHERE stage3_sol IS NULL OR stage3_sol!='pass'
            ORDER BY year, source_type, problem_number
            LIMIT ?
        """, (limit,)).fetchall()]
        missing_answer = [dict(r) for r in conn.execute("""
            SELECT id, title, year, source_type, problem_number
            FROM problems
            WHERE answer IS NULL OR answer=''
            ORDER BY year, source_type, problem_number
        """).fetchall()]
        source_refs = {
            r["file_id"]: dict(r) for r in conn.execute("""
                SELECT file_id, file_path_q, file_path_a, file_path_s
                FROM file_registry
                WHERE file_type='exam'
            """).fetchall()
        }
        conn.close()
        for item in missing_solution:
            file_id = file_id_from_new_id(item.get("new_id") or "")
            item["source_files"] = source_refs.get(file_id, {})
        result = {
            "generated_at": datetime.now().isoformat(),
            "missing_answer_count": len(missing_answer),
            "solution_queue_count": len(missing_solution),
            "missing_answer": missing_answer,
            "solution_queue": missing_solution,
            "policy": "원본 해설은 보존한다. 추가 해설만 별도 입력한다.",
        }
        out = BASE_DIR / "logs" / "agents" / "answer_solution_queue.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_obsidian_queue(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def write_obsidian_queue(self, result: dict) -> Path:
        path = BASE_DIR / "wiki" / "00_SOLUTION_QUEUE.md"
        lines = [
            "---",
            "tags: [solution, queue, agents]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# 해설 입력 큐",
            "",
            "> 원본 해설은 보존합니다. 이 큐는 추가 해설 작성 대상만 나열합니다.",
            "",
            f"- 정답 누락: {result['missing_answer_count']}개",
            f"- 해설 큐 표시: {result['solution_queue_count']}개",
            "",
            "| 문제 | 난이도 | 정답 | 원본/해설 파일 | 추가 해설 상태 |",
            "|---|---|---|---|---|",
        ]
        for item in result["solution_queue"]:
            refs = item.get("source_files") or {}
            src = refs.get("file_path_s") or refs.get("file_path_a") or ""
            lines.append(
                f"| [[{item['id']}]] | {item['difficulty']} | {item['answer']} | `{src}` | stage3 pending |"
            )
        lines += [
            "",
            "## 작업 원칙",
            "",
            "- 원본 해설 PDF는 수정하지 않는다.",
            "- 추가 해설은 문제 노트의 `stage3_solution` 또는 별도 추가 해설 노트에만 적는다.",
            "- 원본 해설과 추가 해설을 한 필드에 섞지 않는다.",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def draft_notes(self, limit: int = 20, skip_existing: bool = False) -> dict:
        """추가 해설 입력용 안전 초안 노트를 생성합니다. 원본/DB는 수정하지 않습니다."""
        fetch_limit = 1000 if skip_existing else limit
        result = self.queue(fetch_limit)
        out_dir = BASE_DIR / "wiki" / "solutions" / "additional_drafts"
        out_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for item in result["solution_queue"]:
            path = out_dir / f"{item['id']}.md"
            if skip_existing and path.exists():
                continue
            if len(created) >= limit:
                break
            refs = item.get("source_files") or {}
            source_solution = refs.get("file_path_s") or refs.get("file_path_a") or ""
            lines = [
                "---",
                "tags: [solution-draft, additional-solution, needs-review]",
                f"problem_id: {item['id']}",
                f"new_id: {item.get('new_id','')}",
                "solution_type: additional_draft",
                "status: needs_official_solution_access",
                f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "---",
                "",
                f"# 추가 해설 초안: {item['id']}",
                "",
                "## 원본 보존",
                "",
                f"- 원본/공식 해설 파일: `{source_solution}`",
                "- 이 노트는 추가 해설 초안이며 원본 해설을 대체하지 않습니다.",
                "- 공식 해설 접근 또는 교사 검수 전에는 `stage3_sol: pass`로 올리지 않습니다.",
                "",
                "## 문제 정보",
                "",
                f"- 제목: {item['title']}",
                f"- 단원: {item['topic']}",
                f"- 난이도: {item['difficulty']}",
                f"- 정답: {item['answer']}",
                f"- 문제 이미지: ![]({item['crop_path']})",
                "",
                "## 추가 해설 작성란",
                "",
                "> 공식 해설 확인 후, 원본 표현을 보존하면서 수업용 추가 해설만 작성합니다.",
                "",
                "1. 접근 전략:",
                "2. 핵심 계산:",
                "3. 정답 확인:",
                "4. 학생 주의점:",
                "",
                "## 검수",
                "",
                "- [ ] 공식/원본 해설 대조",
                "- [ ] Math Expert 검토",
                "- [ ] Teacher 수업 표현 검토",
                "- [ ] Verification stage3 반영",
            ]
            path.write_text("\n".join(lines), encoding="utf-8")
            created.append(str(path.relative_to(BASE_DIR)))
        summary = {"created": created, "count": len(created), "skip_existing": skip_existing}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        self.save_result(summary, "answer_solution_draft_notes.json")
        return summary

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "draft_notes":
            return self.draft_notes(task.get("limit", 20), task.get("skip_existing", False))
        return self.queue(task.get("limit", 50))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Answer Solution Curator Agent")
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--draft-notes", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    agent = AnswerSolutionCuratorAgent()
    if args.draft_notes:
        agent.draft_notes(args.limit, args.skip_existing)
    else:
        agent.queue(args.limit)
