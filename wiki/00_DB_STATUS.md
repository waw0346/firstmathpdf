---
tags: [dashboard, db-status]
updated: 2026-06-11 15:59
---

# 📊 수학 위키 DB 현황 대시보드

> **마지막 동기화**: 2026-06-11 15:59
> **DB 파일**: `db/problems.db` (764 KB)
> **총 문제 수**: 276문제 | **유사문제 쌍**: 377쌍
> **이미지**: 276/276 연결됨

---

## 📅 연도별 현황

| 연도 | 문제 수 |
|------|---------|
| 2025 | 92 |
| 2026 | 184 |

## 📐 영역별 현황

| 영역 | 문제 수 |
|------|---------|
| 함수 | 119 |
| 기하 | 53 |
| 확률과통계 | 48 |
| 수와연산 | 26 |
| 수열 | 17 |
| 삼각함수 | 11 |
| 미적분 | 2 |

## 🎯 난이도별 현황

| 난이도 | 문제 수 |
|--------|---------|
| 🟡 중 | 78 |
| 🟠 중상 | 66 |
| 🔴 상 | 66 |
| 🟢 하 | 30 |
| ⭐ 최상 | 24 |
| 🔵 중하 | 12 |

## 📚 출처별 현황

| 출처 | 문제 수 |
|------|---------|
| 모의고사 | 184 |
| 수능 | 92 |

## 🎓 학년별 현황

| 학년 | 문제 수 |
|------|---------|
| 고3 | 276 |

---

## 🔍 Dataview 쿼리 (Obsidian Dataview 플러그인 필요)

### 최근 추가된 문제 10개

```dataview
TABLE title, difficulty, domain, topic, year
FROM "wiki/problems"
SORT created_at DESC
LIMIT 10
```

### 난이도 상 문제 목록

```dataview
TABLE title, topic, year, answer
FROM "wiki/problems"
WHERE difficulty = "상"
SORT year DESC
```

### 영역별 그룹

```dataview
TABLE rows.file.link, rows.difficulty, rows.year
FROM "wiki/problems"
GROUP BY domain
```

### 유사문제 있는 문제

```dataview
TABLE title, length(similar_ids) as "유사문제 수", topic
FROM "wiki/problems"
WHERE similar_ids
SORT length(similar_ids) DESC
LIMIT 20
```

---

*🤖 `scripts/obsidian_sync.py`로 자동 생성됨 — 2026-06-11 15:59*
