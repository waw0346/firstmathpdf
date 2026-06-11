#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Student Agent — 학생 에이전트 시뮬레이터
풀이 시뮬레이션 · 오류 패턴 분석 · 진도 추적 · 피드백

사용법:
  python agents/student_agent.py --simulate --level 중 --problems 5
  python agents/student_agent.py --student 홍길동 --homework-check
  python agents/student_agent.py --error-analysis
  python agents/student_agent.py --progress --student 홍길동
============================================================
"""

import json, random, argparse
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR     = Path(__file__).parent.parent
STUDENTS_DIR = BASE_DIR / "data" / "students"


class StudentAgent(BaseAgent):
    """학생 에이전트 — 풀이 시뮬레이션 및 학습 관리"""

    # 실력 수준별 정답률 파라미터
    LEVEL_CONFIG = {
        "하": {"correct_rate": 0.85, "careless_rate": 0.05, "concept_err_rate": 0.10},
        "중": {"correct_rate": 0.68, "careless_rate": 0.10, "concept_err_rate": 0.22},
        "상": {"correct_rate": 0.48, "careless_rate": 0.12, "concept_err_rate": 0.40},
        "최상": {"correct_rate": 0.22, "careless_rate": 0.08, "concept_err_rate": 0.70},
    }

    # 오류 유형 분류
    ERROR_TYPES = {
        "calculation": "계산 실수 (부호, 사칙연산)",
        "concept":     "개념 혼동 (공식 오적용)",
        "reading":     "문제 오독 (조건 누락)",
        "timeout":     "시간 부족 (미완성)",
        "blank":       "포기 (무답)",
    }

    def __init__(self):
        super().__init__("student", "Student Agent", tier=3)

    # ──────────────────────────────────────────────────────
    # 풀이 시뮬레이션
    # ──────────────────────────────────────────────────────
    def simulate_solve(self, problem: dict, student_level: str) -> dict:
        """학생 실력 수준에 따른 풀이 시뮬레이션"""
        cfg  = self.LEVEL_CONFIG.get(student_level, self.LEVEL_CONFIG["중"])
        diff = problem.get("difficulty", "중")

        # 난이도 vs 실력 조정
        diff_map = {"하": 0, "중": 1, "상": 2, "최상": 3}
        lvl_map  = {"하": 0, "중": 1, "상": 2, "최상": 3}
        diff_gap = diff_map.get(diff, 1) - lvl_map.get(student_level, 1)

        # 난이도가 실력보다 높을수록 오답 가능성 증가
        adjusted_rate = max(0.05, cfg["correct_rate"] - diff_gap * 0.20)
        rand = random.random()

        if rand < adjusted_rate:
            # 정답
            return {
                "is_correct":  True,
                "answer":      problem.get("answer", ""),
                "error_type":  None,
                "time_spent":  self._estimate_time(diff, student_level, correct=True),
            }
        else:
            # 오답 — 오류 유형 결정
            error_type = self._pick_error(cfg, diff_gap)
            wrong_ans  = self._generate_wrong_answer(problem, error_type)
            return {
                "is_correct":  False,
                "answer":      wrong_ans,
                "error_type":  error_type,
                "error_desc":  self.ERROR_TYPES.get(error_type, ""),
                "time_spent":  self._estimate_time(diff, student_level, correct=False),
            }

    def _pick_error(self, cfg: dict, diff_gap: int) -> str:
        """오류 유형 결정"""
        if diff_gap >= 2:
            return random.choice(["concept", "timeout", "blank"])
        elif diff_gap == 1:
            return random.choice(["concept", "calculation", "reading"])
        else:
            return random.choice(["calculation", "calculation", "reading"])

    def _generate_wrong_answer(self, problem: dict, error_type: str) -> str:
        """오답 생성 (실제 오류 패턴 모사)"""
        ans = problem.get("answer", "1")
        try:
            num = int(ans)
            if error_type == "calculation":
                return str(num + random.choice([-1, 1, -2, 2]))
            elif error_type == "concept":
                return str(num * random.choice([2, -1]) + random.randint(-5, 5))
            elif error_type == "reading":
                return str(num + random.choice([-10, 10, -5, 5]))
            elif error_type in ("timeout", "blank"):
                return ""
        except ValueError:
            # 선다형
            choices = ["1", "2", "3", "4", "5"]
            wrong = [c for c in choices if c != ans]
            return random.choice(wrong) if wrong else "1"
        return ""

    def _estimate_time(self, diff: str, level: str, correct: bool) -> int:
        """예상 풀이 시간 (초)"""
        base = {"하": 90, "중": 150, "상": 240, "최상": 360}.get(diff, 150)
        multiplier = {"하": 0.7, "중": 1.0, "상": 1.3, "최상": 1.8}.get(level, 1.0)
        if not correct:
            multiplier *= 1.4  # 오답이면 시간 더 소요
        return int(base * multiplier + random.randint(-30, 30))

    # ──────────────────────────────────────────────────────
    # 일괄 시뮬레이션 (테스트 모드)
    # ──────────────────────────────────────────────────────
    def run_simulation(self, student_level: str = "중",
                       count: int = 5, target_diff: str = None) -> dict:
        """여러 문제 연속 풀이 시뮬레이션"""
        conn, _ = self.get_db()
        sql = "SELECT * FROM problems"
        params = []
        if target_diff:
            sql += " WHERE difficulty=?"
            params.append(target_diff)
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(count)
        rows = conn.execute(sql, params).fetchall()
        conn.close()

        problems = [dict(r) for r in rows]
        session_results = []
        correct_total = wrong_total = 0
        error_counts = {k: 0 for k in self.ERROR_TYPES}
        total_time = 0

        print(f"\n{'='*60}")
        print(f"📝 Student Agent 시뮬레이션 (실력: {student_level})")
        print(f"{'='*60}")

        for p in problems:
            result = self.simulate_solve(p, student_level)
            total_time += result["time_spent"]
            mark = "✅" if result["is_correct"] else "❌"

            if result["is_correct"]:
                correct_total += 1
            else:
                wrong_total += 1
                if result.get("error_type"):
                    error_counts[result["error_type"]] += 1

            print(f"  {mark} [{p['difficulty']}] {p['title'][:25]}")
            if not result["is_correct"]:
                print(f"      오류: {result.get('error_desc', '')} | 제출: '{result['answer']}'")

            session_results.append({
                "problem_id": p["id"],
                "title":      p["title"],
                "difficulty": p["difficulty"],
                **result
            })

        score = round(correct_total / max(len(problems), 1) * 100, 1)
        top_error = max(error_counts, key=error_counts.get) if any(error_counts.values()) else None

        summary = {
            "student_level": student_level,
            "total":         len(problems),
            "correct":       correct_total,
            "wrong":         wrong_total,
            "score":         score,
            "total_time_min": round(total_time / 60, 1),
            "avg_time_sec":  round(total_time / max(len(problems), 1)),
            "top_error":     top_error,
            "error_counts":  {k: v for k, v in error_counts.items() if v > 0},
        }

        print(f"\n📊 시뮬레이션 결과:")
        print(f"  점수: {score}% ({correct_total}/{len(problems)})")
        print(f"  총 소요 시간: {summary['total_time_min']}분")
        if top_error:
            print(f"  주요 오류 유형: {self.ERROR_TYPES[top_error]}")

        # 교사 에이전트에 보고
        self.send_message("teacher", "simulation_result",
                         {"summary": summary, "details": session_results}, priority="medium")

        out = self.save_result({"summary": summary, "details": session_results},
                               f"student_simulation_{student_level}.json")
        return {"summary": summary, "details": session_results}

    # ──────────────────────────────────────────────────────
    # 학생 진도 조회
    # ──────────────────────────────────────────────────────
    def get_progress(self, student_name: str) -> dict:
        """특정 학생의 학습 진도 분석"""
        sf = STUDENTS_DIR / f"{student_name}.json"
        if not sf.exists():
            print(f"⚠️ 학생 파일 없음: {student_name}")
            return {}

        data = json.loads(sf.read_text(encoding="utf-8"))
        hws  = data.get("homework", [])
        scored = [h for h in hws if h.get("score") is not None]
        avg = round(sum(h["score"] for h in scored) / max(len(scored), 1), 1)

        # 오답 패턴 분석
        wrong_domains = {}
        for hw in scored:
            for p in hw.get("problems", []):
                if not p.get("is_correct", True):
                    domain = p.get("domain", "미분류")
                    wrong_domains[domain] = wrong_domains.get(domain, 0) + 1

        progress = {
            "name":          student_name,
            "total_hw":      len(hws),
            "completed_hw":  len(scored),
            "avg_score":     avg,
            "weak_domains":  sorted(wrong_domains, key=wrong_domains.get, reverse=True)[:3],
            "trend":         "향상" if len(scored) >= 2 and scored[-1]["score"] > scored[-2]["score"] else "유지",
        }

        print(f"\n📈 {student_name} 학습 진도:")
        print(f"  평균 점수: {avg}%")
        print(f"  취약 영역: {', '.join(progress['weak_domains']) or '없음'}")
        print(f"  추세: {progress['trend']}")

        return progress

    # ──────────────────────────────────────────────────────
    # 오류 패턴 분석
    # ──────────────────────────────────────────────────────
    def error_analysis(self) -> dict:
        """전체 학생 오류 패턴 집계"""
        all_errors = {k: 0 for k in self.ERROR_TYPES}
        domain_errors = {}
        difficulty_errors = {}
        total_attempts = 0

        for sf in STUDENTS_DIR.glob("*.json"):
            data = json.loads(sf.read_text(encoding="utf-8"))
            for hw in data.get("homework", []):
                for p in hw.get("problems", []):
                    total_attempts += 1
                    if not p.get("is_correct", True):
                        etype = p.get("error_type", "unknown")
                        if etype in all_errors:
                            all_errors[etype] += 1

        print(f"\n🔍 전체 오류 패턴 분석 ({total_attempts}회 시도)")
        for etype, count in sorted(all_errors.items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"  {self.ERROR_TYPES[etype]}: {count}건")

        result = {"total_attempts": total_attempts, "error_counts": all_errors}
        self.save_result(result, "student_error_analysis.json")
        return result

    def run(self, task: dict = None) -> dict:
        task = task or {}
        action = task.get("action", "simulate")
        if action == "simulate":
            return self.run_simulation(task.get("level", "중"), task.get("count", 5))
        elif action == "progress":
            return self.get_progress(task.get("student", ""))
        elif action == "error_analysis":
            return self.error_analysis()
        return {}


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    parser = argparse.ArgumentParser(description="Student Agent")
    parser.add_argument("--simulate",       action="store_true", help="풀이 시뮬레이션")
    parser.add_argument("--level",          default="중", help="학생 실력 수준: 하/중/상/최상")
    parser.add_argument("--count",          type=int, default=5, help="문제 수")
    parser.add_argument("--difficulty",     help="문제 난이도 필터")
    parser.add_argument("--progress",       action="store_true", help="진도 조회")
    parser.add_argument("--student",        help="학생 이름")
    parser.add_argument("--error-analysis", action="store_true", help="오류 패턴 분석")
    args = parser.parse_args()

    agent = StudentAgent()

    if args.simulate:
        agent.run_simulation(args.level, args.count, args.difficulty)
    elif args.progress and args.student:
        agent.get_progress(args.student)
    elif args.error_analysis:
        agent.error_analysis()
    else:
        parser.print_help()
