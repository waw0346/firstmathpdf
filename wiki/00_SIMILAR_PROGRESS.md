---
tags: [similar, progress, schedule]
updated: 2026-06-05
---

# 📅 유사문제 시스템 — 실행 일정 & 점검판

> 원본 이미지 불변 원칙 | raw_text AI 100% 전까지 보류
> **방법**: 이미지+메타데이터+이미지임베딩+선생님태깅

---

## 📊 현재 진행 상황

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;
const tagged = pp.filter(p => p.concept_tags && p.concept_tags !== "").length;
const grouped = pp.filter(p => p.similar_group && p.similar_group !== "").length;
const hasSimilar = pp.filter(p => p.similar_ids && p.similar_ids.length > 0).length;

dv.paragraph(`
| 항목 | 현재 | 목표 |
|------|------|------|
| 총 문제 | ${total}개 | - |
| 유사그룹 배정 | ${grouped}개 (${Math.round(grouped/total*100)}%) | 100% |
| 선생님 태깅 완료 | ${tagged}개 (${Math.round(tagged/total*100)}%) | 80% |
| 유사문제 있음 | ${hasSimilar}개 (${Math.round(hasSimilar/total*100)}%) | 90% |
`);
```

---

## 🗓️ 단계별 실행 일정

### ✅ Week 1 (완료) — 기반 구축
- [x] 메타데이터 자동 그룹화 (43그룹)
- [x] 이미지 임베딩 유사도 7쌍 추가 (total 377쌍)
- [x] 태깅 컬럼 4개 추가
- [x] Obsidian 태깅 섹션 연동

### 🔧 Week 2 — 선생님 태깅 집중
- [ ] 수능 공통 1-22번 concept_tags 입력 (46문제)
- [ ] 선택과목 23-30번 solution_key 입력 (48문제)
- [ ] similar_type 분류 (계산형/추론형/조건형)

### 📈 Week 3 — 그룹 정교화
- [ ] 잘못된 유사그룹 수정 (유사도 낮은 쌍 제거)
- [ ] 교차 연도 유사문제 연결 강화
- [ ] 태깅 DB 반영 (`검수완료_DB반영.bat`)

### 🔮 Week 4+ — 확장
- [ ] 경시대회 문제 추가 (ST·KC)
- [ ] 내신 기출 추가
- [ ] 이미지 임베딩 THRESHOLD 조정

---

## 🏷️ 태깅 빠른 가이드

**문제 페이지에서 Properties 패널 열기 후:**

```yaml
concept_tags: 곱의미분법          ← 핵심 개념
solution_key: f'(x) 계산후 x=1 대입  ← 풀이 핵심
similar_type: 계산형              ← 계산형/추론형/조건형
variation_note: 함수만 바꾸면 유사  ← 변형 아이디어
```

**태깅 후**: `검수완료_DB반영.bat` 실행

---

## 🔗 유사문제 현황 (이미지 유사도 TOP)

```dataview
TABLE year AS "연도", source_type AS "출처", 
      topic AS "단원", length(similar_ids) AS "유사수"
FROM "wiki/problems"
WHERE similar_ids AND length(similar_ids) >= 5
SORT length(similar_ids) DESC
LIMIT 15
```

---

## ⚡ 태깅 미완료 문제 목록

```dataview
TABLE topic AS "단원", difficulty AS "난이도", year AS "연도"
FROM "wiki/problems"
WHERE concept_tags = "" OR concept_tags IS NULL
SORT year ASC, problem_number ASC
LIMIT 20
```

---

## 📋 주간 점검 항목

매주 실행:
```bash
# 유사그룹 자동 갱신
python3 scripts/update_similar_groups.py

# 태깅 DB 반영
검수완료_DB반영.bat

# 진행률 확인
python3 scripts/intern_agent.py --report
```
