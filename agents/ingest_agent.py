#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingest Agent
새 PDF 후보와 인제스트 준비 상태를 점검합니다.
"""

import argparse, json, shutil, sqlite3, subprocess, sys, tempfile
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent


def norm_rel(path: str) -> str:
    return str(path).replace("\\", "/")


class IngestAgent(BaseAgent):
    def __init__(self):
        super().__init__("ingest", "Ingest Agent", tier=2)

    FILE_MAP = {
        ("2025", 10, "NA"): {
            "file_id": "H2510-NA",
            "q": "sources/2025/2025 10월 고3 전국연합학력평가 수학 문제지.pdf",
            "a": "sources/2025/2025 10월 고3 전국연합학력평가 수학 정답 및 해설.pdf",
            "s": "sources/2025/2025 10월 고3 전국연합학력평가 수학 정답 및 해설.pdf",
        },
        ("2025", 11, "SU"): {
            "file_id": "H2511-SU",
            "q": "sources/2025/2025수능_수학문제.pdf",
            "a": "sources/2025/2025수능_수학문제정답.pdf",
            "s": "",
        },
        ("2026", 5, "NA"): {
            "file_id": "H2605-NA",
            "q": "sources/2026/2026 5월 고3 전국연합학력평가 수학 문제.pdf",
            "a": "sources/2026/2026 5월 고3 전국연합학력평가 수학 해설.pdf",
            "s": "sources/2026/2026 5월 고3 전국연합학력평가 수학 해설.pdf",
        },
        ("2026", 6, "NA"): {
            "file_id": "H2606-NA",
            "q": "sources/2026/2026 대학수학능력시험 6월 모의평가 수학 문제지.pdf",
            "a": "sources/2026/2026 대학수학능력시험 6월 모의평가 수학 해설지(ebs).pdf",
            "s": "sources/2026/2026 대학수학능력시험 6월 모의평가 수학 해설지(ebs).pdf",
        },
        ("2026", 9, "NA"): {
            "file_id": "H2609-NA",
            "q": "sources/2026/2026학년도 대학수학능력시험 9월 모의평가 수학 문제 (2).pdf",
            "a": "sources/2026/2026 대학수학능력시험 9월 모의평가 수학 해설지(EBS) (2).pdf",
            "s": "sources/2026/2026 대학수학능력시험 9월 모의평가 수학 해설지(EBS) (2).pdf",
        },
        ("2026", 11, "SU"): {
            "file_id": "H2611-SU",
            "q": "sources/2026/2026수능_수학문제.pdf",
            "a": "sources/2026/2026 대학수학능력시험 수학 해설지(EBS).pdf",
            "s": "sources/2026/2026 대학수학능력시험 수학 해설지(EBS).pdf",
        },
    }

    def _registered_problem_pdfs(self, conn) -> set:
        registered = set()
        try:
            registered.update(
                norm_rel(r[0]) for r in conn.execute(
                    "SELECT file_path_q FROM file_registry WHERE file_path_q IS NOT NULL AND file_path_q!=''"
                )
            )
        except Exception:
            pass
        # DB에 문제가 이미 존재하면 해당 시험의 원본 PDF는 처리 완료로 본다.
        for row in conn.execute("""
            SELECT CAST(year AS TEXT) AS year, month, source_code, COUNT(*) AS cnt
            FROM problems
            WHERE year IS NOT NULL AND month IS NOT NULL AND source_code IS NOT NULL
            GROUP BY year, month, source_code
        """):
            meta = self.FILE_MAP.get((row["year"], row["month"], row["source_code"]))
            if meta and row["cnt"] > 0:
                registered.add(norm_rel(meta["q"]))
        return registered

    def status(self) -> dict:
        conn, _ = self.get_db()
        registered = self._registered_problem_pdfs(conn)
        conn.close()
        pdfs = sorted((BASE_DIR / "sources").rglob("*.pdf"))
        candidates = [
            str(p.relative_to(BASE_DIR)) for p in pdfs
            if norm_rel(str(p.relative_to(BASE_DIR))) not in registered and "정답" not in p.name and "해설" not in p.name
        ]
        result = {"timestamp": datetime.now().isoformat(), "pdf_count": len(pdfs), "unregistered_problem_pdfs": candidates}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "ingest_status.json")
        return result

    def reconcile_registry(self) -> dict:
        """이미 DB에 반영된 시험 PDF를 file_registry에 등록합니다."""
        tmp = Path(tempfile.gettempdir()) / "ingest_registry_reconcile.db"
        shutil.copy(BASE_DIR / "db" / "problems.db", tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        existing = {
            r["file_id"] for r in cur.execute(
                "SELECT file_id FROM file_registry WHERE file_id IS NOT NULL AND file_id!=''"
            )
        }
        inserted = []
        updated = []
        for row in cur.execute("""
            SELECT CAST(year AS TEXT) AS year, month, source_code, COUNT(*) AS cnt
            FROM problems
            WHERE year IS NOT NULL AND month IS NOT NULL AND source_code IS NOT NULL
            GROUP BY year, month, source_code
            ORDER BY year, month, source_code
        """).fetchall():
            meta = self.FILE_MAP.get((row["year"], row["month"], row["source_code"]))
            if not meta:
                continue
            if meta["file_id"] in existing:
                current = cur.execute("""
                    SELECT file_path_q, file_path_a, file_path_s
                    FROM file_registry
                    WHERE file_id = ?
                """, (meta["file_id"],)).fetchone()
                if current and (
                    (meta["q"] and not current["file_path_q"]) or
                    (meta["a"] and not current["file_path_a"]) or
                    (meta["s"] and not current["file_path_s"])
                ):
                    cur.execute("""
                        UPDATE file_registry
                        SET file_path_q = CASE WHEN file_path_q IS NULL OR file_path_q='' THEN ? ELSE file_path_q END,
                            file_path_a = CASE WHEN file_path_a IS NULL OR file_path_a='' THEN ? ELSE file_path_a END,
                            file_path_s = CASE WHEN file_path_s IS NULL OR file_path_s='' THEN ? ELSE file_path_s END
                        WHERE file_id = ?
                    """, (meta["q"], meta["a"], meta["s"], meta["file_id"]))
                    updated.append(meta["file_id"])
                continue
            cur.execute("""
                INSERT INTO file_registry
                (file_id, file_type, year, month, grade, source_code,
                 file_path_q, file_path_a, file_path_s, created_at)
                VALUES (?, 'exam', ?, ?, 'H3', ?, ?, ?, ?, datetime('now'))
            """, (
                meta["file_id"], int(row["year"]), row["month"], row["source_code"],
                meta["q"], meta["a"], meta["s"],
            ))
            inserted.append(meta["file_id"])
        conn.commit()
        conn.close()
        shutil.copy(tmp, BASE_DIR / "db" / "problems.db")
        result = {"inserted": inserted, "updated": updated, "count": len(inserted) + len(updated)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "ingest_registry_reconcile.json")
        return result

    def source_trace(self, apply: bool = True) -> dict:
        """원본 역추적 색인을 실행합니다.

        문제 본문, 정답, 기존 해설은 변경하지 않고 별도 색인만 생성/검증합니다.
        """
        cmd = [sys.executable, "scripts/source_trace_index.py"]
        if apply:
            cmd.append("--apply")
        run = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        payload = {
            "timestamp": datetime.now().isoformat(),
            "command": " ".join(cmd),
            "returncode": run.returncode,
            "ok": run.returncode == 0,
            "stdout": run.stdout[-4000:],
            "stderr": run.stderr[-4000:],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        self.save_result(payload, "ingest_source_trace.json")
        return payload

    def run(self, task: dict = None) -> dict:
        if (task or {}).get("action") == "reconcile":
            return self.reconcile_registry()
        if (task or {}).get("action") == "source_trace":
            return self.source_trace(apply=(task or {}).get("apply", True))
        return self.status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Agent")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reconcile-registry", action="store_true")
    parser.add_argument("--source-trace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    agent = IngestAgent()
    if args.reconcile_registry:
        agent.reconcile_registry()
    elif args.source_trace:
        agent.source_trace(apply=not args.dry_run)
    else:
        agent.status()
