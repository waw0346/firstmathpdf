#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Student Success Agent
학생 맞춤 추천, 오답 이력, 취약 단원 분석 준비 상태를 점검합니다.
"""

import argparse, json
from datetime import datetime
from base_agent import BaseAgent


class StudentSuccessAgent(BaseAgent):
    def __init__(self):
        super().__init__("student_success", "Student Success Agent", tier=3)

    def readiness(self) -> dict:
        conn, _ = self.get_db()
        students = [dict(r) for r in conn.execute("SELECT id, name, grade, school, region FROM students").fetchall()]
        answers = conn.execute("SELECT COUNT(*) FROM student_answers").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0]
        tagged = conn.execute("SELECT COUNT(*) FROM problems WHERE concept_tags IS NOT NULL AND concept_tags!=''").fetchone()[0]
        conn.close()
        result = {
            "timestamp": datetime.now().isoformat(),
            "students": students,
            "student_answers": answers,
            "study_sessions": sessions,
            "concept_tagged_problems": tagged,
            "next_action": "진우.md 생성 후 20문제 진단 세트와 오답 입력 루프를 시작한다.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "student_success_readiness.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.readiness()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Student Success Agent")
    parser.add_argument("--readiness", action="store_true")
    args = parser.parse_args()
    StudentSuccessAgent().readiness()
