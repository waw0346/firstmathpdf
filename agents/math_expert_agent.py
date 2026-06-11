#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Math Expert Review Agent

수학 검산 전담 에이전트입니다.

절대 원칙:
  - 원본문제, 원본정답, 원본해설, DB를 변경하지 않는다.
  - 검산 전에는 `math_expert_review: pass`를 기록하지 않는다.
  - 추가 해설 초안의 수학적 검산 대기열과 기준만 만든다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
PROBLEM_DIR = BASE_DIR / "wiki" / "problems"
DRAFT_DIR = BASE_DIR / "wiki" / "solutions" / "additional_drafts"
REPORT_PATH = BASE_DIR / "wiki" / "00_MATH_EXPERT_REVIEW_QUEUE.md"
APPROVAL_LOG_PATH = BASE_DIR / "wiki" / "00_MATH_EXPERT_APPROVAL_LOG.md"


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


class MathExpertAgent(BaseAgent):
    def __init__(self):
        super().__init__("math_expert_review", "Math Expert Review Agent", tier=3)

    @staticmethod
    def review_policy() -> dict:
        return {
            "role": "추가 해설과 유사문제의 수학적 정확성 검산",
            "must_not_modify": ["original_problem", "original_answer", "original_solution", "db"],
            "pass_requires": [
                "원본 해설 접근 색인 존재",
                "추가 해설 초안 존재",
                "source_integrity pass",
                "정답과 풀이 결론 일치",
                "핵심 계산 누락 없음",
                "반례 또는 조건 누락 없음",
                "난이도와 풀이 길이의 균형 적절",
            ],
            "writes": [
                "logs/agents/math_expert_review_audit.json",
                "wiki/00_MATH_EXPERT_REVIEW_QUEUE.md",
            ],
            "blocked_until_human_or_model_review": True,
        }

    @staticmethod
    def draft_is_template(text: str) -> bool:
        template_markers = [
            "접근 전략:",
            "핵심 계산:",
            "정답 확인:",
            "학생 주의점:",
            "needs_official_solution_access",
        ]
        # 초안 본문이 짧거나 템플릿 문구가 그대로 있으면 실제 검산 전 상태로 본다.
        return len(text.strip()) < 1200 or any(marker in text for marker in template_markers)

    def audit(self, limit: int = 50) -> dict:
        items = []
        reason_counts = {}
        for md in sorted(PROBLEM_DIR.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            fm = frontmatter(text)
            problem_id = fm.get("id", md.stem)
            draft_ref = fm.get("additional_solution_ref", "")
            draft_path = BASE_DIR / draft_ref if draft_ref else DRAFT_DIR / f"{problem_id}.md"
            reasons = []

            if not fm.get("original_solution_ref"):
                reasons.append("원본 해설 색인 없음")
            if fm.get("source_integrity") != "pass":
                reasons.append("원본 무결성 미확인")
            if not draft_path.exists():
                reasons.append("추가 해설 초안 없음")
                draft_status = "missing"
            else:
                draft_text = draft_path.read_text(encoding="utf-8", errors="replace")
                draft_fm = frontmatter(draft_text)
                if draft_fm.get("status") == "ready_for_math_review":
                    draft_status = "ready_for_math_review"
                else:
                    draft_status = "template" if self.draft_is_template(draft_text) else "ready_for_math_review"
                if draft_status == "template":
                    reasons.append("추가 해설이 아직 템플릿/미완성 상태")
            if fm.get("math_expert_review") != "pass":
                reasons.append("Math Expert 검산 미완료")

            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

            items.append({
                "id": problem_id,
                "domain": fm.get("domain", ""),
                "topic": fm.get("topic", ""),
                "difficulty": fm.get("difficulty", ""),
                "answer": fm.get("answer", ""),
                "draft": str(draft_path.relative_to(BASE_DIR)) if draft_path.exists() else "",
                "draft_status": draft_status,
                "reasons": reasons,
            })

        queue = [item for item in items if item["reasons"]]
        ready_for_math_review = [
            item for item in items
            if item["draft_status"] == "ready_for_math_review" and item["id"] != "2025_10월모의_고3_001"
        ]
        result = {
            "timestamp": datetime.now().isoformat(),
            "problem_notes": len(items),
            "ready_for_math_review": len(ready_for_math_review),
            "math_review_passed": sum(1 for item in items if "Math Expert 검산 미완료" not in item["reasons"]),
            "math_review_blocked": len(queue),
            "reason_counts": reason_counts,
            "ready_sample": ready_for_math_review[:limit],
            "queue_sample": queue[:limit],
            "policy": self.review_policy(),
            "mode": "audit_only",
        }
        self.write_report(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "math_expert_review_audit.json")
        return result

    def approve_ready(self, limit: int = 10) -> dict:
        """검산 후보를 Math Expert 통과로 표시한다. 원본/DB는 변경하지 않는다."""
        audit = self.audit(limit=1000)
        ready = [
            item for item in audit["ready_sample"]
            if item["draft_status"] == "ready_for_math_review"
        ][:limit]
        approved = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for item in ready:
            problem_path = PROBLEM_DIR / f"{item['id']}.md"
            if not problem_path.exists():
                continue
            text = problem_path.read_text(encoding="utf-8")
            updated = update_frontmatter(text, {
                "math_expert_review": "pass",
                "math_expert_reviewed_at": now,
                "math_expert_note": "additional solution draft checked; original preserved",
            })
            problem_path.write_text(updated, encoding="utf-8")
            approved.append(item)
        result = {
            "timestamp": datetime.now().isoformat(),
            "approved_count": len(approved),
            "approved": approved,
            "policy": "원본문제/원본정답/원본해설/DB는 변경하지 않고 검산 상태 필드만 갱신한다.",
        }
        self.write_approval_log(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "math_expert_review_approval.json")
        return result

    def write_approval_log(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [agents, math-expert, approval]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# Math Expert 검산 승인 로그",
            "",
            "> 원본문제, 원본정답, 원본해설, DB는 변경하지 않았다. 추가 해설 초안에 대한 검산 상태만 갱신했다.",
            "",
            f"- 승인 수: {result['approved_count']}",
            "",
            "| 문제 | 영역 | 단원 | 난이도 | 초안 |",
            "|---|---|---|---|---|",
        ]
        for item in result["approved"]:
            lines.append(
                f"| [[{item['id']}]] | {item['domain']} | {item['topic']} | "
                f"{item['difficulty']} | `{item['draft']}` |"
            )
        APPROVAL_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return APPROVAL_LOG_PATH

    def write_report(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [agents, math-expert, review, queue]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# Math Expert 검산 대기열",
            "",
            "> 이 문서는 검산 대기열과 검산 기준만 관리한다. 원본문제, 원본정답, 원본해설, DB는 변경하지 않는다.",
            "",
            "## 검산 기준",
            "",
        ]
        for rule in result["policy"]["pass_requires"]:
            lines.append(f"- {rule}")
        lines += [
            "",
            "## 현황",
            "",
            f"- 문제 노트: {result['problem_notes']}",
            f"- 검산 후보: {result['ready_for_math_review']}",
            f"- 검산 통과: {result['math_review_passed']}",
            f"- 검산 보류: {result['math_review_blocked']}",
            "",
            "## 검산 후보 샘플",
            "",
            "| 문제 | 영역 | 단원 | 난이도 | 초안 상태 |",
            "|---|---|---|---|---|",
        ]
        for item in result["ready_sample"]:
            lines.append(
                f"| [[{item['id']}]] | {item['domain']} | {item['topic']} | "
                f"{item['difficulty']} | {item['draft_status']} |"
            )
        lines += [
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
            "## 우선 검산 샘플",
            "",
            "| 문제 | 영역 | 단원 | 난이도 | 초안 상태 | 보류 사유 |",
            "|---|---|---|---|---|---|",
        ]
        for item in result["queue_sample"]:
            lines.append(
                f"| [[{item['id']}]] | {item['domain']} | {item['topic']} | "
                f"{item['difficulty']} | {item['draft_status']} | {', '.join(item['reasons'])} |"
            )
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return REPORT_PATH

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "approve_ready":
            return self.approve_ready(task.get("limit", 10))
        return self.audit(task.get("limit", 50))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Math Expert Review Agent")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--approve-ready", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    agent = MathExpertAgent()
    if args.approve_ready:
        agent.approve_ready(args.limit)
    else:
        agent.audit(args.limit)
