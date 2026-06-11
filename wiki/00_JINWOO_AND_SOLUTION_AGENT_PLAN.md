---
tags: [agents, jinwoo, solution-curation]
updated: 2026-06-05
---

# 진우 프록시·정답해설 큐레이션 에이전트 운영안

## 1. 진우 학생 프록시 에이전트

목적: 실제 학생 기록을 오염시키지 않고 진우의 가상 풀이 세션, 진단 세트, 예상 오답 패턴을 실험한다.

담당 에이전트: `Jinwoo Proxy Agent`

명령:

```powershell
python agents\jinwoo_proxy_agent.py --diagnostic-set --count 20
python agents\jinwoo_proxy_agent.py --dry-run-attempts --count 20
```

원칙:

- 기본 실행은 dry-run이다.
- 실제 `student_answers` 반영은 별도 승인 전까지 금지한다.
- 진우 실제 기록과 에이전트 시뮬레이션 기록은 분리한다.
- 원본문제/원본해설은 변경하지 않는다.

## 2. 정답·해설 큐레이션 에이전트

목적: 정답 누락, 해설 누락, stage3 검수 대상을 큐로 만들고 Math Expert/Teacher에게 작업을 배정한다.

담당 에이전트: `Answer Solution Curator Agent`

명령:

```powershell
python agents\answer_solution_curator_agent.py --queue --limit 50
```

임무:

- 정답 누락 문제 탐지
- 해설 미완료 문제 큐 생성
- 공식/원본 해설 파일의 존재 여부 확인
- 추가 해설 입력 대상과 우선순위 산출

절대 원칙:

- 원본 해설은 수정하지 않는다.
- 공식 해설은 보존한다.
- 추가 해설은 `stage3_solution` 또는 별도 추가 해설 노트에만 기록한다.
- 원본 해설과 추가 해설을 같은 필드에서 섞지 않는다.

## 3. 권장 작업 순서

1. `Integrity Guard` audit
2. `Answer Solution Curator`가 해설 큐 생성
3. `Math Expert`가 추가 해설 초안 작성
4. `Teacher`가 수업용 표현으로 검수
5. `Verification`이 stage3 pass 여부만 기록
6. `Obsidian Curator`가 원본/추가 해설 분리 상태 확인
