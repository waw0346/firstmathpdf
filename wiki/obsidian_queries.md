# 📊 Obsidian Dataview 쿼리 모음

> **사용법**: Obsidian에서 이 파일을 열면 아래 쿼리들이 동적 테이블로 렌더링됩니다.
> Dataview 플러그인이 필요합니다. (Community Plugins → Dataview 검색 후 설치)

---

## 🎯 1. 난이도별 전체 문제 목록

```dataview
TABLE title, domain, topic, answer, year, school
FROM "problems"
SORT difficulty ASC, year DESC
```

---

## ⚫ 2. 최상 난이도 킬러 문제만

```dataview
TABLE title, topic, answer, year, school, file.link AS "바로가기"
FROM "problems"
WHERE difficulty = "최상"
SORT year DESC
```

---

## 📚 3. 영역별 문제 수 요약

```dataview
TABLE length(rows) AS "문제 수"
FROM "problems"
GROUP BY domain AS "영역"
SORT length(rows) DESC
```

---

## 🔗 4. 유사문제가 많은 문제 TOP 10

```dataview
TABLE title, domain, difficulty, length(similar_ids) AS "유사문제수"
FROM "problems"
SORT length(similar_ids) DESC
LIMIT 10
```

---

## 🏫 5. 학교·연도 필터 — 수능 문제만

```dataview
TABLE title, grade, domain, topic, difficulty, answer
FROM "problems"
WHERE school = "수능"
SORT year DESC, problem_number ASC
```

---

## 🟢 6. 쉬운 문제 (하/중) — 기초 개념 복습용

```dataview
TABLE title, topic, concept, answer, year
FROM "problems"
WHERE difficulty = "하" OR difficulty = "중"
SORT domain ASC, topic ASC
```

---

## 🔴 7. 어려운 문제 (상/최상) — 심화 훈련용

```dataview
TABLE title, topic, solution_steps AS "풀이단계", answer, year
FROM "problems"
WHERE difficulty = "상" OR difficulty = "최상"
SORT solution_steps DESC
```

---

## 📐 8. 영역별 상세 — 함수 단원

```dataview
TABLE title, topic, concept, difficulty, answer, year
FROM "problems"
WHERE domain = "함수"
SORT difficulty DESC, year DESC
```

---

## 🔢 9. 수열 문제 전체

```dataview
TABLE title, topic, concept, difficulty, answer
FROM "problems"
WHERE domain = "수열"
SORT difficulty DESC
```

---

## 📅 10. 연도별 문제 수

```dataview
TABLE length(rows) AS "문제 수"
FROM "problems"
GROUP BY year AS "연도"
SORT year DESC
```

---

## 🏷️ 11. 특정 개념 포함 문제 검색 (예: 점화식)

```dataview
TABLE title, domain, difficulty, answer, year
FROM "problems"
WHERE contains(concept, "점화식")
SORT difficulty DESC
```

---

## 📊 12. 전체 통계 카드

```dataview
TABLE WITHOUT ID
  length(rows) AS "총 문제",
  min(rows.year) AS "최초 연도",
  max(rows.year) AS "최근 연도"
FROM "problems"
GROUP BY "전체 현황"
```

---

## 🎓 13. 학년별 분류

```dataview
TABLE title, domain, topic, difficulty, year
FROM "problems"
WHERE grade = "고3"
SORT difficulty DESC, year DESC
```

---

## 🗺️ 14. 그래프 뷰 활용 팁

> Obsidian 그래프 뷰(Ctrl+G)에서 `problems/` 폴더만 필터링하면  
> `similar_ids`로 연결된 문제 네트워크를 시각적으로 확인할 수 있습니다.
>
> - **중심 허브** = 여러 문제와 유사한 핵심 유형 문제
> - **클러스터** = 같은 단원·개념 문제군
> - **고립 노드** = 유사문제가 없는 특이 유형

---

## 🃏 15. Marp 슬라이드용 쿼리 — 수업 문제 선별

```dataview
TABLE title, topic, difficulty, answer
FROM "problems"
WHERE (difficulty = "중" OR difficulty = "상") AND domain = "함수"
SORT difficulty ASC
LIMIT 10
```

> 위 결과를 `scripts/marp_export.py --ids [ID목록]` 에 입력하면  
> 수업용 슬라이드(.md Marp 형식)가 자동 생성됩니다.

---

*마지막 업데이트: 자동 생성 by math-wiki system*
