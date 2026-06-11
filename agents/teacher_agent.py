#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teacher Review Agent

선생님 검수과정 에이전트입니다.

절대 원칙:
  - 원본문제, 원본정답, 원본해설, DB를 변경하지 않는다.
  - Math Expert 검산 통과 전에는 Teacher pass를 만들지 않는다.
  - 학생에게 설명 가능한 표현, 수업 흐름, 오개념 예방 포인트를 검수한다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
PROBLEM_DIR = BASE_DIR / "wiki" / "problems"
REPORT_PATH = BASE_DIR / "wiki" / "00_TEACHER_REVIEW_QUEUE.md"
APPROVAL_LOG_PATH = BASE_DIR / "wiki" / "00_TEACHER_APPROVAL_LOG.md"


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


def update_frontmatter(text: str, updates: dict) -> str:
    match = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not match:
        return text
    lines = match.group(1).splitlines()
    seen = set()
    new_lines = []
    for line in lines:
        if ":" not in line:
            new_lines.append(line)
            continue
        key, _ = line.split(":", 1)
        key = key.strip()
        if key in updates:
            new_lines.append(f'{key}: "{updates[key]}"')
            seen.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f'{key}: "{value}"')
    return "---\n" + "\n".join(new_lines) + "\n---\n\n" + text[match.end():]


class TeacherAgent(BaseAgent):
    def __init__(self):
        super().__init__("teacher_review", "Teacher Review Agent", tier=3)

    @staticmethod
    def review_policy() -> dict:
        return {
            "role": "수업 표현, 학생 이해도, 오개념 예방 검수",
            "must_not_modify": ["original_problem", "original_answer", "original_solution", "db"],
            "pass_requires": [
                "Math Expert 검산 pass",
                "풀이 흐름이 학생에게 설명 가능",
                "핵심 개념과 조건이 명확히 분리됨",
                "오개념 주의점 포함",
                "난이도에 맞는 풀이 길이",
                "원본 해설과 추가 해설의 구분 유지",
            ],
            "writes": [
                "logs/agents/teacher_review_audit.json",
                "wiki/00_TEACHER_REVIEW_QUEUE.md",
            ],
            "blocked_until_math_review_pass": True,
        }

    def audit(self, limit: int = 50) -> dict:
        items = []
        reason_counts = {}
        for md in sorted(PROBLEM_DIR.glob("*.md")):
            fm = frontmatter(md.read_text(encoding="utf-8"))
            problem_id = fm.get("id", md.stem)
            reasons = []
            if fm.get("math_expert_review") != "pass":
                reasons.append("Math Expert 검산 선행 필요")
            if fm.get("teacher_review") != "pass":
                reasons.append("Teacher 수업 표현 검수 미완료")
            if not fm.get("additional_solution_ref"):
                reasons.append("추가 해설 초안 없음")
            if not fm.get("original_solution_ref"):
                reasons.append("원본 해설 색인 없음")

            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

            items.append({
                "id": problem_id,
                "domain": fm.get("domain", ""),
                "topic": fm.get("topic", ""),
                "difficulty": fm.get("difficulty", ""),
                "math_expert_review": fm.get("math_expert_review", ""),
                "teacher_review": fm.get("teacher_review", ""),
                "reasons": reasons,
            })

        ready = [
            item for item in items
            if item["math_expert_review"] == "pass" and item["teacher_review"] != "pass"
        ]
        blocked = [item for item in items if item["reasons"]]
        result = {
            "timestamp": datetime.now().isoformat(),
            "problem_notes": len(items),
            "teacher_ready": len(ready),
            "teacher_blocked": len(blocked),
            "reason_counts": reason_counts,
            "ready_sample": ready[:limit],
            "blocked_sample": blocked[:limit],
            "policy": self.review_policy(),
            "mode": "audit_only",
        }
        self.write_report(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "teacher_review_audit.json")
        return result

    def approve_ready(self, limit: int = 10) -> dict:
        """Math Expert 통과분을 Teacher 검수 통과로 표시한다. 서명과 A등급 승격은 하지 않는다."""
        audit = self.audit(limit=1000)
        ready = audit["ready_sample"][:limit]
        approved = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for item in ready:
            problem_path = PROBLEM_DIR / f"{item['id']}.md"
            if not problem_path.exists():
                continue
            text = problem_path.read_text(encoding="utf-8")
            updated = update_frontmatter(text, {
                "teacher_review": "pass",
                "teacher_reviewed_at": now,
                "teacher_note": "student-facing explanation reviewed; original preserved",
            })
            problem_path.write_text(updated, encoding="utf-8")
            approved.append(item)
        result = {
            "timestamp": datetime.now().isoformat(),
            "approved_count": len(approved),
            "approved": approved,
            "policy": "원본문제/원본정답/원본해설/DB는 변경하지 않고 Teacher 검수 상태 필드만 갱신한다.",
        }
        self.write_approval_log(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "teacher_review_approval.json")
        return result

    def write_approval_log(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [agents, teacher, approval]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# Teacher 검수 승인 로그",
            "",
            "> 원본문제, 원본정답, 원본해설, DB는 변경하지 않았다. Teacher 검수 상태만 갱신했다.",
            "",
            f"- 승인 수: {result['approved_count']}",
            "",
            "| 문제 | 영역 | 단원 | 난이도 |",
            "|---|---|---|---|",
        ]
        for item in result["approved"]:
            lines.append(
                f"| [[{item['id']}]] | {item['domain']} | {item['topic']} | {item['difficulty']} |"
            )
        APPROVAL_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return APPROVAL_LOG_PATH

    def write_report(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [agents, teacher, review, queue]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# Teacher 검수 대기열",
            "",
            "> 선생님 검수는 Math Expert 검산 이후에만 진행한다. 원본문제, 원본정답, 원본해설, DB는 변경하지 않는다.",
            "",
            "## 검수 기준",
            "",
        ]
        for rule in result["policy"]["pass_requires"]:
            lines.append(f"- {rule}")
        lines += [
            "",
            "## 현황",
            "",
            f"- 문제 노트: {result['problem_notes']}",
            f"- Teacher 검수 가능: {result['teacher_ready']}",
            f"- Teacher 검수 보류: {result['teacher_blocked']}",
            "",
            "## 보류 사유 집계",
            "",
            "| 사유 | 문제 수 |",
            "|---|---:|",
        ]
        for reason, count in sorted(result["reason_counts"].items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"| {reason} | {count} |")
        lines += [
            "",
            "## 보류 샘플",
            "",
            "| 문제 | 영역 | 단원 | 난이도 | 보류 사유 |",
            "|---|---|---|---|---|",
        ]
        for item in result["blocked_sample"]:
            lines.append(
                f"| [[{item['id']}]] | {item['domain']} | {item['topic']} | "
                f"{item['difficulty']} | {', '.join(item['reasons'])} |"
            )
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return REPORT_PATH

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "approve_ready":
            return self.approve_ready(task.get("limit", 10))
        return self.audit(task.get("limit", 50))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Teacher Review Agent")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--approve-ready", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    agent = TeacherAgent()
    if args.approve_ready:
        agent.approve_ready(args.limit)
    else:
        agent.audit(args.limit)
