#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create Obsidian concept stub notes for unresolved concept wikilinks."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent.parent
CONCEPTS = BASE / "wiki" / "concepts"
REPORT = BASE / "logs" / "agents" / "obsidian_concept_stubs.json"
AUDIT_JSON = BASE / "logs" / "agents" / "obsidian_integration_audit.json"

SKIP_TARGETS = {"개념명", "전체 검수 시작하기"}
INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')


def safe_target(target: str) -> str | None:
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target or target in SKIP_TARGETS:
        return None
    if "${" in target or "}" in target or "/" in target:
        return None
    if INVALID_CHARS.search(target):
        return None
    return target


def load_missing_targets() -> list[str]:
    data = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    targets = []
    for item in data["markdown"]["missing_wiki_links"]:
        target = safe_target(item["target"])
        if target:
            targets.append(target)
    return sorted(set(targets))


def write_stub(name: str) -> bool:
    path = CONCEPTS / f"{name}.md"
    if path.exists():
        return False
    body = f"""---
tags: [concept, auto-stub]
concept: {name}
created: {datetime.now().strftime('%Y-%m-%d')}
---

# {name}

## 연결된 문제

```dataview
TABLE id, domain, topic, difficulty, final_grade
FROM "wiki/problems"
WHERE contains(file.outlinks, this.file.link)
SORT year DESC, problem_number ASC
```

## 운영 메모

- 원본문제, 원본정답, 원본해설은 이 노트에서 수정하지 않는다.
- 이 노트는 Obsidian 그래프와 백링크 연결을 위한 개념 스텁이다.
"""
    path.write_text(body, encoding="utf-8")
    return True


def main() -> None:
    CONCEPTS.mkdir(parents=True, exist_ok=True)
    targets = load_missing_targets()
    created = [name for name in targets if write_stub(name)]
    result = {
        "timestamp": datetime.now().isoformat(),
        "candidate_targets": len(targets),
        "created": created,
        "created_count": len(created),
        "policy": "concept stubs only; original problems, answers, and solutions are not modified",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
