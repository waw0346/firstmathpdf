---
tags: [dashboard, visual, analytics]
---

# 📈 수학 문제 시각 분석 대시보드

> 🔄 자동 갱신 | Dataview 플러그인 필요

---

## 📊 전체 현황

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;
const byYear = {};
const bySrc = {};
const byDiff = {};

pp.forEach(p => {
  const y = p.year || '?';
  const s = p.source_type || '?';
  const d = p.difficulty || '?';
  byYear[y] = (byYear[y]||0)+1;
  bySrc[s]  = (bySrc[s]||0)+1;
  byDiff[d] = (byDiff[d]||0)+1;
});

// 막대그래프 (텍스트)
const bar = (n,max,width=20) => {
  const fill = Math.round(n/max*width);
  return '█'.repeat(fill) + '░'.repeat(width-fill) + ` ${n}`;
};

const maxY = Math.max(...Object.values(byYear));
const maxD = Math.max(...Object.values(byDiff));

dv.paragraph(`**총 문제: ${total}개**\n`);

dv.paragraph("### 📅 연도별\n" +
  Object.entries(byYear).sort().map(([y,n])=>
    `**${y}년** ${bar(n,maxY)}`
  ).join('\n'));

dv.paragraph("### 🎯 난이도별\n" +
  ['최하','하','중하','중','중상','상','최상']
    .filter(d=>byDiff[d])
    .map(d=>`**${d}** ${bar(byDiff[d],maxD)}`).join('\n'));
```

---

## 🔥 킬러 문제 (최상·상 난이도)

```dataview
TABLE year AS "연도", source_type AS "출처",
      problem_number AS "번호", answer AS "정답",
      topic AS "단원"
FROM "wiki/problems"
WHERE difficulty = "상" OR difficulty = "최상"
SORT year DESC, problem_number ASC
LIMIT 20
```

---

## 📚 단원별 분포

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const byTopic = {};
pp.forEach(p => {
  const t = p.topic || '미분류';
  byTopic[t] = (byTopic[t]||0)+1;
});
const sorted = Object.entries(byTopic).sort((a,b)=>b[1]-a[1]).slice(0,15);
const max = sorted[0]?.[1] || 1;
dv.table(["단원","문제수","비율"],
  sorted.map(([t,n])=>[t, n, '█'.repeat(Math.round(n/max*10))+'░'.repeat(10-Math.round(n/max*10))])
);
```

---

## 🗓️ 최근 추가된 문제

```dataview
TABLE title AS "제목", year AS "연도", source_type AS "출처",
      difficulty AS "난이도"
FROM "wiki/problems"
SORT created_at DESC
LIMIT 10
```

---

## 🔗 단원 네트워크 (연결 많은 순)

```dataview
TABLE length(similar_ids) AS "유사문제수", topic AS "단원", year AS "연도"
FROM "wiki/problems"
WHERE similar_ids AND length(similar_ids) > 3
SORT length(similar_ids) DESC
LIMIT 15
```
