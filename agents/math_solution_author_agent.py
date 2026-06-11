#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Math Solution Author Agent

추가 해설과 유사문제 작성 업무를 관리하는 수학전문가 에이전트입니다.

절대 원칙:
  - 원본문제, 원본정답, 원본해설은 수정하지 않는다.
  - 공식/원본 해설을 확인하지 못한 상태에서는 완성 해설을 작성하지 않는다.
  - 추가 해설과 유사문제는 별도 초안/큐에만 작성한다.
  - 유사문제에는 영역, 단원, 개념, 난이도, 원문제 id를 반드시 기록한다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
AUTHOR_BOARD = BASE_DIR / "wiki" / "00_MATH_SOLUTION_AUTHOR_BOARD.md"
SIMILAR_DRAFT_DIR = BASE_DIR / "wiki" / "similar_drafts"
SOLUTION_DRAFT_DIR = BASE_DIR / "wiki" / "solutions" / "additional_drafts"


def safe_name(text: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", text)


def file_id_from_new_id(new_id: str) -> str:
    if not new_id:
        return ""
    base = re.sub(r"-(?:Q|S)\d+$", "", new_id)
    return base.split("_")[0]


class MathSolutionAuthorAgent(BaseAgent):
    def __init__(self):
        super().__init__("math_solution_author", "Math Solution Author Agent", tier=3)

    def mission(self) -> dict:
        result = {
            "agent": self.agent_id,
            "role": "추가 해설 및 유사문제 작성 수학전문가",
            "must_preserve": ["원본문제", "원본정답", "원본해설"],
            "writes_only_to": [
                "wiki/solutions/additional_drafts/",
                "wiki/similar_drafts/",
                "logs/agents/",
            ],
            "required_metadata_for_similar_problem": [
                "source_problem_id",
                "domain",
                "topic",
                "concept_tags",
                "difficulty",
                "variation_type",
                "answer_status",
                "review_status",
            ],
            "workflow": [
                "원본 해설 색인 확인",
                "추가 해설 초안 작성",
                "유사문제 초안 작성",
                "Math Expert 자체 검산",
                "Teacher 검수 요청",
                "Stage3 Promotion Manager 감사 요청",
            ],
        }
        self.write_board(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "math_solution_author_mission.json")
        return result

    def _problem_rows(self, limit: int) -> list[dict]:
        conn, _ = self.get_db()
        rows = [dict(r) for r in conn.execute("""
            SELECT id, new_id, title, domain, topic, concept_tags, difficulty,
                   answer, stage3_sol
            FROM problems
            ORDER BY year, month, source_code, problem_number, id
            LIMIT ?
        """, (limit,)).fetchall()]
        refs = self._source_refs(conn)
        conn.close()
        for row in rows:
            row["original_solution_ref"] = self._solution_ref_for(row, refs)
            draft = SOLUTION_DRAFT_DIR / f"{row['id']}.md"
            row["additional_solution_ref"] = str(draft.relative_to(BASE_DIR)) if draft.exists() else ""
        return rows

    @staticmethod
    def _source_refs(conn) -> dict:
        return {
            r["file_id"]: dict(r) for r in conn.execute("""
                SELECT file_id, file_path_q, file_path_a, file_path_s
                FROM file_registry
                WHERE file_type='exam'
            """).fetchall()
        }

    @staticmethod
    def _solution_ref_for(row: dict, refs: dict) -> str:
        ref = refs.get(file_id_from_new_id(row.get("new_id", "")), {})
        return ref.get("file_path_s") or ref.get("file_path_a") or ""

    def similar_queue(self, limit: int = 30) -> dict:
        conn, _ = self.get_db()
        rows = [dict(r) for r in conn.execute("""
            SELECT p.id, p.new_id, p.title, p.domain, p.topic, p.concept_tags,
                   p.difficulty, p.answer,
                   COUNT(sp.similar_id) AS similar_count
            FROM problems p
            LEFT JOIN similar_problems sp ON p.id = sp.problem_id
            GROUP BY p.id
            HAVING similar_count = 0
            ORDER BY p.domain, p.topic, p.difficulty, p.id
            LIMIT ?
        """, (limit,)).fetchall()]
        refs = self._source_refs(conn)
        conn.close()
        for row in rows:
            row["original_solution_ref"] = self._solution_ref_for(row, refs)
        result = {
            "timestamp": datetime.now().isoformat(),
            "count": len(rows),
            "items": rows,
            "policy": "유사문제는 원본문제 변형이 아니라 별도 초안으로만 작성한다.",
        }
        self.write_similar_queue(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "math_solution_author_similar_queue.json")
        return result

    def draft_similar_templates(self, limit: int = 20) -> dict:
        queue = self.similar_queue(limit)
        SIMILAR_DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        created = []
        for item in queue["items"]:
            path = SIMILAR_DRAFT_DIR / f"{safe_name(item['id'])}_similar_draft.md"
            lines = [
                "---",
                "tags: [similar-draft, math-expert, needs-review]",
                f"source_problem_id: {item['id']}",
                f"new_id: {item.get('new_id','')}",
                f"domain: {item.get('domain','')}",
                f"topic: {item.get('topic','')}",
                f"concept_tags: {item.get('concept_tags','')}",
                f"difficulty: {item.get('difficulty','')}",
                "variation_type: same-concept-new-numbers",
                "answer_status: pending",
                "review_status: needs_math_expert",
                "stage3_linked: false",
                "---",
                "",
                f"# 유사문제 초안: {item['id']}",
                "",
                "## 원본 보존",
                "",
                f"- 원본문제: [[{item['id']}]]",
                f"- 원본 해설 색인: `{item.get('original_solution_ref','')}`",
                "- 이 노트는 별도 유사문제 초안입니다. 원본문제와 원본해설을 대체하지 않습니다.",
                "",
                "## 메타데이터",
                "",
                f"- 영역: {item.get('domain','')}",
                f"- 단원: {item.get('topic','')}",
                f"- 개념: {item.get('concept_tags','')}",
                f"- 난이도: {item.get('difficulty','')}",
                "",
                "## 작성란",
                "",
                "### 유사문제",
                "",
                "> 새 문제를 작성하되 원본문제 문장을 복사하지 않습니다.",
                "",
                "### 정답",
                "",
                "### 추가 해설",
                "",
                "### 검수 체크",
                "",
                "- [ ] 원본문제 문장 복사 없음",
                "- [ ] 원본 해설 표현 복사 없음",
                "- [ ] 영역/단원/개념/난이도 일치",
                "- [ ] 정답 검산 완료",
                "- [ ] Teacher 검수 완료",
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            created.append(str(path.relative_to(BASE_DIR)))
        result = {"timestamp": datetime.now().isoformat(), "created": created, "count": len(created)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "math_solution_author_similar_drafts.json")
        return result

    def write_board(self, mission: dict) -> Path:
        lines = [
            "---",
            "tags: [agents, math-expert, solution-author]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# 수학전문가 에이전트 임무",
            "",
            "## 역할",
            "",
            "- 추가 해설 초안을 작성한다.",
            "- 유사문제 초안을 작성한다.",
            "- 유사문제마다 영역, 단원, 개념, 난이도를 명시한다.",
            "- 작성물은 Math Expert 자체 검산 후 Teacher 검수로 넘긴다.",
            "",
            "## 절대 금지",
            "",
            "- 원본문제 수정 금지",
            "- 원본정답 수정 금지",
            "- 원본해설 수정 또는 재표현 금지",
            "- 원본 해설과 추가 해설을 한 필드에 혼합 금지",
            "",
            "## 작성 위치",
            "",
        ]
        for target in mission["writes_only_to"]:
            lines.append(f"- `{target}`")
        lines += [
            "",
            "## 유사문제 필수 메타데이터",
            "",
        ]
        for field in mission["required_metadata_for_similar_problem"]:
            lines.append(f"- `{field}`")
        AUTHOR_BOARD.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return AUTHOR_BOARD

    def write_similar_queue(self, result: dict) -> Path:
        path = BASE_DIR / "wiki" / "00_SIMILAR_AUTHOR_QUEUE.md"
        lines = [
            "---",
            "tags: [similar, queue, math-expert]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# 유사문제 작성 큐",
            "",
            "> 유사문제는 원본문제 변형이 아니라 별도 초안으로 작성합니다.",
            "",
            "| 원본문제 | 영역 | 단원 | 개념 | 난이도 | 원본 해설 색인 |",
            "|---|---|---|---|---|---|",
        ]
        for item in result["items"]:
            lines.append(
                f"| [[{item['id']}]] | {item.get('domain','')} | {item.get('topic','')} | "
                f"{item.get('concept_tags','')} | {item.get('difficulty','')} | "
                f"`{item.get('original_solution_ref','')}` |"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def run(self, task: dict = None) -> dict:
        task = task or {}
        action = task.get("action", "mission")
        if action == "similar_queue":
            return self.similar_queue(task.get("limit", 30))
        if action == "draft_similar":
            return self.draft_similar_templates(task.get("limit", 20))
        return self.mission()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Math Solution Author Agent")
    parser.add_argument("--mission", action="store_true")
    parser.add_argument("--similar-queue", action="store_true")
    parser.add_argument("--draft-similar", action="store_true")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    agent = MathSolutionAuthorAgent()
    if args.draft_similar:
        agent.draft_similar_templates(args.limit)
    elif args.similar_queue:
        agent.similar_queue(args.limit)
    else:
        agent.mission()
