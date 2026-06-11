#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit Obsidian integration without modifying problem text, answers, or solutions.

Checks:
  - Obsidian settings and required plugins.
  - Problem note frontmatter and crop_path consistency.
  - Markdown/wiki image links resolve to existing files.
  - Dataview code fences are balanced.
  - Dashboard/index files exist.
  - Source trace index has a row for every DB crop row.
"""

import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent.parent
WIKI = BASE / "wiki"
PROBLEMS = WIKI / "problems"
OBSIDIAN = BASE / ".obsidian"
DB_PATH = BASE / "db" / "problems.db"
REPORT_JSON = BASE / "logs" / "agents" / "obsidian_integration_audit.json"
REPORT_MD = WIKI / "00_OBSIDIAN_INTEGRATION_AUDIT.md"

REQUIRED_PLUGINS = {"dataview"}
IMPORTANT_NOTES = [
    "wiki/index.md",
    "wiki/00_VERIFY.md",
    "wiki/00_QUICK_VERIFY.md",
    "wiki/00_VISUAL_DASHBOARD.md",
    "wiki/00_KANBAN.md",
    "wiki/00_SOURCE_TRACE_INDEX.md",
    "wiki/00_CROP_PIPELINE_EMERGENCY_CHECKLIST.md",
]


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def frontmatter(text: str) -> dict:
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not match:
        return {}
    data = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def resolve_link(note: Path, target: str) -> tuple[bool, str]:
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    if "${" in target or "}" in target:
        return True, "dynamic"
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return True, "external"

    candidates = []
    if target.startswith("/"):
        candidates.append(BASE / target.lstrip("/"))
    else:
        candidates.append(BASE / target)
        candidates.append(note.parent / target)
        candidates.append(WIKI / target)
        candidates.append(BASE / "sources" / "crops" / target)

    for cand in candidates:
        if cand.exists():
            try:
                return True, str(cand.relative_to(BASE)).replace("\\", "/")
            except ValueError:
                return True, str(cand)
    return False, target


def find_image_links(text: str) -> list[str]:
    links = []
    links.extend(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text))
    links.extend(re.findall(r"!\[\[([^\]]+)\]\]", text))
    return links


def find_wiki_links(text: str) -> list[str]:
    return [m for m in re.findall(r"(?<!!)\[\[([^\]]+)\]\]", text)]


def strip_code(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


def audit_markdown_files() -> dict:
    md_files = sorted(WIKI.rglob("*.md"))
    md_by_stem = {p.stem for p in md_files}
    md_rel_no_ext = {str(p.relative_to(WIKI)).replace("\\", "/")[:-3] for p in md_files}
    missing_images = []
    missing_wiki_links = []
    dataview_files = 0
    dataview_unbalanced = []
    mojibake_candidates = []

    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        link_text = strip_code(text)
        if "```dataview" in text:
            dataview_files += 1
        fence_count = len(re.findall(r"```", text))
        if fence_count % 2 != 0:
            dataview_unbalanced.append(str(md.relative_to(BASE)).replace("\\", "/"))

        bad_chars = text.count("�") + text.count("?섑") + text.count("?꾪") + text.count("?몄")
        if bad_chars >= 3:
            mojibake_candidates.append(str(md.relative_to(BASE)).replace("\\", "/"))

        for link in find_image_links(link_text):
            ok, resolved = resolve_link(md, link)
            if not ok:
                missing_images.append(
                    {
                        "file": str(md.relative_to(BASE)).replace("\\", "/"),
                        "target": link,
                        "resolved": resolved,
                    }
                )

        for link in find_wiki_links(link_text):
            target = link.split("|", 1)[0].split("#", 1)[0].strip()
            if "${" in target or "}" in target:
                continue
            if not target:
                continue
            candidates = [
                BASE / f"{target}.md",
                BASE / target,
                WIKI / f"{target}.md",
                WIKI / target,
                md.parent / f"{target}.md",
                md.parent / target,
            ]
            if not any(c.exists() for c in candidates) and target not in md_by_stem and target not in md_rel_no_ext:
                missing_wiki_links.append(
                    {
                        "file": str(md.relative_to(BASE)).replace("\\", "/"),
                        "target": link,
                    }
                )

    return {
        "markdown_files": len(md_files),
        "dataview_files": dataview_files,
        "dataview_unbalanced": dataview_unbalanced,
        "missing_images": missing_images,
        "missing_wiki_links": missing_wiki_links,
        "mojibake_candidates": mojibake_candidates[:50],
        "mojibake_candidate_count": len(mojibake_candidates),
    }


def audit_problem_notes() -> dict:
    notes = sorted(PROBLEMS.glob("*.md"))
    missing_crop_field = []
    missing_crop_file = []
    markdown_root_image_links = []
    for note in notes:
        text = note.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        crop = fm.get("crop_path", "")
        rel_note = str(note.relative_to(BASE)).replace("\\", "/")
        if not crop:
            missing_crop_field.append(rel_note)
        else:
            crop_file = BASE / crop
            if not crop_file.exists():
                missing_crop_file.append({"file": rel_note, "crop_path": crop})
        for link in re.findall(r"!\[[^\]]*\]\((sources/crops/[^)]+)\)", text):
            markdown_root_image_links.append({"file": rel_note, "target": link})
    return {
        "problem_notes": len(notes),
        "missing_crop_field": missing_crop_field,
        "missing_crop_file": missing_crop_file,
        "markdown_root_image_link_count": len(markdown_root_image_links),
        "markdown_root_image_link_sample": markdown_root_image_links[:20],
    }


def audit_db_trace() -> dict:
    if not DB_PATH.exists():
        return {"db_exists": False}
    con = sqlite3.connect(DB_PATH)
    try:
        crop_rows = con.execute("SELECT COUNT(*) FROM problems WHERE crop_path IS NOT NULL AND crop_path!=''").fetchone()[0]
        trace_exists = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='problem_source_trace'"
        ).fetchone()[0]
        trace_rows = 0
        if trace_exists:
            trace_rows = con.execute("SELECT COUNT(*) FROM problem_source_trace").fetchone()[0]
        return {
            "db_exists": True,
            "db_crop_rows": crop_rows,
            "source_trace_table_exists": bool(trace_exists),
            "source_trace_rows": trace_rows,
            "source_trace_complete": bool(trace_exists and trace_rows >= crop_rows),
        }
    finally:
        con.close()


def audit() -> dict:
    app = read_json(OBSIDIAN / "app.json", {})
    community = set(read_json(OBSIDIAN / "community-plugins.json", []))
    plugins_dir = OBSIDIAN / "plugins"
    enabled_missing = sorted(REQUIRED_PLUGINS - community)
    installed_missing = sorted(p for p in REQUIRED_PLUGINS if not (plugins_dir / p).exists())
    important_missing = [p for p in IMPORTANT_NOTES if not (BASE / p).exists()]
    markdown = audit_markdown_files()
    problems = audit_problem_notes()
    db = audit_db_trace()

    blocking = []
    warnings = []
    if not OBSIDIAN.exists():
        blocking.append(".obsidian folder missing")
    if enabled_missing:
        blocking.append(f"required plugins not enabled: {enabled_missing}")
    if installed_missing:
        blocking.append(f"required plugins not installed: {installed_missing}")
    if markdown["missing_images"]:
        blocking.append(f"missing image links: {len(markdown['missing_images'])}")
    if problems["missing_crop_file"]:
        blocking.append(f"missing crop files: {len(problems['missing_crop_file'])}")
    if not db.get("source_trace_complete"):
        blocking.append("source trace index incomplete")
    if markdown["missing_wiki_links"]:
        warnings.append(f"missing wiki links: {len(markdown['missing_wiki_links'])}")
    if markdown["mojibake_candidate_count"]:
        warnings.append(f"possible mojibake files: {markdown['mojibake_candidate_count']}")
    if problems["markdown_root_image_link_count"]:
        warnings.append(
            "problem notes use markdown image paths; Obsidian attachment wikilinks are more reliable"
        )

    result = {
        "timestamp": datetime.now().isoformat(),
        "obsidian_exists": OBSIDIAN.exists(),
        "attachment_folder": app.get("attachmentFolderPath"),
        "attachment_folder_exists": (BASE / app.get("attachmentFolderPath", "")).exists(),
        "required_plugins_enabled_missing": enabled_missing,
        "required_plugins_installed_missing": installed_missing,
        "important_notes_missing": important_missing,
        "markdown": markdown,
        "problems": problems,
        "db_trace": db,
        "blocking": blocking,
        "warnings": warnings,
        "ok": not blocking,
        "policy": "audit only; original problems, answers, and solutions are not modified",
    }
    return result


def write_reports(result: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md = f"""---
tags: [obsidian, audit, integration]
---

