#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Self Improvement Agent

프로젝트의 자체 발전성을 점검하는 메타 에이전트입니다.

역할:
  - 각 에이전트 감사 결과를 모아 현재 병목을 식별한다.
  - 다음 작업 우선순위를 자동 산출한다.
  - 원본 보존 원칙 위반 가능성을 상위 위험으로 표시한다.
"""

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs" / "agents"
REPORT_PATH = BASE_DIR / "wiki" / "00_SELF_IMPROVEMENT_SYSTEM.md"


class SelfImprovementAgent(BaseAgent):
    def __init__(self):
        super().__init__("self_improvement", "Self Improvement Agent", tier=2)

    @staticmethod
    def read_json(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"_error": "json_decode_failed", "path": str(path)}

    @staticmethod
    def count_files(path: Path, pattern: str = "*.md") -> int:
        return len(list(path.glob(pattern))) if path.exists() else 0

    def git_untracked_count(self) -> int:
        try:
            run = subprocess.run(
                ["git", "--git-dir=.local_git", "--work-tree=.", "status", "--short"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if run.returncode != 0:
                return -1
            return sum(1 for line in run.stdout.splitlines() if line.startswith("??"))
        except Exception:
            return -1

    def audit(self) -> dict:
        qa = self.read_json(LOG_DIR / "qa_smoke.json")
        integrity = self.read_json(LOG_DIR / "integrity_guard_audit.json")
        solution_index = self.read_json(LOG_DIR / "solution_index_audit.json")
        math_review = self.read_json(LOG_DIR / "math_expert_review_audit.json")
        teacher_review = self.read_json(LOG_DIR / "teacher_review_audit.json")
        stage3 = self.read_json(LOG_DIR / "stage3_promotion_audit.json")
        grade = self.read_json(LOG_DIR / "grade_promotion_audit.json")

        qa_ok = all(item.get("ok") for item in qa.get("results", [])) if qa.get("results") else False
        additional_drafts = self.count_files(BASE_DIR / "wiki" / "solutions" / "additional_drafts")
        similar_drafts = self.count_files(BASE_DIR / "wiki" / "similar_drafts")
        problem_notes = self.count_files(BASE_DIR / "wiki" / "problems")
        untracked = self.git_untracked_count()

        risks = []
        if integrity.get("status") != "PASS":
            risks.append("원본 무결성 감사가 PASS가 아님")
        if solution_index.get("missing_index_fields", 1) != 0:
            risks.append("문제 노트 색인 필드 누락 존재")
        if additional_drafts < problem_notes:
            risks.append("추가 해설 초안 부족")
        if stage3.get("stage3_eligible", 0) == 0:
            risks.append("stage3 승격 후보 0개")
        if grade.get("a_grade_eligible", 0) == 0:
            risks.append("A등급 후보 0개")
        if untracked > 30:
            risks.append("추적되지 않은 파일이 많아 로컬 git 운영 안정성 저하")

        next_actions = [
            {
                "priority": 1,
                "owner": "Math Expert Review Agent",
                "task": "추가 해설 초안 276개 중 우선 10개를 실제 검산 대상으로 분리",
                "success_metric": "math_expert_review pass 후보 10개",
            },
            {
                "priority": 2,
                "owner": "Teacher Review Agent",
                "task": "Math Expert 통과분만 수업 표현 검수",
                "success_metric": "teacher_review pass 후보 생성",
            },
            {
                "priority": 3,
                "owner": "Stage3 Promotion Manager",
                "task": "검산/검수 통과분의 stage3 승격 후보 감사",
                "success_metric": "stage3_eligible 증가",
            },
            {
                "priority": 4,
                "owner": "Captain",
                "task": "untracked 파일 보존/추적/무시 분류",
                "success_metric": "untracked 파일 수 감소",
            },
            {
                "priority": 5,
                "owner": "Self Improvement Agent",
                "task": "QA, 검산, 검수, 승격 결과를 매 회차 비교해 병목 변화 기록",
                "success_metric": "병목 사유 감소 추세 기록",
            },
        ]

        result = {
            "timestamp": datetime.now().isoformat(),
            "qa_smoke_ok": qa_ok,
            "source_integrity": integrity.get("status", "unknown"),
            "problem_notes": problem_notes,
            "additional_solution_drafts": additional_drafts,
            "similar_drafts": similar_drafts,
            "missing_index_fields": solution_index.get("missing_index_fields"),
            "math_review_blocked": math_review.get("math_review_blocked"),
            "ready_for_math_review": math_review.get("ready_for_math_review"),
            "teacher_ready": teacher_review.get("teacher_ready"),
            "teacher_blocked": teacher_review.get("teacher_blocked"),
            "stage3_eligible": stage3.get("stage3_eligible"),
            "a_grade_eligible": grade.get("a_grade_eligible"),
            "git_untracked_count": untracked,
            "risks": risks,
            "next_actions": next_actions,
            "mode": "meta_audit_only",
        }
        self.write_report(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "self_improvement_audit.json")
        return result

    def write_report(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [agents, self-improvement, meta, governance]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# 자체 발전 시스템",
            "",
            "> 이 문서는 에이전트 감사 결과를 모아 다음 병목과 우선순위를 산출한다. 원본과 DB는 변경하지 않는다.",
            "",
            "## 현재 상태",
            "",
            f"- QA smoke: {'PASS' if result['qa_smoke_ok'] else 'WARN'}",
            f"- 원본 무결성: {result['source_integrity']}",
            f"- 문제 노트: {result['problem_notes']}",
            f"- 추가 해설 초안: {result['additional_solution_drafts']}",
            f"- 유사문제 초안: {result['similar_drafts']}",
            f"- 색인 누락: {result['missing_index_fields']}",
            f"- Math Expert 검산 보류: {result['math_review_blocked']}",
            f"- Math Expert 검산 후보: {result['ready_for_math_review']}",
            f"- Teacher 검수 가능: {result['teacher_ready']}",
            f"- Teacher 검수 보류: {result['teacher_blocked']}",
            f"- stage3 승격 후보: {result['stage3_eligible']}",
            f"- A등급 후보: {result['a_grade_eligible']}",
            f"- local git untracked 파일 수: {result['git_untracked_count']}",
            "",
            "## 구조적 위험",
            "",
        ]
        if result["risks"]:
            for risk in result["risks"]:
                lines.append(f"- {risk}")
        else:
            lines.append("- 현재 상위 위험 없음")
        lines += [
            "",
            "## 다음 자기 발전 우선순위",
            "",
            "| 우선순위 | 담당 | 작업 | 성공 기준 |",
            "|---:|---|---|---|",
        ]
        for item in result["next_actions"]:
            lines.append(
                f"| {item['priority']} | {item['owner']} | {item['task']} | {item['success_metric']} |"
            )
        lines += [
            "",
            "## 자기 발전 루프",
            "",
            "1. Integrity Guard가 원본 변경 여부를 확인한다.",
            "2. Solution Index가 모든 문제의 원본/추가 해설 색인을 확인한다.",
            "3. Math Expert가 추가 해설의 수학적 검산 대기열을 만든다.",
            "4. Teacher가 검산 통과분만 수업 표현 검수 대기열로 받는다.",
            "5. Stage3 Promotion Manager가 검산/검수 통과분만 승격 후보로 본다.",
            "6. Grade Promotion Agent가 서명 완료분만 A등급 후보로 본다.",
            "7. Self Improvement Agent가 병목 변화를 기록하고 다음 우선순위를 갱신한다.",
        ]
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return REPORT_PATH

    def run(self, task: dict = None) -> dict:
        return self.audit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Self Improvement Agent")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    SelfImprovementAgent().audit()
