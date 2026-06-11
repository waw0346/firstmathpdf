---
tags: [dashboard, verify]
---

# 🔍 수학 문제 검수 대시보드 (Obsidian)

>  📌 **Dataview 플러그인** 필요 | 문제를 클릭하면 이미지와 함께 검수 가능

> ⚡ **빠른 검수**: [[00_QUICK_VERIFY|그리드 뷰]] | 🌐 [브라우저 썸네일](quick_verify.html)

---

## 📊 전체 진행 현황

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;

const s1ok = pp.filter(p => p.stage1_img === "pass").length;
const s2ok = pp.filter(p => p.stage2_ans === "pass" || p.stage2_ans === "fixed").length;
const s3ok = pp.filter(p => p.stage3_sol === "pass").length;
const trOk = pp.filter(p => p.sign_tr && p.sign_tr !== "").length;
const cpOk = pp.filter(p => p.sign_cp && p.sign_cp !== "").length;
const done = pp.filter(p => p.final_grade === "A").length;
const signed = pp.filter(p => p.sign_tr && p.sign_cp && p.sign_tr !== "" && p.sign_cp !== "").length;

const bar = (n, t) => {
  const pct = Math.round(n/t*100);
  const filled = Math.round(pct/5);
  return `${"█".repeat(filled)}${"░".repeat(20-filled)} ${n}/${t} (${pct}%)`;
};

dv.paragraph(`
| 단계 | 진행 |
|------|------|
| 1단계 이미지 | \`${bar(s1ok, total)}\` |
| 2단계 정답   | \`${bar(s2ok, total)}\` |
| 3단계 해설   | \`${bar(s3ok, total)}\` |
| 선생님(tr) 서명 | \`${bar(trOk, total)}\` |
| 관리자(cp) 서명 | \`${bar(cpOk, total)}\` |
| **최종 완료 (A등급)** | \`${bar(done, total)}\` |
| **TR+CP 서명 완료** | \`${bar(signed, total)}\` |
`);
```

---

## 🔍 검수 방법 (Obsidian)

> 1. 아래 목록에서 **문제 클릭** → 문제 페이지 열기
> 2. **이미지 확인** → 문제+선택지가 온전히 보이는지
> 3. **정답 확인** → DB 정답이 실제 정답과 일치하는지  
> 4. **우측 Properties 패널**에서 값 수정:

| 필드 | 이미지 정상 | 이미지 오류 |
|------|------------|------------|
| `stage1_img` | `pass` | `fail` |
| `stage2_ans` | `pass` | `fail` 또는 `fixed` |
| `stage3_sol` | `pass` | `fail` |
| `sign_tr` | `tr✓ 날짜` | (비워두기) |
| `sign_cp` | `cp✓ 날짜` | (비워두기) |

---

## ⏳ 검수 대기 문제

```dataviewjs
const pp = dv.pages('"wiki/problems"')
  .filter(p => p.stage1_img !== "pass" || p.stage2_ans !== "pass")
  .sort(p => p.year + String(p.problem_number).padStart(3,"0"));

dv.table(
  ["이미지", "문제", "출처", "정답", "1단계", "2단계"],
  pp.map(p => [
    p.crop_path ? `![[${p.crop_path.split("/").pop()}|80]]` : "❌없음",
    p.file.link,
    (p.year || "") + (p.source_type || ""),
    p.answer || "⚠️",
    p.stage1_img === "pass" ? "✅" : p.stage1_img === "fail" ? "❌" : "⏳",
    p.stage2_ans === "pass" ? "✅" : p.stage2_ans === "fixed" ? "🔧" : p.stage2_ans === "fail" ? "❌" : "⏳",
  ])
);
```

---

## ❌ 수정 필요 (fail 표시된 문제)

```dataview
TABLE title AS "제목", year AS "연도", source_type AS "출처",
      stage1_img AS "이미지", stage2_ans AS "정답", stage1_note AS "메모"
FROM "wiki/problems"
WHERE stage1_img = "fail" OR stage2_ans = "fail" OR stage3_sol = "fail"
SORT year ASC, problem_number ASC
```

---

## 🖊️ 서명 대기 (A등급 미서명)

```dataview
TABLE title AS "제목", year AS "연도", source_type AS "출처",
      sign_tr AS "선생님", sign_cp AS "관리자"
FROM "wiki/problems"
WHERE final_grade = "A" AND (sign_tr = "" OR sign_cp = "")
SORT year ASC, problem_number ASC
```

---

## ✅ 검수 완료 목록

```dataview
TABLE title AS "제목", difficulty AS "난이도", year AS "연도",
      source_type AS "출처", answer AS "정답"
FROM "wiki/problems"
WHERE final_grade = "A"
SORT year ASC, problem_number ASC
```

---

## 📋 전체 문제 목록 (연도/과목별)

```dataviewjs
const pp = dv.pages('"wiki/problems"').sort(p => 
  String(p.year) + (p.source_type||"") + String(p.problem_number||0).padStart(3,"0")
);

dv.table(
  ["이미지", "문제", "정답", "1단계", "2단계", "3단계", "tr", "cp"],
  pp.map(p => {
    const fname = p.crop_path ? p.crop_path.split("/").pop() : "";
    const s1 = p.stage1_img;
    const s2 = p.stage2_ans;
    const s3 = p.stage3_sol;
    return [
      fname ? `![[${fname}|60]]` : "❌",
      p.file.link,
      p.answer || "⚠️",
      s1==="pass"?"✅":s1==="fail"?"❌":"⏳",
      s2==="pass"?"✅":s2==="fixed"?"🔧":s2==="fail"?"❌":"⏳",
      s3==="pass"?"✅":s3==="fail"?"❌":"⏳",
      p.sign_tr ? "✅" : "⬜",
      p.sign_cp ? "✅" : "⬜",
    ];
  })
);
```

