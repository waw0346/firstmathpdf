#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrity Guard Agent
원본문제·원본정답·원본해설 파일의 불변성을 감시합니다.

절대 원칙:
  - sources/ 아래 PDF 원본은 변형하지 않는다.
  - 기존 공식 해설은 변형하지 않는다.
  - 추가 해설은 별도 필드/노트/테이블에만 생성한다.

사용법:
  python agents/integrity_guard_agent.py --baseline
  python agents/integrity_guard_agent.py --audit
"""

import argparse, hashlib, json, sys
from pathlib import Path
from datetime import datetime
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent
MANIFEST = BASE_DIR / "db" / "source_integrity_manifest.json"
PROTECTED_EXTS = {".pdf"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class IntegrityGuardAgent(BaseAgent):
    def __init__(self):
        super().__init__("integrity_guard", "Integrity Guard Agent", tier=1)

    def protected_files(self) -> list[Path]:
        files = []
        for path in (BASE_DIR / "sources").rglob("*"):
            if path.is_file() and path.suffix.lower() in PROTECTED_EXTS:
                files.append(path)
        return sorted(files)

    @staticmethod
    def sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def snapshot(self) -> dict:
        items = {}
        for path in self.protected_files():
            rel = str(path.relative_to(BASE_DIR)).replace("\\", "/")
            meta = {
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
                "protected_type": self.classify(path.name),
            }
            try:
                meta["sha256"] = self.sha256(path)
                meta["readable"] = True
            except PermissionError as exc:
                meta["sha256"] = None
                meta["readable"] = False
                meta["error"] = f"permission_denied: {exc}"
            items[rel] = meta
        return {
            "policy": "원본문제·원본정답·원본해설은 변형 금지. 추가 해설만 별도 생성 가능.",
            "generated_at": datetime.now().isoformat(),
            "files": items,
        }

    @staticmethod
    def classify(name: str) -> str:
        if "해설" in name:
            return "original_solution"
        if "정답" in name:
            return "original_answer"
        return "original_problem"

    def write_baseline(self) -> dict:
        data = self.snapshot()
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {"status": "baseline_written", "files": len(data["files"]), "manifest": str(MANIFEST)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.report_to("captain", "completed", "원본 무결성 기준선 생성", result)
        return result

    def audit(self) -> dict:
        if not MANIFEST.exists():
            result = {"status": "missing_baseline", "action": "run --baseline first"}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result
        baseline = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current = self.snapshot()
        old = baseline.get("files", {})
        new = current.get("files", {})
        changed, missing, added = [], [], []
        for rel, meta in old.items():
            if rel not in new:
                missing.append(rel)
            elif meta.get("sha256") and new[rel].get("sha256") and new[rel]["sha256"] != meta["sha256"]:
                changed.append({"file": rel, "type": meta.get("protected_type", "unknown")})
            elif meta.get("sha256") is None and (
                new[rel].get("size") != meta.get("size") or new[rel].get("mtime") != meta.get("mtime")
            ):
                changed.append({"file": rel, "type": meta.get("protected_type", "unknown"), "reason": "unreadable_file_stat_changed"})
        for rel in new:
            if rel not in old:
                added.append(rel)
        status = "FAIL" if changed or missing else "PASS"
        result = {
            "status": status,
            "checked": len(new),
            "changed_protected_files": changed,
            "missing_protected_files": missing,
            "new_protected_files": added,
            "note": "새 원본 파일 추가는 허용된다. 기준선 반영 전까지 added로 표시한다.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "integrity_guard_audit.json")
        if status == "FAIL":
            self.alert("원본문제/원본해설 변형 감지", severity="critical")
        return result

    def run(self, task: dict = None) -> dict:
        if (task or {}).get("action") == "baseline":
            return self.write_baseline()
        return self.audit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integrity Guard Agent")
    parser.add_argument("--baseline", action="store_true", help="현재 원본 파일 해시 기준선 생성")
    parser.add_argument("--audit", action="store_true", help="원본 파일 무결성 점검")
    args = parser.parse_args()
    agent = IntegrityGuardAgent()
    if args.baseline:
        agent.write_baseline()
    else:
        agent.audit()
