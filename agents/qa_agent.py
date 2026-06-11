#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QA Agent
핵심 회귀 점검을 한 번에 실행합니다.
"""

import argparse, json, subprocess, sys
from datetime import datetime
from pathlib import Path
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent


class QAAgent(BaseAgent):
    def __init__(self):
        super().__init__("qa", "QA Agent", tier=2)

    def smoke(self) -> dict:
        commands = [
            ["agents/integrity_guard_agent.py", "--audit"],
            ["agents/db_guardian_agent.py", "--status"],
            ["scripts/crop_pipeline_audit.py"],
            ["scripts/source_trace_index.py"],
            ["scripts/obsidian_integration_audit.py"],
            ["agents/senior_engineer.py", "--check", "all"],
            ["agents/math_solution_author_agent.py", "--mission"],
            ["agents/math_expert_agent.py", "--audit", "--limit", "20"],
            ["agents/teacher_agent.py", "--audit", "--limit", "20"],
            ["agents/solution_index_agent.py", "--audit"],
            ["agents/stage3_promotion_manager_agent.py", "--audit"],
            ["agents/grade_promotion_agent.py", "--audit"],
            ["agents/verification_agent.py", "--status"],
            ["agents/obsidian_curator_agent.py", "--audit"],
            ["agents/concept_tagging_agent.py", "--plan", "--limit", "5"],
            ["agents/student_success_agent.py", "--readiness"],
            ["agents/jinwoo_proxy_agent.py", "--diagnostic-set", "--count", "20"],
            ["agents/answer_solution_curator_agent.py", "--queue", "--limit", "20"],
            ["agents/self_improvement_agent.py", "--audit"],
        ]
        results = []
        for cmd in commands:
            run = subprocess.run(
                [sys.executable] + cmd,
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            results.append({"command": " ".join(cmd), "returncode": run.returncode, "ok": run.returncode == 0})
        report = {"timestamp": datetime.now().isoformat(), "results": results}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        self.save_result(report, "qa_smoke.json")
        return report

    def run(self, task: dict = None) -> dict:
        return self.smoke()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QA Agent")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    QAAgent().smoke()
