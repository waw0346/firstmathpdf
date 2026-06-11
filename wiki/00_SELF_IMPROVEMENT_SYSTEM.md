---
tags: [agents, self-improvement, meta, governance]
updated: 2026-06-06 16:55
---

# 자체 발전 시스템

> 이 문서는 에이전트 감사 결과를 모아 다음 병목과 우선순위를 산출한다. 원본과 DB는 변경하지 않는다.

## 현재 상태

- QA smoke: PASS
- 원본 무결성: PASS
- 문제 노트: 276
- 추가 해설 초안: 276
- 유사문제 초안: 50
- 색인 누락: 0
- Math Expert 검산 보류: 266
- Math Expert 검산 후보: 10
- Teacher 검수 가능: 0
- Teacher 검수 보류: 266
- stage3 승격 후보: 10
- A등급 후보: 10
- local git untracked 파일 수: 357

## 구조적 위험

- 추적되지 않은 파일이 많아 로컬 git 운영 안정성 저하

## 다음 자기 발전 우선순위

| 우선순위 | 담당 | 작업 | 성공 기준 |
|---:|---|---|---|
| 1 | Math Expert Review Agent | 추가 해설 초안 276개 중 우선 10개를 실제 검산 대상으로 분리 | math_expert_review pass 후보 10개 |
| 2 | Teacher Review Agent | Math Expert 통과분만 수업 표현 검수 | teacher_review pass 후보 생성 |
| 3 | Stage3 Promotion Manager | 검산/검수 통과분의 stage3 승격 후보 감사 | stage3_eligible 증가 |
| 4 | Captain | untracked 파일 보존/추적/무시 분류 | untracked 파일 수 감소 |
| 5 | Self Improvement Agent | QA, 검산, 검수, 승격 결과를 매 회차 비교해 병목 변화 기록 | 병목 사유 감소 추세 기록 |

## 자기 발전 루프

1. Integrity Guard가 원본 변경 여부를 확인한다.
2. Solution Index가 모든 문제의 원본/추가 해설 색인을 확인한다.
3. Math Expert가 추가 해설의 수학적 검산 대기열을 만든다.
4. Teacher가 검산 통과분만 수업 표현 검수 대기열로 받는다.
5. Stage3 Promotion Manager가 검산/검수 통과분만 승격 후보로 본다.
6. Grade Promotion Agent가 서명 완료분만 A등급 후보로 본다.
7. Self Improvement Agent가 병목 변화를 기록하고 다음 우선순위를 갱신한다.
