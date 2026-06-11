#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage3 Promotion Manager Agent

stage3_sol 승격 기준을 정의하고 관리합니다.

이 에이전트는 기본적으로 감사만 수행합니다. 원본문제, 원본정답,
원본해설, DB 등급을 변경하지 않습니다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
PROB_DIR = BASE_DIR / "wiki" / "problems"
REPORT_PATH = BASE_DIR / "wiki" / "00_STAGE3_PROMOTION_POLICY.md"
PROMOTION_LOG_PATH = BASE_DIR / "wiki" / "00_STAGE3_PROMOTION_LOG.md"


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


class Stage3PromotionManagerAgent(BaseAgent):
    def __init__(self):
        super().__init__("stage3_promotion_manager", "Stage3 Promotion Manager Agent", tier=2)

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

    @staticmethod
    def policy() -> dict:
        return {
            "stage3_sol_pass_required": [
                {"field": "stage1_img", "expected": "pass", "reason": "이미지 검수 통과 필요"},
                {"field": "stage2_ans", "expected": "pass", "reason": "정답 검수 통과 필요"},
                {"field": "original_solution_ref", "expected": "nonempty", "reason": "원본 해설 색인 필요"},
                {"field": "additional_solution_ref", "expected": "nonempty", "reason": "추가 해설 초안 필요"},
                {"field": "math_expert_review", "expected": "pass", "reason": "Math Expert 검산 필요"},
                {"field": "teacher_review", "expected": "pass", "reason": "Teacher 수업 표현 검수 필요"},
                {"field": "source_integrity", "expected": "pass", "reason": "원본 무결성 확인 필요"},
            ],
            "metadata_required": [
                "domain",
                "topic",
                "concept_tags",
                "difficulty",
            ],
            "forbidden": [
                "원본문제 수정",
                "원본정답 수정",
                "원본해설 수정",
                "원본 해설과 추가 해설의 동일 필드 혼합",
                "공식 해설 미확인 상태의 stage3_sol pass",
            ],
            "promotion_result_fields": [
                "stage3_sol",
                "stage3_note",
                "sign_tr",
                "sign_cp",
            ],
        }

    @staticmethod
    def check_expected(fm: dict, field: str, expected: str) -> bool:
        value = fm.get(field, "")
        if expected == "nonempty":
            return bool(value)
        if field in ("math_expert_review", "teacher_review", "source_integrity"):
            # These review fields are not yet in all notes, so absence blocks promotion.
            return value == expected
        return value == expected

    def audit(self) -> dict:
        policy = self.policy()
        files = sorted(PROB_DIR.glob("*.md"))
        eligible = []
        blocked = []
        reason_counts = {}
        for md in files:
            fm = self.frontmatter(md.read_text(encoding="utf-8"))
            reasons = []
            for rule in policy["stage3_sol_pass_required"]:
                if not self.check_expected(fm, rule["field"], rule["expected"]):
                    reasons.append(rule["reason"])
            for field in policy["metadata_required"]:
                if not fm.get(field):
                    reasons.append(f"{field} 메타데이터 필요")
            item = {
                "id": fm.get("id", md.stem),
                "domain": fm.get("domain", ""),
                "topic": fm.get("topic", ""),
                "concept_tags": fm.get("concept_tags", ""),
                "difficulty": fm.get("difficulty", ""),
                "reasons": reasons,
            }
            if reasons:
                blocked.append(item)
                for reason in reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
            else:
                eligible.append(item)
        result = {
            "timestamp": datetime.now().isoformat(),
            "problem_notes": len(files),
            "stage3_eligible": len(eligible),
            "stage3_blocked": len(blocked),
            "reason_counts": reason_counts,
            "sample_blocked": blocked[:40],
            "policy": policy,
            "mode": "audit_only",
        }
        self.write_report(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "stage3_promotion_audit.json")
        return result

    def promote_eligible(self, limit: int = 10) -> dict:
        """stage3 eligible 항목만 승격한다. 원본문제/정답/해설/DB는 변경하지 않는다."""
        audit = self.audit()
        eligible_ids = []
        for md in sorted(PROB_DIR.glob("*.md")):
            fm = self.frontmatter(md.read_text(encoding="utf-8"))
            reasons = []
            for rule in audit["policy"]["stage3_sol_pass_required"]:
                if not self.check_expected(fm, rule["field"], rule["expected"]):
                    reasons.append(rule["reason"])
            for field in audit["policy"]["metadata_required"]:
                if not fm.get(field):
                    reasons.append(f"{field} metadata required")
            if not reasons:
                eligible_ids.append(fm.get("id", md.stem))

        promoted = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for problem_id in eligible_ids[:limit]:
            problem_path = PROB_DIR / f"{problem_id}.md"
            if not problem_path.exists():
                continue
            text = problem_path.read_text(encoding="utf-8")
            updated = update_frontmatter(text, {
                "stage3_sol": "pass",
                "stage3_promoted_at": now,
                "stage3_note": "additional solution passed Math Expert and Teacher review; original preserved",
            })
            problem_path.write_text(updated, encoding="utf-8")
            promoted.append(problem_id)

        result = {
            "timestamp": datetime.now().isoformat(),
            "promoted_count": len(promoted),
            "promoted": promoted,
            "policy": "원본문제/원본정답/원본해설/DB는 변경하지 않고 stage3_sol 상태만 승격한다.",
        }
        self.write_promotion_log(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "stage3_promotion_apply.json")
        return result

    def write_promotion_log(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [stage3, promotion, approval]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# stage3_sol 승격 로그",
            "",
            "> 원본문제, 원본정답, 원본해설, DB는 변경하지 않았다. 추가 해설 검수 상태에 따라 stage3_sol만 승격했다.",
            "",
            f"- 승격 수: {result['promoted_count']}",
            "",
            "| 문제 |",
            "|---|",
        ]
        for problem_id in result["promoted"]:
            lines.append(f"| [[{problem_id}]] |")
        PROMOTION_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return PROMOTION_LOG_PATH

    def write_report(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [stage3, promotion, policy, agents]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# stage3_sol 승격 기준 및 관리",
            "",
            "> 이 문서는 stage3 승격 기준입니다. 감사 모드에서는 원본문제·원본정답·원본해설·DB를 변경하지 않습니다.",
            "",
            "## 승격 조건",
            "",
        ]
        for rule in result["policy"]["stage3_sol_pass_required"]:
            lines.append(f"- `{rule['field']}` = `{rule['expected']}`: {rule['reason']}")
        lines += [
            "",
            "## 필수 메타데이터",
            "",
        ]
        for field in result["policy"]["metadata_required"]:
            lines.append(f"- `{field}`")
        lines += [
            "",
            "## 금지 사항",
            "",
        ]
        for item in result["policy"]["forbidden"]:
            lines.append(f"- {item}")
        lines += [
            "",
            "## 감사 결과",
            "",
            f"- 문제 노트: {result['problem_notes']}개",
            f"- stage3 승격 가능: {result['stage3_eligible']}개",
            f"- stage3 보류: {result['stage3_blocked']}개",
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
            "| 문제 | 영역 | 단원 | 개념 | 난이도 | 보류 사유 |",
            "|---|---|---|---|---|---|",
        ]
        for item in result["sample_blocked"]:
            lines.append(
                f"| [[{item['id']}]] | {item['domain']} | {item['topic']} | "
                f"{item['concept_tags']} | {item['difficulty']} | {', '.join(item['reasons'])} |"
            )
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return REPORT_PATH

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "promote_eligible":
            return self.promote_eligible(task.get("limit", 10))
        return self.audit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage3 Promotion Manager Agent")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--promote-eligible", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    agent = Stage3PromotionManagerAgent()
    if args.promote_eligible:
        agent.promote_eligible(args.limit)
    else:
        agent.audit()
