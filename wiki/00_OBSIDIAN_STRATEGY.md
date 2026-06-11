---
tags: [strategy, obsidian, consulting]
updated: 2026-06-05
---

# 🎯 Obsidian 활용 전략 — 수학의 지름길 학원

> 276개 문제 DB 기반 | 선생님 Mi·cp | 학생 관리 시스템 연동

---

## 📊 현재 시스템 강점 (2026.06 기준)

```dataviewjs
const pp = dv.pages('"wiki/problems"');
const total = pp.length;
const byDomain = {};
pp.forEach(p => { byDomain[p.domain||'미분류'] = (byDomain[p.domain||'미분류']||0)+1; });
const sorted = Object.entries(byDomain).sort((a,b)=>b[1]-a[1]);
const max = sorted[0]?.[1]||1;
dv.paragraph(`**총 ${total}개 문제** | 7개 출처 | 선생님 2명 | 학생 시스템 구축\n`);
dv.table(["영역","문제수","비율"],
  sorted.map(([d,n])=>[d, n, '█'.repeat(Math.round(n/max*15))+'░'.repeat(15-Math.round(n/max*15))]));
```

---

## 🔌 단계별 플러그인 전략

### Phase 1 — 즉시 설치 (이번 주)

| 플러그인 | 역할 | 효과 |
|---------|------|------|
| **Spaced Repetition** | 복습 스케줄링 | 망각곡선 방지 |
| **Excalidraw** | 풀이 드로잉 | 손풀이 보존 |
| **Kanban** | 검수 진행판 | 276개 검수 시각화 |

**설치 방법**: 설정 → 커뮤니티 플러그인 → 검색 → 설치

```
Spaced Repetition 사용법:
  문제 페이지 하단에 추가:
  #flashcard
  Q: f(x)=(x²+1)(3x²-x), f'(1)=?
  A: ② 10
```

---

### Phase 2 — 1개월 내

| 플러그인 | 역할 | 효과 |
|---------|------|------|
| **Advanced Canvas** | 개념 지도 | 단원 연결망 시각화 |
| **Dataview JS** | 고급 통계 | 학생별 분석 대시보드 |
| **Templater** | 자동 템플릿 | 문제 페이지 자동 생성 |

---

### Phase 3 — 학생 앱 연동 (3개월)

| 플러그인 | 역할 |
|---------|------|
| **Obsidian-Anki-Sync** | Anki 플래시카드 자동 생성 |
| **remotely-save** | 학생/선생님 Obsidian 동기화 |

---

## 🗺️ 발전 로드맵

### 지금 (276개) → 500개 — "기반 완성"

```
✅ 현재: 수능 2025·2026, 모의고사 5·6·9·10월
🔜 추가: 2025 3·6·9월 모의평가 (92개 추가)
🔜 추가: 경시대회 문제 (성대·KMC)
목표: 500개 전체 검수+서명 완료
```

### 500개 → 1,000개 — "단원 완성"

```
📌 내신 기출 추가 (학교별)
   → H12511-SN성남외 등 v4.0 ID 체계 활용
📌 개념 파일 연결
   → CON-H2-26-A (대수 개념) ← → 관련 문제들
📌 유사문제 네트워크 강화
   → 그래프 뷰에서 클러스터 시각화
```

### 1,000개 → 3,000개 — "학생 맞춤"

```
🎯 학생별 취약 단원 분석
   → 진우: 함수 정답률 45% → 자동 추천
🎯 맞춤 문제지 자동 생성
   → H22606-SN성남외_진우_기말 자동 구성
🎯 학습 결과 트래킹
   → student_answers DB → Obsidian 분석
```

### 3,000개+ → "플랫폼"

```
🚀 학생 웹 앱 (문제 풀기·채점)
🚀 AI 해설 자동 생성 (Claude API)
🚀 선생님 대시보드 (성취도 분석)
🚀 연도별 트렌드 (킬러 문제 패턴)
```

---

## 📐 Obsidian 구조 최적화

### 현재 폴더 구조
```
wiki/
├── problems/     (276개 문제 마크다운)
├── 00_VERIFY.md  (검수 대시보드)
├── 00_QUICK_VERIFY.md
├── 00_VISUAL_DASHBOARD.md  ← 시각 분석
├── 00_KANBAN.md            ← 검수 칸반
└── 00_OBSIDIAN_STRATEGY.md ← 이 파일
```

### 추가 권장 구조
```
wiki/
├── concepts/    ← 개념 파일 연결 (CON-H2-26-A 등)
├── students/    ← 학생별 분석 페이지
│   └── 진우.md  ← 학습 이력·취약단원
├── teachers/    ← 선생님 메모
└── sources/     ← 출처별 인덱스
    ├── 수능_2025.md
    ├── 수능_2026.md
    └── 모의고사_2026.md
```

---

## ⚡ 핵심 Obsidian 활용 3가지

### 1. 그래프 뷰 (Graph View)
```
Ctrl+G → 그래프 뷰 열기
필터: path:wiki/problems
→ 유사문제 연결망 시각화
→ 단원별 클러스터 확인
→ 킬러 문제(연결 많은 노드) 식별
```

### 2. 빠른 검색 (Quick Switcher)
```
Ctrl+O → 문제 검색
예: "확통 29" → 확통 29번 문제 바로 이동
예: "킬러" → 킬러 문제 목록
예: "H2511-SU-Q020" → new_id로 검색
```

### 3. Dataview 쿼리 (이미 설치됨)
```dataview
TABLE difficulty, answer, year
FROM "wiki/problems"
WHERE domain = "함수" AND difficulty = "상"
SORT year DESC
LIMIT 10
```

---

## 🔢 데이터 증가 대비 아키텍처

| 문제 수 | 구조 | 비고 |
|--------|------|------|
| ~500   | 현재 구조 OK | Dataview 쿼리 빠름 |
| ~2,000 | Dataview 캐시 필요 | .obsidian/cache 설정 |
| ~5,000 | SQLite + 뷰어 분리 | 현재 구조가 최적 |
| 10,000+ | 외부 벡터DB | Obsidian은 뷰어만 |

**현재 구조(SQLite + Obsidian)는 5,000개까지 최적화 없이 운영 가능**

---

## 📋 이번 주 할 일

- [ ] Spaced Repetition 플러그인 설치
- [ ] Excalidraw 플러그인 설치  
- [ ] Kanban 플러그인 설치
- [ ] 검수 대시보드(00_QUICK_VERIFY.md)에서 Mi·cp 서명 시작
- [ ] 학생 진우 첫 맞춤 문제지 생성
