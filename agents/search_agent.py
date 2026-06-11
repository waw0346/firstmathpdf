#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search Agent
유사문제/검색 인덱스 준비 상태를 점검합니다.
"""

import argparse, json
from datetime import datetime
from base_agent import BaseAgent


class SearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("search", "Search Agent", tier=2)

    def status(self) -> dict:
        conn, _ = self.get_db()
        total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        similar = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]
        groups = 0
        try:
            groups = conn.execute("SELECT COUNT(*) FROM similar_groups").fetchone()[0]
        except Exception:
            groups = 0
        zero_similar = conn.execute("""
            SELECT COUNT(*) FROM problems p
            WHERE NOT EXISTS (
                SELECT 1 FROM similar_problems s
                WHERE s.problem_id=p.id OR s.similar_id=p.id
            )
        """).fetchone()[0]
        conn.close()
        result = {
            "timestamp": datetime.now().isoformat(),
            "problems": total,
            "similar_pairs": similar,
            "similar_groups": groups,
            "problems_without_similarity": zero_similar,
            "next_action": "python scripts/update_similar_groups.py",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "search_status.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search Agent")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    SearchAgent().status()
