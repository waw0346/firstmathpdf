#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification Agent
이미지/정답/해설/서명 3단계 검수 진행률을 관리합니다.
"""

import argparse, json
from datetime import datetime
from base_agent import BaseAgent


class VerificationAgent(BaseAgent):
    def __init__(self):
        super().__init__("verification", "Verification Agent", tier=2)

    def status(self) -> dict:
        conn, _ = self.get_db()
        total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        metrics = {
            "stage1_img_pass": "stage1_img='pass'",
            "stage2_ans_pass": "stage2_ans='pass'",
            "stage3_sol_pass": "stage3_sol='pass'",
            "final_grade_A": "final_grade='A'",
            "final_grade_B": "final_grade='B'",
            "sign_tr_done": "sign_tr_final IS NOT NULL AND sign_tr_final!=''",
            "sign_cp_done": "sign_cp_final IS NOT NULL AND sign_cp_final!=''",
        }
        counts = {}
        for key, where in metrics.items():
            counts[key] = conn.execute(f"SELECT COUNT(*) FROM problems WHERE {where}").fetchone()[0]
        conn.close()
        result = {"timestamp": datetime.now().isoformat(), "total": total, "counts": counts}
        if counts["stage1_img_pass"] < total or counts["stage2_ans_pass"] < total:
            result["next_focus"] = "stage1/stage2 pending 문제 정리"
        elif counts["stage3_sol_pass"] < total:
            result["next_focus"] = "stage3 해설 입력 및 Math Expert 검수"
        elif counts["sign_tr_done"] < total or counts["sign_cp_done"] < total:
            result["next_focus"] = "tr/cp 최종 서명"
        else:
            result["next_focus"] = "A등급 완료 상태 유지"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "verification_status.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verification Agent")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    VerificationAgent().status()
