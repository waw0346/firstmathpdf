---
tags: [dashboard, quick-verify]
---

# ⚡ 빠른 검수 그리드 (Obsidian)

> 📌 **Dataview 플러그인** 필요 | 이미지를 보며 한 화면에서 빠르게 검수

---

## 📊 현재 진행 상황

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;
const A  = pp.filter(p => p.final_grade === "A").length;
const B  = pp.filter(p => p.final_grade === "B").length;
const s3 = pp.filter(p => p.stage3_sol === "pass").length;
const tr = pp.filter(p => p.sign_tr && p.sign_tr !== "").length;
const cp = pp.filter(p => p.sign_cp && p.sign_cp !== "").length;

const bar = (n,t,color) => {
  const pct = Math.round(n/t*100);
  return `<span style="color:${color};font-weight:bold">${n}/${t} (${pct}%)</span>`;
};

dv.paragraph(`
| 항목 | 현황 |
|------|------|
| ✅ 이미지+정답 자동통과 | ${bar(138,total,"#00b894")} |
| 📝 3단계 해설 완료 | ${bar(s3,total,"#fdcb6e")} |
| 🏆 A등급 완료 | ${bar(A,total,"#00b894")} |
| 🟡 B등급 (해설 필요) | ${bar(B,total,"#fdcb6e")} |
| 🖊️ 선생님(tr) 서명 | ${bar(tr,total,"#ff7043")} |
| 🖊️ 관리자(cp) 서명 | ${bar(cp,total,"#a29bfe")} |
`);
```

---

## 📖 해설 입력 방법 (단계별)

> 1. 아래 그리드에서 문제 클릭 → 문제 페이지 열기
> 2. 우측 **Properties 패널** 에서 2개 필드만 수정:
>    - `stage3_sol` → `pass`
>    - `stage3_solution` → `풀이 내용 (간략히)`
> 3. 파일 자동 저장됨

---

## 🔍 필터: B등급 (해설 미입력) 문제 그리드

```dataviewjs
const pp = dv.pages('"wiki/problems"')
  .filter(p => p.final_grade === "B" || p.final_grade === "pending")
  .sort(p => String(p.year) + String(p.problem_number||0).padStart(3,"0") + p.file.name);

if (pp.length === 0) {
  dv.paragraph("🎉 **모든 문제 완료!** A등급 달성");
} else {
  dv.paragraph(`📋 **${pp.length}개 해설 필요** — 문제 클릭 후 Properties에서 stage3_sol: pass 입력`);
  dv.table(
    ["🖼️", "문제", "정답", "출처", "난이도", "해설상태"],
    pp.map(p => {
      const fname = p.crop_path ? p.crop_path.split("/").pop() : "";
      const s3 = p.stage3_sol;
      const s3icon = s3==="pass"?"✅":s3==="fail"?"❌":"⏳";
      return [
        fname ? `![[${fname}|70]]` : "❌",
        p.file.link,
        p.answer || "⚠️",
        (p.year||"") + " " + (p.source_type||""),
        p.difficulty || "-",
        s3icon + " " + s3
      ];
    })
  );
}
```

---

## ✅ A등급 완료 목록

```dataviewjs
const pp = dv.pages('"wiki/problems"')
  .filter(p => p.final_grade === "A")
  .sort(p => String(p.year) + String(p.problem_number||0).padStart(3,"0"));

if (pp.length === 0) {
  dv.paragraph("⏳ 아직 A등급 없음");
} else {
  dv.table(
    ["문제", "정답", "출처", "tr", "cp"],
    pp.map(p => [
      p.file.link,
      p.answer || "⚠️",
      (p.year||"") + " " + (p.source_type||""),
      p.sign_tr ? "✅" : "⬜",
      p.sign_cp ? "✅" : "⬜"
    ])
  );
}
```

---

## 🌐 브라우저 그리드 뷰 (이미지 썸네일 전체)

> 더 빠른 시각 검수: 아래 파일을 파일 탐색기에서 더블클릭

📂 `wiki/quick_verify.html` — 138개 썸네일 한 화면

또는 터미널에서:
```bash
cd C:\Users\oem\Documents\math_llm
python wiki\start_server.py
```
→ 브라우저에서 `http://localhost:8765/wiki/quick_verify.html` 열기

---

## 💾 해설 입력 후 DB 반영

```bash
# Obsidian에서 해설 입력 완료 후
python scripts\sync_from_obsidian.py

# 또는 더블클릭
검수완료_DB반영.bat
```

