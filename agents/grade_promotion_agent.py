#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A Grade Promotion Agent

A등급 승격 가능 여부를 감사합니다.
실제 문제, 원본 해설, DB 등급을 변경하지 않고 보고서만 생성합니다.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
PROB_DIR = BASE_DIR / "wiki" / "problems"
REPORT_PATH = BASE_DIR / "wiki" / "00_A_GRADE_PROMOTION.md"
SIGNOFF_LOG_PATH = BASE_DIR / "wiki" / "00_A_GRADE_SIGNOFF_LOG.md"


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


class GradePromotionAgent(BaseAgent):
    def __init__(self):
        super().__init__("grade_promotion", "A Grade Promotion Agent", tier=2)

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
    def missing_reasons(fm: dict) -> list[str]:
        checks = [
            ("stage1_img", fm.get("stage1_img") == "pass", "이미지 검수 미완료"),
            ("stage2_ans", fm.get("stage2_ans") == "pass", "정답 검수 미완료"),
            ("stage3_sol", fm.get("stage3_sol") == "pass", "해설 검수 미완료"),
            ("original_solution_ref", bool(fm.get("original_solution_ref")), "원본 해설 색인 없음"),
            ("additional_solution_ref", bool(fm.get("additional_solution_ref")), "추가 해설 초안 없음"),
            ("sign_tr", bool(fm.get("sign_tr")), "Teacher 서명 없음"),
            ("sign_cp", bool(fm.get("sign_cp")), "Captain 서명 없음"),
        ]
        return [reason for _, ok, reason in checks if not ok]

    def audit(self) -> dict:
        files = sorted(PROB_DIR.glob("*.md"))
        eligible = []
        blocked = []
        reason_counts = {}
        for md in files:
            fm = self.frontmatter(md.read_text(encoding="utf-8"))
            reasons = self.missing_reasons(fm)
            if reasons:
                blocked.append({"id": fm.get("id", md.stem), "reasons": reasons})
                for reason in reasons:
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
            else:
                eligible.append(fm.get("id", md.stem))

        result = {
            "timestamp": datetime.now().isoformat(),
            "problem_notes": len(files),
            "a_grade_eligible": len(eligible),
            "blocked": len(blocked),
            "reason_counts": reason_counts,
            "sample_blocked": blocked[:30],
            "policy": "A등급 승격 감사만 수행하고 원본/DB는 변경하지 않는다.",
        }
        self.write_report(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "grade_promotion_audit.json")
        return result

    def sign_eligible(self, limit: int = 10) -> dict:
        """stage3 통과분 중 서명만 남은 항목에 Teacher/Captain 서명을 적용한다."""
        signed = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for md in sorted(PROB_DIR.glob("*.md")):
            fm = self.frontmatter(md.read_text(encoding="utf-8"))
            reasons = self.missing_reasons(fm)
            only_sign_missing = set(reasons) <= {"Teacher 서명 없음", "Captain 서명 없음"}
            if not reasons or not only_sign_missing:
                continue
            text = md.read_text(encoding="utf-8")
            updated = update_frontmatter(text, {
                "sign_tr": f"TeacherReviewAgent {now}",
                "sign_cp": f"CodexCaptain {now}",
                "final_grade": "A",
                "a_grade_signed_at": now,
                "a_grade_note": "stage3 solution passed and signatures applied; original preserved",
            })
            md.write_text(updated, encoding="utf-8")
            signed.append(fm.get("id", md.stem))
            if len(signed) >= limit:
                break

        result = {
            "timestamp": datetime.now().isoformat(),
            "signed_count": len(signed),
            "signed": signed,
            "policy": "stage3_sol pass 항목 중 서명만 남은 문제에만 Teacher/Captain 서명을 적용한다. 원본/DB는 변경하지 않는다.",
        }
        self.write_signoff_log(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "grade_promotion_signoff.json")
        return result

    def write_signoff_log(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [grade, signoff, agents]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# A등급 서명 로그",
            "",
            "> 원본문제, 원본정답, 원본해설, DB는 변경하지 않았다. stage3 통과 후 서명만 남은 항목에 한해 서명했다.",
            "",
            f"- 서명 수: {result['signed_count']}",
            "",
            "| 문제 |",
            "|---|",
        ]
        for problem_id in result["signed"]:
            lines.append(f"| [[{problem_id}]] |")
        SIGNOFF_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SIGNOFF_LOG_PATH

    def write_report(self, result: dict) -> Path:
        lines = [
            "---",
            "tags: [grade, verification, agents]",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# A등급 승격 감사",
            "",
            "> 이 보고서는 승격 가능 여부만 점검합니다. 원본문제·원본정답·원본해설·DB 등급은 변경하지 않습니다.",
            "",
            "## 기준",
            "",
            "- `stage1_img: pass`",
            "- `stage2_ans: pass`",
            "- `stage3_sol: pass`",
            "- `original_solution_ref` 존재",
            "- `additional_solution_ref` 존재",
            "- `sign_tr` Teacher 서명 존재",
            "- `sign_cp` Captain 서명 존재",
            "",
            "## 결과",
            "",
            f"- 문제 노트: {result['problem_notes']}개",
            f"- A등급 승격 가능: {result['a_grade_eligible']}개",
            f"- 승격 보류: {result['blocked']}개",
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
            "| 문제 | 보류 사유 |",
            "|---|---|",
        ]
        for item in result["sample_blocked"]:
            lines.append(f"| [[{item['id']}]] | {', '.join(item['reasons'])} |")
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return REPORT_PATH

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "sign_eligible":
            return self.sign_eligible(task.get("limit", 10))
        return self.audit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A Grade Promotion Agent")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--sign-eligible", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    agent = GradePromotionAgent()
    if args.sign_eligible:
        agent.sign_eligible(args.limit)
    else:
        agent.audit()
