---
tags: [agents, task-board, kanban]
updated: 2026-06-06
kanban-plugin: basic
---

# 🧭 에이전트 업무 보드

## 🚨 최우선
- [x] Integrity Guard: 원본문제·원본정답·원본해설 해시 기준선 생성
- [x] Integrity Guard: 작업 전 원본 무결성 audit 실행
- [x] DB Guardian: 작업 전 `db/problems.db` 276문제 확인
- [ ] Senior Engineer: 모든 DB 접근 스크립트를 `db_helper.py` 또는 `BaseAgent.get_db()` 패턴으로 통일
- [x] Obsidian Curator: 문제 노트 frontmatter에 검수 필드 누락 여부 점검
- [x] Obsidian Curator: DB 276개 vs Wiki 296개 불일치 원인 분류
- [x] Obsidian Curator: DB 276개 vs Wiki 276개 동기화 완료
- [x] Ingest Agent: file_registry 보정으로 미등록 PDF 오탐 0개 달성
- [x] Solution Index: 276개 문제 노트에 원본 문제지·정답·해설 접근 색인 필드 추가
- [x] Ingest Agent: `H2611-SU` 원본 정답/해설 경로 보강

## 🔍 검수
- [x] Verification: stage1_img pending 138개 정리
- [x] Verification: stage2_ans pending 138개 정리
- [ ] Math Expert: stage3_sol 276개 해설 입력 계획 수립
- [x] Math Solution Author: 추가해설·유사문제 작성 임무 정의
- [x] Stage3 Promotion Manager: stage3_sol 승격 기준 정의 및 감사 보고서 생성
- [x] Answer Solution Curator: 해설 입력 큐 20개를 `wiki/00_SOLUTION_QUEUE.md`로 생성
- [x] Answer Solution Curator: 추가 해설 안전 초안 20개를 `wiki/solutions/additional_drafts/`에 생성
- [x] Answer Solution Curator: 추가 해설 안전 초안 40개까지 확장
- [x] Grade Promotion: A등급 승격 기준 감사 보고서 생성
- [ ] Captain: A등급 기준과 서명 루프 확정

## 🧠 지식화
- [x] Concept Tagger: 우선 태깅 단원 5개 선정
- [x] Concept Tagger: 276개 문제 1차 concept_tags 입력
- [ ] Concept Tagger: 수업용 세부 태그 2차 보정
- [ ] Wiki: `wiki/concepts/` 폴더 생성 및 핵심 개념 노트 10개 작성
- [ ] Search: 유사문제 없는 197개 문제 보강
- [x] Math Solution Author: 유사문제 작성 큐 20개 생성
- [x] Math Solution Author: 유사문제 초안 템플릿 10개 생성
- [x] Search: similar_groups 43개 → 69개로 태그 기반 보강
- [ ] Search: similar_groups 69개를 수업용 그룹명으로 정리

## 👨‍🎓 학생 맞춤
- [x] Student Success: `wiki/students/진우.md` 생성
- [x] Jinwoo Proxy: 진우 20문제 dry-run 진단 세트 구성
- [ ] Teacher: 진우 진단 세트 수업용 난이도/단원 균형 검토
- [ ] Student: 풀이 시뮬레이션 결과와 실제 오답 비교 방식 설계

## ✅ 완료 기록
- [x] DB 복구: 최신 276문제 스냅샷을 운영 DB로 복원
- [x] 업무별 에이전트 10개 실행 파일 생성
- [x] 에이전트 지휘본부 문서 생성
- [x] QA smoke: DB/검수/Obsidian/개념/학생 에이전트 실행 확인
- [x] Render Agent: 276개 crop 이미지 누락·이상 0개 확인
- [x] 아카이브: DB에 없는 20개 문제 노트를 `wiki/archive/problems_not_in_db/`로 이동
- [x] 자동 검수: 이미지/정답 존재 문제 276개를 B등급으로 정리
- [x] 에이전트 임무 수행 점검 보고서 생성: `wiki/00_AGENT_MISSION_CHECK.md`
- [x] QA smoke에 Senior Engineer 점검 포함
- [x] QA smoke에 Jinwoo Proxy와 Answer Solution Curator 점검 포함
- [x] 추가 해설 초안 20개 생성: 공식 해설 접근/교사 검수 전 stage3 승격 금지
- [x] 원본 해설 접근 색인 생성: `wiki/00_ORIGINAL_SOLUTION_INDEX.md`
- [x] A등급 승격 감사 생성: `wiki/00_A_GRADE_PROMOTION.md`
- [x] stage3 승격 기준 문서 생성: `wiki/00_STAGE3_PROMOTION_POLICY.md`
- [x] 수학전문가 작성 임무 문서 생성: `wiki/00_MATH_SOLUTION_AUTHOR_BOARD.md`
