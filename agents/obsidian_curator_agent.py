#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian Curator Agent
문제 노트 frontmatter, 검수 필드, 위키 대시보드 상태를 점검합니다.
"""

import argparse, json, re
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
PROB_DIR = BASE_DIR / "wiki" / "problems"
REQUIRED_FIELDS = [
    "id", "new_id", "title", "grade", "domain", "topic", "difficulty",
    "answer", "crop_path", "stage1_img", "stage2_ans", "stage3_sol",
    "final_grade", "sign_tr", "sign_cp", "concept_tags",
    "original_problem_ref", "original_answer_ref", "original_solution_ref",
    "additional_solution_ref", "solution_index_status",
]


class ObsidianCuratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("obsidian_curator", "Obsidian Curator Agent", tier=2)

    @staticmethod
    def frontmatter(text: str) -> dict:
        match = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not match:
            return {}
        data = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip().strip('"')
        return data

    def audit(self) -> dict:
        files = sorted(PROB_DIR.glob("*.md"))
        missing_by_file = {}
        grade_counts = {}
        for md in files:
            fm = self.frontmatter(md.read_text(encoding="utf-8"))
            missing = [field for field in REQUIRED_FIELDS if field not in fm]
            if missing:
                missing_by_file[md.name] = missing
            grade = fm.get("final_grade", "missing")
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        result = {
            "timestamp": datetime.now().isoformat(),
            "problem_notes": len(files),
            "files_missing_required_fields": len(missing_by_file),
            "sample_missing": dict(list(missing_by_file.items())[:20]),
            "final_grade_counts": grade_counts,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "obsidian_curator_audit.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.audit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Obsidian Curator Agent")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    ObsidianCuratorAgent().audit()