# Obsidian 연동 점검

> 원본 문제, 원본 정답, 원본 해설은 변경하지 않는다. 이 문서는 Obsidian에서 링크, 이미지, Dataview, 대시보드가 작동 가능한지 점검한 결과이다.

## 요약

- 전체 상태: {"정상" if result["ok"] else "조치 필요"}
- Obsidian 설정 폴더: {result["obsidian_exists"]}
- 첨부 폴더: `{result["attachment_folder"]}` / 존재: {result["attachment_folder_exists"]}
- Dataview 활성 누락: {result["required_plugins_enabled_missing"]}
- Dataview 설치 누락: {result["required_plugins_installed_missing"]}
- Markdown 파일: {result["markdown"]["markdown_files"]}
- Dataview 포함 파일: {result["markdown"]["dataview_files"]}
- 문제 노트: {result["problems"]["problem_notes"]}
- 누락 이미지 링크: {len(result["markdown"]["missing_images"])}
- 누락 crop 파일: {len(result["problems"]["missing_crop_file"])}
- 원본 역추적 색인: {result["db_trace"].get("source_trace_rows", 0)} / {result["db_trace"].get("db_crop_rows", 0)}

## 차단 이슈

{chr(10).join(f"- {item}" for item in result["blocking"]) if result["blocking"] else "- 없음"}

## 경고

{chr(10).join(f"- {item}" for item in result["warnings"]) if result["warnings"] else "- 없음"}

## 권장 후속

- 문제 노트의 `![](sources/crops/...)` 이미지 링크는 현재 파일 존재 검사는 통과하지만, Obsidian 안정성을 위해 `![[파일명.jpg|700]]` 형식으로 변환하는 작업을 별도 계획으로 진행한다.
- 인코딩 깨짐 후보 문서는 문제/해설 원본과 분리해서 대시보드/전략 문서부터 복구한다.
- `python scripts/obsidian_integration_audit.py`를 QA smoke에 포함해 이후 Obsidian 연동 이상을 자동 감지한다.
"""
    REPORT_MD.write_text(md, encoding="utf-8")


def main() -> None:
    result = audit()
    write_reports(result)
    print(json.dumps(
        {
            "ok": result["ok"],
            "blocking": result["blocking"],
            "warnings": result["warnings"],
            "markdown_files": result["markdown"]["markdown_files"],
            "problem_notes": result["problems"]["problem_notes"],
            "missing_images": len(result["markdown"]["missing_images"]),
            "missing_crop_files": len(result["problems"]["missing_crop_file"]),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
