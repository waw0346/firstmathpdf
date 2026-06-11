---
tags: [guide, flashcard, spaced-repetition]
---

# 🃏 플래시카드 복습 가이드

## Spaced Repetition 플러그인 설치 방법

```
1. Obsidian 설정(⚙️) 열기
2. 커뮤니티 플러그인 → 탐색
3. "Spaced Repetition" 검색
4. 설치 → 활성화
```

---

## 플래시카드 만드는 법

문제 페이지 아무 곳에나 추가:

```markdown
#flashcard

Q: f(x) = (x²+1)(3x²-x) 에서 f'(1) = ?

A: ② 10
```

또는 **앞면 / 뒷면** 형식:

```markdown
f'(1) = ? (f(x)=(x²+1)(3x²-x))
?
② 10
```

---

## 복습 시작하는 법

```
리본 메뉴(왼쪽) → 카드 아이콘 클릭
또는 Ctrl+P → "Review Flashcards"
```

복습 버튼:
- **쉬움** → 오래 후에 다시
- **보통** → 며칠 후에 다시  
- **어려움** → 내일 다시
- **다음에** → 지금 건너뜀

---

## 현재 플래시카드 있는 문제

```dataview
LIST
FROM "wiki/problems"
WHERE contains(file.content, "#flashcard")
SORT file.name ASC
LIMIT 20
```

---

## 복습 일정 (Spaced Repetition 플러그인 설치 후)

플러그인이 자동으로 망각곡선 계산:
- 오늘 배운 문제 → **내일** 복습
- 내일 맞추면 → **3일 후** 복습
- 또 맞추면 → **1주 후** 복습
- 계속 맞추면 → **한 달, 3개월, 6개월...**

> 💡 하루 10-15분만 투자하면 장기 기억으로!
