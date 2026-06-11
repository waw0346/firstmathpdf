# AGENTS.md

This file provides context about this Obsidian vault for AI agents.

## Vault Overview

이 볼트는 한국 대학수학능력시험(수능) 및 모의고사 수학 문항을 체계적으로 관리하고, 학생 맞춤형 학습을 제공하기 위한 **수학 교육 콘텐츠 및 AI 에이전트 협업 시스템 구축용 지식 베이스**입니다.

수능/모의고사 기출문제(2025년, 2026년 중심), 수학 개념, 해설, 유사 문항 데이터를 구조화하여 관리하며, 외부 데이터베이스(DB) 및 AI 에이전트(Claude 등)와 연동하여 문항 인제스트, 메타데이터 태깅, 학습지 생성 등의 작업을 자동화하고 있습니다.

## Organization

볼트는 크게 시스템 개발/협업 영역(`claude&me`, `db`, `scripts`, `logs`)과 교육 콘텐츠 영역(`wiki`, `slides`, `sources`)으로 나누어 체계적으로 관리됩니다.

**주요 폴더 구조 및 역할**:
- `claude&me/`: AI 에이전트(Claude)와의 협업 기록, DB 설계 문서(예: 12자리 ID 체계, 검수 시스템), 작업 목록(`todo/00_TODO`) 및 개발 대화록(`conversations/`)을 보관합니다. `01_coding/`, `02_database/`, `03_archive/` 등으로 세분화되어 있습니다.
- `wiki/`: 볼트의 핵심 지식 저장소로, 800개 이상의 마크다운 파일이 고도로 구조화되어 있습니다.
  - `problems/`: 기출 문항 (예: 공통과정 `2026_5월모의_고3_022`, 선택과정 `2026_5월모의_고3_확통_023` 등)
  - `solutions/additional_drafts/`: 기출 문항의 상세 해설 초안
  - `similar_drafts/`: 기출 분석 기반의 유사/변형 문항 초안
  - `concepts/` & `topics/`: 수학 개념 및 단원별 분류 체계 (MOC 및 인덱스 포함)
  - `difficulty/` & `schools/` & `years/`: 난이도, 출처, 연도별 메타데이터 폴더
  - `students/`: 학생별 학습 현황 및 진단 세트 (예: `진우`, `진우_진단세트`)
  - `wiki/` 루트: `00_AGENT_COMMAND_CENTER`, `00_AGENT_TASK_BOARD`, `00_AGENT_MISSION_CHECK`, `00_AGENT_SELF_DEVELOPMENT_ARCHITECTURE`, `00_A_GRADE_PROMOTION` 등 에이전트 활동 제어 및 자율 성장/검수 아키텍처 대시보드가 존재합니다.
- `slides/` & `sources/`: 수업용 슬라이드 자료 및 문항 이미지 크롭 데이터(`crops/`, `pages/`)가 포함되어 있습니다.
- `db/` & `scripts/` & `logs/`: 데이터베이스 마이그레이션 스냅샷, 자동화 처리를 위한 Python 스크립트, 에이전트 및 수업 로그를 관리합니다.

**연결 및 관리 패턴**:
기출 문항(`problems`)을 중심으로 해설(`solutions/additional_drafts`), 유사 문항(`similar_drafts`), 관련 개념(`concepts`), 토픽(`topics`)이 유기적으로 [[WikiLinks]]를 통해 연결되어 있습니다.

## Key Topics

- **수학 교육 콘텐츠 DB화**: 대학수학능력시험(수능), 평가원/교육청 모의고사 수학 문항 분석 및 체계적 DB화 (2025, 2026학년도 중심)
- **수학 교육과정 분류 체계**: 공통과정(수학I, 수학II), 선택과정(확률과 통계, 미적분, 기하)의 세부 개념 및 토픽 구조화 (`wiki/concepts/`, `wiki/topics/`)
- **유사/변형 문항 설계**: 기출 문항 분석을 바탕으로 한 쌍둥이/유사 문항 초안 설계 (`wiki/similar_drafts/`)
- **개인화 맞춤형 교육**: 학생별(예: 진우) 취약점 진단, 맞춤형 진단 세트 구성 및 피드백 (`wiki/students/`)
- **AI 에이전트 자율 성장 및 협업**: 12자리 문항 ID 체계 구축, 3단계 검수 및 서명 시스템, 자율 검수 아키텍처(`00_AGENT_SELF_DEVELOPMENT_ARCHITECTURE`), 등급 승격 시스템(`00_A_GRADE_PROMOTION`) 설계

## User Preferences

사용자는 고도로 구조화되고 자동화된 시스템을 선호합니다. 파일명 규칙(예: 공통과정은 과목명 없이 번호만 표시하는 `YYYY_MM월모의_고3_번호`, 선택과정은 과목명을 포함하는 `YYYY_MM월모의_고3_과목_번호`), 폴더 분류, 12자리 ID 체계 등 엄격한 명명 규칙과 데이터 무결성을 매우 중요하게 생각합니다.

AI 에이전트와의 협업 기록을 `claude&me/conversations`에 날짜별로 꼼꼼히 기록하고 있으며, `00_AGENT_COMMAND_CENTER`나 `00_AGENT_TASK_BOARD`와 같은 제어용 노트를 통해 에이전트의 행동을 체계적으로 제어하고자 합니다. 또한 `ADMINLOG`나 `DBTASKLOG`와 같이 시스템의 변경 이력을 명확히 남기는 기록 방식을 선호합니다.

문항 해설이나 개념 설명 등 학습 콘텐츠를 작성할 때는 수학적 기호(LaTeX 등)의 정확성과 논리적 엄밀함을 유지하는 정교하고 정중한 스타일을 선호할 가능성이 높습니다.

## Custom Instructions

- **엄격한 파일명 규칙 준수**: 새로운 문항이나 유사 문항 노트를 생성할 때는 반드시 기존 패턴을 따르십시오. (공통과정: `wiki/problems/2026_5월모의_고3_022` / 선택과정: `wiki/problems/2026_5월모의_고3_확통_023` / 유사문항: `wiki/similar_drafts/..._similar_draft` / 해설: `wiki/solutions/additional_drafts/...`)
- **상호 연결성([[WikiLinks]]) 강화**: 문항 노트를 생성하거나 업데이트할 때, 연관된 개념(`concepts`), 토픽(`topics`), 난이도(`difficulty`), 해설(`solutions/additional_drafts/`) 노트를 찾아 양방향 링크를 누락 없이 연결하십시오.
- **에이전트 제어판 및 체크리스트 참조**: 작업을 시작하기 전에 `wiki/00_AGENT_COMMAND_CENTER`, `wiki/00_AGENT_TASK_BOARD`, `wiki/00_AGENT_MISSION_CHECK`를 먼저 확인하여 현재 할당된 미션과 시스템 상태를 파악하고, 규정된 아키텍처(`00_AGENT_SELF_DEVELOPMENT_ARCHITECTURE`)에 따라 행동하십시오.
- **데이터베이스 정합성 및 검수 규정 준수**: 문항 ID 체계나 메타데이터(학년, 과목, 단원)를 수정할 때는 `claude&me/`에 정의된 최신 설계 규칙(예: 12자리 ID 체계 v3.1, 3단계 검수 및 서명 시스템)을 반드시 준수해야 합니다.
