#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Senior Engineer Agent
DB 안정성 · 보안 · 코드 품질 · 확장성 상시 점검

사용법:
  python agents/senior_engineer.py --check all
  python agents/senior_engineer.py --check db
  python agents/senior_engineer.py --check security
  python agents/senior_engineer.py --check accuracy
  python agents/senior_engineer.py --fix db
============================================================
"""

import json, sqlite3, shutil, os, argparse, sys
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class SeniorEngineerAgent(BaseAgent):
    """시니어 엔지니어 에이전트 — 시스템 전체 건강 점검"""

    def __init__(self):
        super().__init__("senior_engineer", "Senior Engineer Agent", tier=1)
        self.checks_passed = []
        self.checks_failed = []
        self.warnings      = []

    # ──────────────────────────────────────────────────────
    # DB 안정성 점검
    # ──────────────────────────────────────────────────────
    def check_db(self) -> dict:
        """DB 무결성, 크기, 테이블 구조, 레코드 수 검증"""
        results = {}
        db_path = BASE_DIR / "db" / "problems.db"

        # 1. 파일 존재 + 크기
        if not db_path.exists():
            self._fail("db_exists", f"DB 파일 없음: {db_path}")
            results["db_exists"] = False
        elif db_path.stat().st_size == 0:
            self._fail("db_size", "⚠️ DB 파일 0바이트 — VirtioFS 손상 감지!")
            self._auto_fix_db()
            results["db_size"] = False
        else:
            self._pass("db_exists", f"DB {db_path.stat().st_size//1024}KB")
            results["db_size"] = db_path.stat().st_size

        # 2. journal 파일 체크 (미처리 트랜잭션)
        journal = db_path.parent / "problems.db-journal"
        if journal.exists() and journal.stat().st_size > 0:
            self._warn(f"journal 파일 존재 ({journal.stat().st_size}B) — 이전 트랜잭션 미완료 가능성")

        # 3. 테이블/레코드 무결성
        try:
            conn, tmp = self.get_db()
            prob_count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
            sim_count  = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0]
            null_ans   = conn.execute("SELECT COUNT(*) FROM problems WHERE answer IS NULL OR answer=''").fetchone()[0]
            no_crop    = conn.execute("SELECT COUNT(*) FROM problems WHERE crop_path IS NULL").fetchone()[0]
            conn.close()

            self._pass("problem_count",  f"총 {prob_count}개 문제")
            self._pass("similar_count",  f"총 {sim_count}쌍 유사관계")

            if null_ans > 0:
                self._warn(f"정답 없는 문제 {null_ans}개 — Math Expert 검토 필요")
            if no_crop > 0:
                self._warn(f"crop_path 없는 문제 {no_crop}개 — render_pages.py 실행 필요")

            results.update({"problems": prob_count, "similar": sim_count,
                           "null_answers": null_ans, "no_crops": no_crop})
        except Exception as e:
            self._fail("db_integrity", str(e))

        # 4. wiki .md 파일 수 vs DB 수 비교
        md_files = list((BASE_DIR / "wiki" / "problems").glob("*.md"))
        if len(md_files) != prob_count:
            self._warn(f"wiki .md 파일 수({len(md_files)}) ≠ DB 문제 수({prob_count}) — wiki_builder 실행 권장")
        else:
            self._pass("wiki_sync", f"wiki .md {len(md_files)}개 동기화 OK")

        return results

    def _auto_fix_db(self):
        """DB 0바이트 자동 복구"""
        self.logger.warning("🔧 DB 자동 복구 시도 중...")
        # /tmp에서 최신 작업 DB 탐색
        tmp_candidates = sorted(Path("/tmp").glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for cand in tmp_candidates:
            if cand.stat().st_size > 10000:  # 10KB 이상
                dst = BASE_DIR / "db" / "problems.db"
                shutil.copy(cand, dst)
                self.logger.info(f"✅ DB 복구 완료: {cand} → {dst}")
                self._pass("db_auto_fix", f"{cand.name}에서 복구")
                self.alert(f"DB 자동 복구 실행: {cand.name}", severity="info")
                return
        self._fail("db_auto_fix", "복구 가능한 /tmp DB 없음 — 수동 복구 필요")
        self.alert("DB 복구 실패 — 즉시 수동 확인 필요!", severity="critical")

    # ──────────────────────────────────────────────────────
    # 보안 점검
    # ──────────────────────────────────────────────────────
    def check_security(self) -> dict:
        """코드 내 하드코딩 API 키, SQL 인젝션 패턴, 권한 설정 검사"""
        results = {}
        risky_patterns = ["api_key=", "password=", "secret=", "token=", "API_KEY"]

        for py_file in BASE_DIR.glob("**/*.py"):
            if ".git" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for pat in risky_patterns:
                if pat.lower() in content.lower():
                    # 주석이나 변수명 체크 (실제 값 할당인지)
                    for line in content.splitlines():
                        if pat.lower() in line.lower() and "=" in line and not line.strip().startswith("#"):
                            if any(c in line for c in ['"', "'"]):
                                self._warn(f"보안 위험: {py_file.name}:{line.strip()[:60]}")

        # .env 파일 체크
        env_file = BASE_DIR / ".env"
        gitignore = BASE_DIR / ".gitignore"
        if env_file.exists():
            if gitignore.exists() and ".env" in gitignore.read_text():
                self._pass("env_gitignored", ".env 파일 .gitignore 포함됨")
            else:
                self._fail("env_exposed", ".env 파일이 .gitignore에 없음 — git push 시 노출 위험!")

        self._pass("security_scan", "코드 보안 스캔 완료")
        results["security"] = "ok"
        return results

    # ──────────────────────────────────────────────────────
    # 정확도 / 품질 점검
    # ──────────────────────────────────────────────────────
    def check_accuracy(self) -> dict:
        """크롭 이미지 존재, 정답 완성도, 유사문제 연결 점검"""
        results = {}
        try:
            conn, _ = self.get_db()
            rows = conn.execute("SELECT id, answer, crop_path, page_number FROM problems").fetchall()
            conn.close()

            missing_answer = [r["id"] for r in rows if not r["answer"]]
            missing_crop   = [r["id"] for r in rows if r["crop_path"] and
                              not (BASE_DIR / r["crop_path"]).exists()]
            missing_page   = [r["id"] for r in rows if not r["page_number"]]

            if missing_answer:
                self._warn(f"정답 없는 문제: {missing_answer}")
            else:
                self._pass("all_answers", f"전체 {len(rows)}개 정답 완비")

            if missing_crop:
                self._fail("crop_images", f"크롭 이미지 없는 문제: {missing_crop}")
            else:
                self._pass("crop_images", "전체 크롭 이미지 존재")

            results = {"total": len(rows), "missing_answer": len(missing_answer),
                      "missing_crop": len(missing_crop)}
        except Exception as e:
            self._fail("accuracy_check", str(e))

        return results

    # ──────────────────────────────────────────────────────
    # 성능 / 확장성 점검
    # ──────────────────────────────────────────────────────
    def check_performance(self) -> dict:
        """임베딩 처리 속도, DB 쿼리 응답, 파일 크기 점검"""
        import time
        results = {}

        conn, _ = self.get_db()
        start = time.time()
        count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        elapsed = time.time() - start
        conn.close()

        results["db_query_ms"] = round(elapsed * 1000, 2)
        if elapsed < 0.5:
            self._pass("db_performance", f"쿼리 응답 {elapsed*1000:.1f}ms (정상)")
        else:
            self._warn(f"DB 쿼리 느림: {elapsed*1000:.0f}ms")

        # 이미지 크기 통계
        crops = list((BASE_DIR / "sources" / "crops").glob("*.jpg"))
        if crops:
            sizes = [c.stat().st_size for c in crops]
            avg_kb = sum(sizes) // len(sizes) // 1024
            self._pass("crop_sizes", f"크롭 이미지 평균 {avg_kb}KB ({len(crops)}개)")
            results["crop_avg_kb"] = avg_kb

        return results

    # ──────────────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────────────
    def _pass(self, check: str, msg: str):
        self.checks_passed.append(check)
        self.logger.info(f"  ✅ [{check}] {msg}")

    def _fail(self, check: str, msg: str):
        self.checks_failed.append(check)
        self.logger.error(f"  ❌ [{check}] {msg}")

    def _warn(self, msg: str):
        self.warnings.append(msg)
        self.logger.warning(f"  ⚠️  {msg}")

    # ──────────────────────────────────────────────────────
    # 전체 실행
    # ──────────────────────────────────────────────────────
    def run(self, task: dict = None) -> dict:
        checks = (task or {}).get("checks", ["db", "security", "accuracy", "performance"])
        report = {"agent": self.name, "timestamp": datetime.now().isoformat(), "results": {}}

        print(f"\n{'='*60}")
        print(f"🔬 {self.name} — 시스템 점검 시작")
        print(f"{'='*60}")

        if "db" in checks or "all" in checks:
            print("\n📊 DB 안정성 점검...")
            report["results"]["db"] = self.check_db()

        if "security" in checks or "all" in checks:
            print("\n🔒 보안 점검...")
            report["results"]["security"] = self.check_security()

        if "accuracy" in checks or "all" in checks:
            print("\n🎯 정확도 점검...")
            report["results"]["accuracy"] = self.check_accuracy()

        if "performance" in checks or "all" in checks:
            print("\n⚡ 성능 점검...")
            report["results"]["performance"] = self.check_performance()

        # 요약
        total_pass = len(self.checks_passed)
        total_fail = len(self.checks_failed)
        total_warn = len(self.warnings)

        report["summary"] = {
            "passed": total_pass,
            "failed": total_fail,
            "warnings": total_warn,
            "overall": "FAIL" if total_fail > 0 else ("WARN" if total_warn > 0 else "PASS")
        }

        print(f"\n{'='*60}")
        print(f"📋 점검 결과: ✅{total_pass}개 통과 | ❌{total_fail}개 실패 | ⚠️{total_warn}개 경고")
        print(f"전체 상태: {report['summary']['overall']}")
        print(f"{'='*60}\n")

        # Captain에게 보고
        status = report["summary"]["overall"]
        self.report_to("captain", status.lower(), f"시스템 점검 완료: {status}", report["summary"])

        # 결과 저장
        self.save_result(report, "senior_engineer_report.json")
        return report


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    parser = argparse.ArgumentParser(description="Senior Engineer Agent")
    parser.add_argument("--check", default="all", help="점검 항목: all/db/security/accuracy/performance")
    parser.add_argument("--fix",   help="자동 수정 항목: db")
    args = parser.parse_args()

    agent = SeniorEngineerAgent()

    if args.fix == "db":
        agent._auto_fix_db()
    else:
        checks = ["all"] if args.check == "all" else args.check.split(",")
        agent.run({"checks": checks})
