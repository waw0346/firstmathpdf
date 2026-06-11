---
tags: [kanban, workflow]
kanban-plugin: basic
---

# 📋 문제 검수 칸반 보드

## ⏳ 검수 대기
- [ ] [[wiki/00_QUICK_VERIFY|전체 검수 시작하기]]

---

## 🔍 1단계: 이미지 확인

```dataview
LIST file.link
FROM "wiki/problems"
WHERE stage1_img = "pending"
LIMIT 10
```

---

## ✏️ 2단계: 정답 확인

```dataview
LIST file.link
FROM "wiki/problems"
WHERE stage1_img = "pass" AND stage2_ans = "pending"
LIMIT 10
```

---

## 📝 3단계: 해설 입력

```dataview
LIST file.link
FROM "wiki/problems"
WHERE stage2_ans = "pass" AND stage3_sol = "pending"
LIMIT 10
```

---

## 🖊️ 서명 대기 (A등급 임박)

```dataview
LIST file.link
FROM "wiki/problems"
WHERE final_grade = "B"
LIMIT 10
```

---

## 🏆 완료 (A등급)

```dataviewjs
const done = dv.pages('"wiki/problems"').filter(p=>p.final_grade==="A");
dv.paragraph(`✅ **${done.length}개 완료**`);
```
