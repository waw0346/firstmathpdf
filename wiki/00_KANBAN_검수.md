---
kanban-plugin: basic
---

## ⏳ 검수 대기

```dataview
LIST file.link
FROM "wiki/problems"
WHERE stage1_img = "pending"
LIMIT 8
```


## 🔍 1단계: 이미지 확인

```dataview
LIST file.link
FROM "wiki/problems"  
WHERE stage1_img = "pass" AND stage2_ans = "pending"
LIMIT 8
```


## ✅ 2단계: 정답 확인 완료

```dataview
LIST file.link
FROM "wiki/problems"
WHERE stage1_img = "pass" AND stage2_ans = "pass" AND stage3_sol = "pending"
LIMIT 8
```


## 🖊️ 서명 대기 (Mi·cp)

```dataview
LIST file.link
FROM "wiki/problems"
WHERE final_grade = "B"
LIMIT 8
```


## 🏆 완료 (A등급)

```dataviewjs
const done = dv.pages('"wiki/problems"').filter(p=>p.final_grade==="A");
dv.paragraph(`✅ **${done.length}개 완료**`);
if(done.length > 0) {
  dv.list(done.sort(p=>p.year).slice(0,5).map(p=>p.file.link));
}
```

%% kanban:settings
```
{"kanban-plugin":"basic","show-checkboxes":false,"lane-width":300}
```
%%
