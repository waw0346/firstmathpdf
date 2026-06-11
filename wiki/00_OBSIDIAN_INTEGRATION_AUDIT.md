---
tags: [obsidian, audit, integration]
---

# Obsidian 연동 점검

> 원본 문제, 원본 정답, 원본 해설은 변경하지 않는다. 이 문서는 Obsidian에서 링크, 이미지, Dataview, 대시보드가 작동 가능한지 점검한 결과이다.

## 요약

- 전체 상태: 정상
- Obsidian 설정 폴더: True
- 첨부 폴더: `sources/crops` / 존재: True
- Dataview 활성 누락: []
- Dataview 설치 누락: []
- Markdown 파일: 810
- Dataview 포함 파일: 85
- 문제 노트: 276
- 누락 이미지 링크: 0
- 누락 crop 파일: 0
- 원본 역추적 색인: 276 / 276

## 차단 이슈

- 없음

## 경고

- problem notes use markdown image paths; Obsidian attachment wikilinks are more reliable

## 권장 후속

- 문제 노트의 `![](sources/crops/...)` 이미지 링크는 현재 파일 존재 검사는 통과하지만, Obsidian 안정성을 위해 `![[파일명.jpg|700]]` 형식으로 변환하는 작업을 별도 계획으로 진행한다.
- 인코딩 깨짐 후보 문서는 문제/해설 원본과 분리해서 대시보드/전략 문서부터 복구한다.
- `python scripts/obsidian_integration_audit.py`를 QA smoke에 포함해 이후 Obsidian 연동 이상을 자동 감지한다.
