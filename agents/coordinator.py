#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Captain Agent — 총괄 오케스트레이터 (coordinator.py)
모든 에이전트를 조율하고 전체 프로젝트 목표를 유지

사용법:
  python agents/coordinator.py --status        # 전체 시스템 현황
  python agents/coordinator.py --run all       # 전체 파이프라인 실행
  python agents/coordinator.py --run ingest    # 인제스트만
  python agents/coordinator.py --run check     # 시스템 점검만
  python agents/coordinator.py --run test      # 에이전트 테스트
  python agents/coordinator.py --report        # 종합 보고서
============================================================
"""

import json, sys, argparse, subprocess
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


_AGENT_TIMEOUTS = {
    "embed":            1800,
    "embed_simple":     1800,
    "render_agent":      600,
    "render_pages":      600,
    "ingest_agent":      600,
    "senior_engineer":   300,
    "math_expert_agent": 300,
    "verification_agent": 300,
}
_DEFAULT_TIMEOUT = 120


class CaptainAgent(BaseAgent):
    """총괄 Captain 에이전트"""

    def __init__(self):
        super().__init__("captain", "🎖️ Captain Agent", tier=1)
        self.session_start = datetime.now().isoformat()
        self.task_log = []

    # ──────────────────────────────────────────────────────
    # 에이전트 실행기
    # ──────────────────────────────────────────────────────
    def run_agent(self, agent_name: str, args_list: list, desc: str = "") -> dict:
        """특정 에이전트 subprocess 실행"""
        script = BASE_DIR / "agents" / f"{agent_name}.py"
        if not script.exists():
            self.logger.warning(f"에이전트 스크립트 없음: {script}")
            return {"status": "missing", "agent": agent_name}

        timeout = _AGENT_TIMEOUTS.get(agent_name, _DEFAULT_TIMEOUT)
        self.logger.info(f"▶ [{agent_name}] {desc or ' '.join(args_list)} (timeout:{timeout}s)")
        cmd = [sys.executable, str(script)] + args_list

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=BASE_DIR, timeout=timeout
            )
            status = "ok" if result.returncode == 0 else "error"
            if result.stdout:
                print(result.stdout)
            if result.stderr and result.returncode != 0:
                self.logger.error(f"  [{agent_name}] stderr: {result.stderr[:300]}")

            task = {"agent": agent_name, "desc": desc, "status": status,
                   "timestamp": datetime.now().isoformat()}
            self.task_log.append(task)
            return task

        except subprocess.TimeoutExpired:
            self.logger.error(f"  [{agent_name}] 타임아웃 ({timeout}s)")
            return {"agent": agent_name, "status": "timeout"}
        except Exception as e:
            self.logger.error(f"  [{agent_name}] 실행 오류: {e}")
            return {"agent": agent_name, "status": "error", "error": str(e)}

    # ──────────────────────────────────────────────────────
    # 파이프라인
    # ──────────────────────────────────────────────────────
    def pipeline_check(self) -> dict:
        """시스템 상태 점검 파이프라인"""
        print(f"\n{'='*60}")
        print(f"🔬 PIPELINE: 시스템 점검")
        print(f"{'='*60}")

        results = {}
        results["senior_check"] = self.run_agent(
            "senior_engineer", ["--check", "all"], "전체 시스템 점검"
        )
        return results

    def pipeline_test_agents(self) -> dict:
        """3대 도메인 에이전트 테스트 파이프라인"""
        print(f"\n{'='*60}")
        print(f"🧪 PIPELINE: 에이전트 테스트")
        print(f"{'='*60}")

        results = {}

        # 1. Math Expert: 전체 정답 검증
        print("\n[1/3] Math Expert Agent — 정답 검증...")
        results["math_verify"] = self.run_agent(
            "math_expert_agent", ["--verify-all"], "전체 정답 검증"
        )

        # 2. Teacher: 수업 계획 생성
        print("\n[2/3] Teacher Agent — 수업 계획 생성...")
        results["teacher_plan"] = self.run_agent(
            "teacher_agent", ["--plan", "--domain", "함수", "--grade", "고3", "--count", "5"],
            "함수 고3 수업 계획"
        )

        # 3. Student: 풀이 시뮬레이션
        print("\n[3/3] Student Agent — 풀이 시뮬레이션...")
        results["student_sim_mid"] = self.run_agent(
            "student_agent", ["--simulate", "--level", "중", "--count", "5"],
            "중급 학생 시뮬레이션 (5문제)"
        )
        results["student_sim_high"] = self.run_agent(
            "student_agent", ["--simulate", "--level", "상", "--count", "5"],
            "상급 학생 시뮬레이션 (5문제)"
        )

        return results

    def pipeline_full(self) -> dict:
        """전체 파이프라인: 점검 → 임베딩 → 위키 → 테스트"""
        print(f"\n{'#'*60}")
        print(f"🎖️ CAPTAIN AGENT — 전체 파이프라인 시작")
        print(f"{'#'*60}")

        all_results = {}

        # Step 1: 시스템 점검
        all_results["step1_check"] = self.pipeline_check()

        # Step 2: 유사도 재계산
        print(f"\n{'='*60}")
        print(f"🔗 PIPELINE: 유사문제 재계산")
        print(f"{'='*60}")
        all_results["step2_embed"] = self.run_agent(
            "../scripts/embed_simple", ["--build"], "TF-IDF 유사도 재계산"
        )

        # Step 3: 에이전트 테스트
        all_results["step3_test"] = self.pipeline_test_agents()

        return all_results

    # ──────────────────────────────────────────────────────
    # 시스템 현황 조회
    # ──────────────────────────────────────────────────────
    def system_status(self) -> dict:
        """전체 시스템 현황 조회"""
        print(f"\n{'='*60}")
        print(f"📊 시스템 현황 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")

        status = {}

        # DB 상태
        db_path = BASE_DIR / "db" / "problems.db"
        if db_path.exists() and db_path.stat().st_size > 0:
            try:
                from base_agent import BaseAgent
                tmp_agent = BaseAgent("tmp", "tmp", 0)
                conn, _ = tmp_agent.get_db()
                prob_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
                sim_count  = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]
                conn.close()
                status["db"] = {"ok": True, "problems": prob_count, "similar_pairs": sim_count}
                print(f"  ✅ DB: {prob_count}개 문제, {sim_count}쌍 유사관계")
            except Exception as e:
                status["db"] = {"ok": False, "error": str(e)}
                print(f"  ❌ DB 오류: {e}")
        else:
            status["db"] = {"ok": False, "size": db_path.stat().st_size if db_path.exists() else -1}
            print(f"  ❌ DB 불량 (0바이트)")

        # 크롭 이미지
        crops = list((BASE_DIR / "sources" / "crops").glob("*.jpg"))
        status["crops"] = len(crops)
        print(f"  {'✅' if crops else '⚠️'} 크롭 이미지: {len(crops)}개")

        # Wiki .md 파일
        wiki_mds = list((BASE_DIR / "wiki" / "problems").glob("*.md"))
        status["wiki_mds"] = len(wiki_mds)
        print(f"  {'✅' if wiki_mds else '⚠️'} Wiki .md: {len(wiki_mds)}개")

        # 에이전트 스크립트
        agent_scripts = list((BASE_DIR / "agents").glob("*.py"))
        status["agent_scripts"] = len(agent_scripts)
        print(f"  {'✅' if agent_scripts else '⚠️'} 에이전트 스크립트: {len(agent_scripts)}개")

        # 학생 데이터
        students = list((BASE_DIR / "data" / "students").glob("*.json"))
        status["students"] = len(students)
        print(f"  📝 학생 데이터: {len(students)}명")

        # 최근 로그
        msg_queue = BASE_DIR / "logs" / "agents" / "message_queue.jsonl"
        if msg_queue.exists():
            lines = msg_queue.read_text(encoding="utf-8").strip().splitlines()
            status["messages_queued"] = len(lines)
            print(f"  📨 메시지 큐: {len(lines)}건")

        print(f"{'='*60}")
        return status

    # ──────────────────────────────────────────────────────
    # 종합 보고서
    # ──────────────────────────────────────────────────────
    def generate_report(self) -> Path:
        """종합 상태 보고서 생성"""
        status  = self.system_status()
        report  = {
            "session":  self.session_start,
            "generated": datetime.now().isoformat(),
            "status":    status,
            "task_log":  self.task_log,
            "summary":   {
                "health": "OK" if status.get("db", {}).get("ok") else "FAIL",
                "problems": status.get("db", {}).get("problems", 0),
                "crops":    status.get("crops", 0),
            }
        }
        out = BASE_DIR / "logs" / "agents" / "captain_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ 보고서 저장: {out}")
        return out

    def run(self, task: dict = None) -> dict:
        action = (task or {}).get("action", "status")
        if action == "status":  return self.system_status()
        if action == "check":   return self.pipeline_check()
        if action == "test":    return self.pipeline_test_agents()
        if action == "all":     return self.pipeline_full()
        if action == "report":
            self.generate_report()
            return {}
        return {}


# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Captain Agent — 총괄 오케스트레이터")
    parser.add_argument("--status", action="store_true", help="시스템 현황")
    parser.add_argument("--run",    help="파이프라인: all/check/test")
    parser.add_argument("--report", action="store_true", help="종합 보고서")
    args = parser.parse_args()

    agent = CaptainAgent()

    if args.status:
        agent.system_status()
    elif args.run:
        agent.run({"action": args.run})
    elif args.report:
        agent.generate_report()
    else:
        agent.system_status()
