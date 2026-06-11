#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Math LLM Wiki — Base Agent
모든 에이전트가 상속받는 기반 클래스

공통 기능:
  - 메시지 발송/수신
  - 로그 기록
  - DB 접근 (VirtioFS 안전 패턴)
  - 상태 보고
============================================================
"""

import json, sqlite3, shutil, logging, tempfile
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

TMP_DIR = Path(tempfile.gettempdir())

BASE_DIR = Path(__file__).parent.parent
LOG_DIR  = BASE_DIR / "logs" / "agents"
DB_SRC   = BASE_DIR / "db" / "problems.db"
TASK_Q   = BASE_DIR / "db" / "task_queue.db"
SNAP_DIR = BASE_DIR / "db" / "snapshots"

LOG_DIR.mkdir(parents=True, exist_ok=True)


class BaseAgent:
    """모든 에이전트의 기반 클래스"""

    def __init__(self, agent_id: str, name: str, tier: int):
        self.agent_id  = agent_id
        self.name      = name
        self.tier      = tier
        self.started   = datetime.now().isoformat()
        self.log_path  = LOG_DIR / f"{agent_id}.log"

        # 로거 설정
        self.logger = logging.getLogger(agent_id)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(self.log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(f"[{name}] %(message)s"))
        self.logger.addHandler(ch)

        self.logger.info(f"에이전트 시작: {name} (tier {tier})")

    # ──────────────────────────────────────────────────────
    # DB 접근 (VirtioFS 안전 패턴)
    # ──────────────────────────────────────────────────────
    def get_db(self, db_path: Optional[Path] = None) -> tuple[sqlite3.Connection, Path]:
        """DB를 임시 폴더에 복사 후 반환 (Windows/Linux 호환)"""
        src = db_path or DB_SRC
        if not src.exists() or src.stat().st_size < 10_000:
            src = self._latest_valid_snapshot()
            if not src:
                raise RuntimeError("유효한 DB를 찾을 수 없습니다. 최신 스냅샷 복구가 필요합니다.")
            self.logger.warning(f"운영 DB 불량 감지, 스냅샷 사용: {src.name}")
        import uuid
        tmp = TMP_DIR / f"{self.agent_id}_{src.stem}_{uuid.uuid4().hex[:8]}.db"
        shutil.copy(src, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        return conn, tmp

    def save_db(self, tmp_path: Path, dst_path: Optional[Path] = None):
        """작업 완료 후 DB를 원위치로 복사"""
        dst = dst_path or DB_SRC
        if not tmp_path.exists() or tmp_path.stat().st_size < 10_000:
            raise RuntimeError(f"저장 취소: 유효하지 않은 DB 작업본({tmp_path})")
        shutil.copy(tmp_path, dst)
        self.logger.info(f"DB 저장: {tmp_path} → {dst}")

    def _latest_valid_snapshot(self) -> Optional[Path]:
        """문제 테이블이 살아 있는 최신 스냅샷 탐색"""
        if not SNAP_DIR.exists():
            return None
        candidates = sorted(SNAP_DIR.glob("snap_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for snap in candidates:
            if snap.stat().st_size < 10_000:
                continue
            try:
                conn = sqlite3.connect(snap)
                count = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
                conn.close()
                if count > 0:
                    return snap
            except Exception:
                continue
        return None

    # ──────────────────────────────────────────────────────
    # 메시지 시스템
    # ──────────────────────────────────────────────────────
    def send_message(self, to_agent: str, task_type: str,
                     payload: dict, priority: str = "medium") -> str:
        """다른 에이전트에게 메시지 발송"""
        msg_id = f"{self.agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        message = {
            "msg_id":     msg_id,
            "from_agent": self.agent_id,
            "to_agent":   to_agent,
            "task_type":  task_type,
            "payload":    payload,
            "priority":   priority,
            "timestamp":  datetime.now().isoformat(),
            "status":     "pending"
        }
        # 메시지 큐 파일에 저장
        queue_file = LOG_DIR / "message_queue.jsonl"
        with open(queue_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
            f.flush()

        self.logger.info(f"→ [{to_agent}] {task_type} (priority:{priority})")
        return msg_id

    def report_to(self, to_agent: str, status: str, summary: str, details: dict = None):
        """상위 에이전트에 결과 보고"""
        self.send_message(
            to_agent   = to_agent,
            task_type  = "report",
            payload    = {"status": status, "summary": summary, "details": details or {}},
            priority   = "high" if status == "error" else "medium"
        )

    def alert(self, message: str, severity: str = "warning"):
        """긴급 알림 발송 (captain + senior_engineer 동시)"""
        for target in ["captain", "senior_engineer"]:
            self.send_message(
                to_agent  = target,
                task_type = "alert",
                payload   = {"message": message, "severity": severity, "agent": self.agent_id},
                priority  = "critical"
            )
        self.logger.warning(f"🚨 ALERT [{severity}]: {message}")

    # ──────────────────────────────────────────────────────
    # 결과 저장
    # ──────────────────────────────────────────────────────
    def save_result(self, result: dict, filename: str = None):
        """에이전트 실행 결과를 JSON으로 저장"""
        fname = filename or f"{self.agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out   = LOG_DIR / fname
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.logger.info(f"결과 저장: {out}")
        return out

    # ──────────────────────────────────────────────────────
    # 추상 메서드 (서브클래스에서 구현)
    # ──────────────────────────────────────────────────────
    def run(self, task: dict) -> dict:
        """에이전트 실행 — 서브클래스에서 반드시 구현"""
        raise NotImplementedError(f"{self.name}: run() 미구현")

    def health_check(self) -> dict:
        """자체 상태 점검 — 서브클래스에서 구현 권장"""
        return {"agent": self.agent_id, "status": "ok", "timestamp": datetime.now().isoformat()}
