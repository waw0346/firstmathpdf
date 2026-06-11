#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jinwoo Proxy Agent
진우 학생을 임의 학생 에이전트로 실행하기 위한 전용 프록시입니다.

원칙:
  - 실제 학생 기록을 오염시키지 않기 위해 기본은 dry-run입니다.
  - DB에 쓰는 작업은 명시적 --commit-results가 있을 때만 허용합니다.
"""

import argparse, json, random, sys
from datetime import datetime
from pathlib import Path
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class JinwooProxyAgent(BaseAgent):
    def __init__(self):
        super().__init__("jinwoo_proxy", "Jinwoo Proxy Agent", tier=3)

    def build_diagnostic_set(self, count: int = 20) -> dict:
        conn, _ = self.get_db()
        rows = [dict(r) for r in conn.execute("""
            SELECT id, title, domain, topic, difficulty, answer, concept_tags
            FROM problems
            WHERE final_grade IN ('B','A')
            ORDER BY
              CASE difficulty
                WHEN '중하' THEN 1 WHEN '중' THEN 2 WHEN '중상' THEN 3
                WHEN '상' THEN 4 WHEN '최상' THEN 5 ELSE 6
              END,
              RANDOM()
            LIMIT ?
        """, (count,)).fetchall()]
        conn.close()
        result = {
            "student": "진우",
            "mode": "diagnostic_set",
            "count": len(rows),
            "generated_at": datetime.now().isoformat(),
            "problems": rows,
            "policy": "진단 세트 생성은 원본문제/원본해설을 변경하지 않는다.",
        }
        out = BASE_DIR / "logs" / "agents" / "jinwoo_diagnostic_set.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.write_obsidian_diagnostic(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def write_obsidian_diagnostic(self, result: dict) -> Path:
        path = BASE_DIR / "wiki" / "students" / "진우_진단세트.md"
        lines = [
            "---",
            "tags: [student, diagnostic, jinwoo]",
            "student: 진우",
            f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
            "# 진우 진단 세트",
            "",
            "> dry-run 진단 세트입니다. 실제 학생 기록에는 반영하지 않았습니다.",
            "",
            "| 번호 | 문제 | 영역 | 단원 | 난이도 | 정답 | 개념 태그 |",
            "|---|---|---|---|---|---|---|",
        ]
        for idx, p in enumerate(result["problems"], start=1):
            lines.append(
                f"| {idx} | [[{p['id']}]] | {p['domain']} | {p['topic']} | {p['difficulty']} | {p['answer']} | {p.get('concept_tags','')} |"
            )
        lines += [
            "",
            "## 운영 원칙",
            "",
            "- 이 세트 생성은 원본문제/원본해설을 변경하지 않는다.",
            "- 실제 풀이 결과 입력 전까지 `student_answers`에 반영하지 않는다.",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def dry_run_attempts(self, count: int = 20) -> dict:
        diagnostic = self.build_diagnostic_set(count)
        attempts = []
        for p in diagnostic["problems"]:
            # 진우 프록시는 실제 기록 전까지 보수적 확률 모델만 사용합니다.
            diff = p.get("difficulty") or "중"
            correct_rate = {"하": 0.9, "중하": 0.82, "중": 0.72, "중상": 0.58, "상": 0.42, "최상": 0.25}.get(diff, 0.65)
            ok = random.random() < correct_rate
            attempts.append({
                "problem_id": p["id"],
                "submitted_answer": p["answer"] if ok else "",
                "is_correct": ok,
                "error_type": None if ok else random.choice(["concept", "calculation", "timeout"]),
                "dry_run": True,
            })
        result = {
            "student": "진우",
            "mode": "dry_run_attempts",
            "generated_at": datetime.now().isoformat(),
            "attempts": attempts,
            "commit_to_db": False,
        }
        out = BASE_DIR / "logs" / "agents" / "jinwoo_dry_run_attempts.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def run(self, task: dict = None) -> dict:
        task = task or {}
        if task.get("action") == "attempts":
            return self.dry_run_attempts(task.get("count", 20))
        return self.build_diagnostic_set(task.get("count", 20))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jinwoo Proxy Agent")
    parser.add_argument("--diagnostic-set", action="store_true")
    parser.add_argument("--dry-run-attempts", action="store_true")
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    agent = JinwooProxyAgent()
    if args.dry_run_attempts:
        agent.dry_run_attempts(args.count)
    else:
        agent.build_diagnostic_set(args.count)
