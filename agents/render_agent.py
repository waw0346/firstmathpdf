#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render Agent
크롭 이미지 존재성과 크기 이상을 점검합니다.
"""

import argparse, json
from pathlib import Path
from datetime import datetime
from PIL import Image
from base_agent import BaseAgent

BASE_DIR = Path(__file__).parent.parent


class RenderAgent(BaseAgent):
    def __init__(self):
        super().__init__("render", "Render Agent", tier=2)

    def status(self) -> dict:
        conn, _ = self.get_db()
        rows = [dict(r) for r in conn.execute("SELECT id, crop_path FROM problems WHERE crop_path IS NOT NULL AND crop_path!=''").fetchall()]
        conn.close()
        missing, abnormal = [], []
        for row in rows:
            path = BASE_DIR / row["crop_path"]
            if not path.exists():
                missing.append(row["id"])
                continue
            try:
                img = Image.open(path)
                w, h = img.size
                if h < 100 or h > 4500 or w > 2200:
                    abnormal.append({"id": row["id"], "size": [w, h]})
            except Exception:
                abnormal.append({"id": row["id"], "size": "read_error"})
        result = {"timestamp": datetime.now().isoformat(), "checked": len(rows), "missing": missing, "abnormal": abnormal[:50]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        self.save_result(result, "render_status.json")
        return result

    def run(self, task: dict = None) -> dict:
        return self.status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render Agent")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    RenderAgent().status()
