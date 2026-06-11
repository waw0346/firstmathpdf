#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Concept Tagging Agent
개념 태깅 진행률과 우선 태깅 대상을 산출합니다.
"""

import argparse, json
from datetime import datetime
from base_agent import BaseAgent


class ConceptTaggingAgent(BaseAgent):
    def __init__(self):
        super().__init__("concept_tagger", "Concept Tagging Agent", tier=3)

    def plan(self, limit: int = 20) -> dict:
        conn, _ = self.get_db()
        total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        tagged = conn.execute("SELECT COUNT(*) FROM problems WHERE concept_tags IS NOT NULL AND concept_tags!=''").fetchone()[0]
        topics = [dict(r) for r in conn.execute("""
            SELECT topic, domain, COUNT(*) AS count
            FROM problems
            WHERE concept_tags IS NULL OR concept_tags=''
            GROUP BY topic, domain
            ORDER BY count DESC
            LIMIT ?
        """, (limit,)).fetchall()]
        conn.close()
        result = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "tagged": tagged,
            "untagged": total - tagged,
            "priority_topics": topics,
            "rule": "문제별 concept_tags는 2~5개로 제한하고, concepts 노트와 링크한다.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "concept_tagging_plan.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.plan((task or {}).get("limit", 20))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concept Tagging Agent")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    ConceptTaggingAgent().plan(args.limit)
