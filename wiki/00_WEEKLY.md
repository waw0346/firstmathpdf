---
tags: [weekly, checklist, management]
---

# 📅 주간 필수 관리 체크리스트

> 매주 월요일 `주간점검.bat` 더블클릭 → 자동 실행
> 수동 확인 항목만 아래에서 체크

---

## ⚡ 자동 실행 항목 (배치파일이 처리)

```
✅ DB 스냅샷 생성        (매주 자동)
✅ 유사문제 그룹 갱신    (매주 자동)
✅ 이미지 품질 점검      (매주 자동)
✅ 새 PDF 탐지           (매주 자동)
✅ ADMINLOG 갱신         (매주 자동)
✅ Obsidian 동기화       (매주 자동)
```

---

## 📋 선생님이 직접 확인할 항목

### 🔴 매주 반드시

- [ ] **외부 백업** — math_llm 폴더를 외장HDD 또는 OneDrive에 복사
- [ ] **검수 진행** — Obsidian `00_QUICK_VERIFY.md`에서 문제 확인
- [ ] **Mi 서명** — 확인된 문제에 `sign_Mi: Mi✓ 날짜` 입력

### 🟠 격주 확인

- [ ] **개념 태깅** — 문제 5개 이상 `concept_tags` 입력
- [ ] **새 PDF** — 추가할 시험지 있으면 `PDF_인제스트.bat` 실행

### 🟡 월 1회

- [ ] **ADMINLOG 검토** — 로드맵 점검, 목표 업데이트
- [ ] **스냅샷 정리** — 오래된 스냅샷 삭제 (최근 12개만 유지)

---

## 📊 이번 주 현황

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;
const a = pp.filter(p=>p.final_grade==="A").length;
const tagged = pp.filter(p=>p.concept_tags && p.concept_tags!=="").length;
const miSign = pp.filter(p=>p.sign_Mi && p.sign_Mi!=="").length;

const bar = (n,t) => {
  const pct = Math.round(n/t*100);
  const fill = Math.round(pct/5);
  return `${'█'.repeat(fill)}${'░'.repeat(20-fill)} ${n}/${t} (${pct}%)`;
};

dv.paragraph(`
| 항목 | 진행률 |
|------|--------|
| ✅ A등급 완료 | \`${bar(a,total)}\` |
| 🏷️ 개념 태깅 | \`${bar(tagged,total)}\` |
| 🖊️ Mi 서명 | \`${bar(miSign,total)}\` |
`);
```

---

## 🗓️ 외부 백업 체크

```
마지막 백업: ___________  (직접 날짜 입력)

백업 위치:
  □ 외장하드 (D:\ 또는 E:\)
  □ OneDrive
  □ Google Drive
  □ NAS
```

---

## 📝 이번 주 메모

> (자유롭게 입력)

---

## 🚀 다음 주 목표

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;
const a = pp.filter(p=>p.final_grade==="A").length;
const remaining = total - a;
const weekly_goal = Math.min(remaining, 20);

dv.paragraph(`
**현재**: A등급 ${a}/${total}개
**이번주 목표**: ${weekly_goal}개 추가 검수·서명
**완료 예상**: ${Math.ceil(remaining/weekly_goal)}주 후
`);
```
