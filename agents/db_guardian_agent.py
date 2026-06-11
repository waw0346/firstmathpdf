#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DB Guardian Agent
운영 DB 생존성, 스냅샷, 복구 기준점을 관리합니다.

사용법:
  python agents/db_guardian_agent.py --status
  python agents/db_guardian_agent.py --restore-latest
"""

import argparse, json, shutil, sqlite3
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "db" / "problems.db"
SNAP_DIR = BASE_DIR / "db" / "snapshots"


class DBGuardianAgent(BaseAgent):
    def __init__(self):
        super().__init__("db_guardian", "DB Guardian Agent", tier=1)

    def _db_info(self, path: Path) -> dict:
        info = {"path": str(path), "name": path.name, "size": path.stat().st_size if path.exists() else 0}
        try:
            conn = sqlite3.connect(path)
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            info["tables"] = len(tables)
            info["problems"] = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0] if "problems" in tables else 0
            info["similar"] = conn.execute("SELECT COUNT(*) FROM similar_problems").fetchone()[0] if "similar_problems" in tables else 0
            conn.close()
            info["valid"] = info["problems"] > 0
        except Exception as exc:
            info["valid"] = False
            info["error"] = str(exc)
        return info

    def latest_valid_snapshot(self) -> Path | None:
        snapshots = sorted(SNAP_DIR.glob("snap_*.db"), key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)
        for snap in snapshots:
            if self._db_info(snap).get("valid"):
                return snap
        return None

    def status(self) -> dict:
        current = self._db_info(DB_PATH)
        latest = self.latest_valid_snapshot()
        latest_info = self._db_info(latest) if latest else None
        result = {
            "timestamp": datetime.now().isoformat(),
            "current_db": current,
            "latest_valid_snapshot": latest_info,
            "recommendation": "ok" if current.get("valid") else "restore_latest",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "db_guardian_status.json")
        return result

    def restore_latest(self) -> dict:
        latest = self.latest_valid_snapshot()
        if not latest:
            raise RuntimeError("복구 가능한 유효 스냅샷이 없습니다.")
        before = DB_PATH.with_name(f"problems_BEFORE_DB_GUARDIAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        if DB_PATH.exists():
            shutil.copy(DB_PATH, before)
        shutil.copy(latest, DB_PATH)
        result = {"restored_from": latest.name, "backup_before": before.name, "db": self._db_info(DB_PATH)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.report_to("captain", "completed", f"DB 복구 완료: {latest.name}", result)
        return result

    def run(self, task: dict = None) -> dict:
        if (task or {}).get("action") == "restore_latest":
            return self.restore_latest()
        return self.status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DB Guardian Agent")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--restore-latest", action="store_true")
    args = parser.parse_args()
    agent = DBGuardianAgent()
    if args.restore_latest:
        agent.restore_latest()
    else:
        agent.status()
