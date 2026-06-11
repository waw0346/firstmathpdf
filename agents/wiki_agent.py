#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wiki Agent
DB와 Obsidian 문제 노트 수의 정합성을 점검합니다.
"""

import argparse, json
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent


class WikiAgent(BaseAgent):
    def __init__(self):
        super().__init__("wiki", "Wiki Agent", tier=2)

    def status(self) -> dict:
        conn, _ = self.get_db()
        db_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        conn.close()
        md_count = len(list((BASE_DIR / "wiki" / "problems").glob("*.md")))
        result = {
            "timestamp": datetime.now().isoformat(),
            "db_problem_count": db_count,
            "wiki_problem_notes": md_count,
            "in_sync": db_count == md_count,
            "next_action": "python scripts/obsidian_sync.py" if db_count != md_count else "ok",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "wiki_status.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wiki Agent")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    WikiAgent().status()
