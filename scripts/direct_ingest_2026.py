#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026 수능 수학 직접 인제스트
Claude가 직접 분류 — ANTHROPIC_API_KEY 불필요
"""
import sqlite3, shutil, json, tempfile
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DB_SRC   = BASE_DIR / "db" / "problems.db"
TMP_DIR  = Path(tempfile.gettempdir())

# ──────────────────────────────────────────────────────────────
# 2026 수능 수학 문제 데이터 (Claude 직접 분류)
# 수식은 PDF 크롭 이미지로 표시 — 여기서는 구조/메타데이터만
# ──────────────────────────────────────────────────────────────
PROBLEMS_2026 = [
    # ── 공통 5지선다형 (1~15번) ────────────────────────────────
    {
        "id": "2026_수능_고3_001",
        "title": "지수법칙 계산 (2점)",
        "domain": "수와연산",
        "topic": "지수법칙",
        "concept": ["지수", "거듭제곱"],
        "difficulty": "하",
        "problem_number": 1,
        "score": 2,
        "problem_type": "5지선다형",
        "page": 1,
        "raw_text": "지수 계산식의 값을 구하는 문제. [2점]"
    },
    {
        "id": "2026_수능_고3_002",
        "title": "함수의 극한값 (2점)",
        "domain": "함수",
        "topic": "극한",
        "concept": ["함수의 극한", "극한값"],
        "difficulty": "하",
        "problem_number": 2,
        "score": 2,
        "problem_type": "5지선다형",
        "page": 1,
        "raw_text": "함수 f(x)에 대하여 극한값을 구하는 문제. [2점]"
    },
    {
        "id": "2026_수능_고3_003",
        "title": "수열 합 계산 (3점)",
        "domain": "수와연산",
        "topic": "수열",
        "concept": ["수열", "합", "시그마"],
        "difficulty": "중",
        "problem_number": 3,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 1,
        "raw_text": "수열 {a_n}에 대하여 합의 값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_004",
        "title": "연속함수 상수 결정 (3점)",
        "domain": "함수",
        "topic": "연속",
        "concept": ["함수의 연속", "연속조건", "상수"],
        "difficulty": "중",
        "problem_number": 4,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 1,
        "raw_text": "함수가 실수 전체에서 연속일 때 상수 a의 값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_005",
        "title": "함수 미분값 (3점)",
        "domain": "함수",
        "topic": "미분",
        "concept": ["미분", "도함수", "미분값"],
        "difficulty": "중",
        "problem_number": 5,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 2,
        "raw_text": "함수 f(x)에 대하여 f'(a)의 값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_006",
        "title": "로그 조건과 값 계산 (3점)",
        "domain": "수와연산",
        "topic": "로그",
        "concept": ["로그", "상용로그", "조건"],
        "difficulty": "중",
        "problem_number": 6,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 2,
        "raw_text": "두 실수 a, b가 로그 조건을 만족할 때 log 값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_007",
        "title": "두 곡선과 직선으로 둘러싸인 넓이 (3점)",
        "domain": "함수",
        "topic": "적분의 활용",
        "concept": ["넓이", "정적분", "곡선"],
        "difficulty": "중",
        "problem_number": 7,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 2,
        "raw_text": "두 곡선과 직선으로 둘러싸인 부분의 넓이를 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_008",
        "title": "삼각함수 조건과 값 (3점)",
        "domain": "함수",
        "topic": "삼각함수",
        "concept": ["삼각함수", "sin", "cos", "조건식"],
        "difficulty": "중",
        "problem_number": 8,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 3,
        "raw_text": "sin+cos 조건과 cos 조건이 주어질 때 sin 값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_009",
        "title": "함수와 직선의 접선 조건 (4점)",
        "domain": "함수",
        "topic": "미분의 활용",
        "concept": ["접선", "미분", "접하는 조건"],
        "difficulty": "상",
        "problem_number": 9,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 3,
        "raw_text": "양수 a에 대하여 직선이 곡선에 접할 때 a의 값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_010",
        "title": "지수함수 점근선과 삼각형 넓이 (4점)",
        "domain": "함수",
        "topic": "지수함수",
        "concept": ["지수함수", "점근선", "삼각형 넓이", "좌표"],
        "difficulty": "상",
        "problem_number": 10,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 3,
        "raw_text": "지수함수 곡선 위 점과 점근선, 삼각형 넓이 조건으로 값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_011",
        "title": "수직선 위 점의 운동 (4점)",
        "domain": "함수",
        "topic": "속도와 거리",
        "concept": ["속도", "이동거리", "수직선", "보기"],
        "difficulty": "상",
        "problem_number": 11,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 4,
        "raw_text": "수직선 위를 움직이는 점 P의 속도가 주어질 때 보기 참/거짓을 판별하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_012",
        "title": "등비수열 조건 계산 (4점)",
        "domain": "수와연산",
        "topic": "등비수열",
        "concept": ["등비수열", "공비", "합", "조건"],
        "difficulty": "상",
        "problem_number": 12,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 4,
        "raw_text": "등비수열이 조건을 만족시킬 때 값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_013",
        "title": "함수 조건과 극값 (4점)",
        "domain": "함수",
        "topic": "미분의 활용",
        "concept": ["극값", "미분", "함수 조건"],
        "difficulty": "상",
        "problem_number": 13,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 5,
        "raw_text": "두 함수 조건에서 극값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_014",
        "title": "사인함수 조건 최솟값 (4점)",
        "domain": "함수",
        "topic": "삼각함수",
        "concept": ["삼각함수", "최솟값", "sin", "부등식"],
        "difficulty": "상",
        "problem_number": 14,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 5,
        "raw_text": "모든 실수에 대한 부등식 조건으로 최솟값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_015",
        "title": "함수 연속과 극한 종합 (4점)",
        "domain": "함수",
        "topic": "극한과 연속",
        "concept": ["극한", "연속", "합성함수"],
        "difficulty": "상",
        "problem_number": 15,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 6,
        "raw_text": "함수의 연속과 극한이 복합된 조건 문제. [4점]"
    },
    # ── 공통 단답형 (16~22번) ──────────────────────────────────
    {
        "id": "2026_수능_고3_016",
        "title": "삼각형 넓이 단답 (3점)",
        "domain": "기하",
        "topic": "삼각형",
        "concept": ["삼각형 넓이", "코사인법칙", "사인법칙"],
        "difficulty": "중",
        "problem_number": 16,
        "score": 3,
        "problem_type": "단답형",
        "page": 7,
        "raw_text": "AB, AC 길이와 cos각도가 주어진 삼각형 넓이를 구하시오. [3점]"
    },
    {
        "id": "2026_수능_고3_017",
        "title": "부등식 만족하는 상수 범위 (3점)",
        "domain": "수와연산",
        "topic": "부등식",
        "concept": ["부등식", "상수", "범위"],
        "difficulty": "중",
        "problem_number": 17,
        "score": 3,
        "problem_type": "단답형",
        "page": 7,
        "raw_text": "구간에서 모든 실수 x에 대해 부등식을 만족하는 자연수 k의 개수를 구하시오. [3점]"
    },
    {
        "id": "2026_수능_고3_018",
        "title": "삼각함수 합 단답 (3점)",
        "domain": "함수",
        "topic": "삼각함수",
        "concept": ["삼각함수", "합", "단답"],
        "difficulty": "중",
        "problem_number": 18,
        "score": 3,
        "problem_type": "단답형",
        "page": 7,
        "raw_text": "삼각함수 조건에서 합의 값을 구하시오. [3점]"
    },
    {
        "id": "2026_수능_고3_019",
        "title": "수열 조건 단답 (4점)",
        "domain": "수와연산",
        "topic": "수열",
        "concept": ["수열", "점화식", "조건"],
        "difficulty": "상",
        "problem_number": 19,
        "score": 4,
        "problem_type": "단답형",
        "page": 7,
        "raw_text": "수열 조건이 주어질 때 값을 구하시오. [4점]"
    },
    {
        "id": "2026_수능_고3_020",
        "title": "함수 조건 단답 (4점)",
        "domain": "함수",
        "topic": "함수의 성질",
        "concept": ["함수", "조건", "단답"],
        "difficulty": "상",
        "problem_number": 20,
        "score": 4,
        "problem_type": "단답형",
        "page": 7,
        "raw_text": "함수 조건에서 값을 구하시오. [4점]"
    },
    {
        "id": "2026_수능_고3_021",
        "title": "삼차함수 연속 조건 킬러 (4점)",
        "domain": "함수",
        "topic": "연속과 미분",
        "concept": ["삼차함수", "연속", "조건", "킬러"],
        "difficulty": "최상",
        "problem_number": 21,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 8,
        "raw_text": "최고차항의 계수가 양수인 삼차함수와 실수에 대한 함수가 연속 조건을 만족할 때 값을 구하는 킬러 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_022",
        "title": "최고난도 단답 킬러 (4점)",
        "domain": "함수",
        "topic": "함수 종합",
        "concept": ["킬러", "함수", "최고난도"],
        "difficulty": "최상",
        "problem_number": 22,
        "score": 4,
        "problem_type": "단답형",
        "page": 8,
        "raw_text": "공통 22번 최고난도 킬러 문제. [4점]"
    },
    # ── 확률과 통계 선택 (23~30번) ─────────────────────────────
    {
        "id": "2026_수능_고3_확통_023",
        "title": "중복순열 경우의 수 (2점)",
        "domain": "확률과통계",
        "topic": "경우의 수",
        "concept": ["중복순열", "경우의 수"],
        "difficulty": "하",
        "problem_number": 23,
        "score": 2,
        "problem_type": "5지선다형",
        "page": 9,
        "raw_text": "네 문자 중 중복을 허락하여 나열하는 경우의 수. [2점]"
    },
    {
        "id": "2026_수능_고3_확통_024",
        "title": "두 사건 조건부확률 (3점)",
        "domain": "확률과통계",
        "topic": "조건부확률",
        "concept": ["조건부확률", "두 사건"],
        "difficulty": "중",
        "problem_number": 24,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 9,
        "raw_text": "두 사건에 대한 조건부확률 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_확통_025",
        "title": "주머니 공 확률 (3점)",
        "domain": "확률과통계",
        "topic": "확률",
        "concept": ["확률", "주머니", "시행"],
        "difficulty": "중",
        "problem_number": 25,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 10,
        "raw_text": "주머니에서 공을 꺼내는 시행에서의 확률 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_확통_026",
        "title": "이항분포 활용 (3점)",
        "domain": "확률과통계",
        "topic": "이항분포",
        "concept": ["이항분포", "확률변수", "기댓값"],
        "difficulty": "중",
        "problem_number": 26,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 10,
        "raw_text": "이항분포를 따르는 확률변수 관련 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_확통_027",
        "title": "이산확률변수 분산 (4점)",
        "domain": "확률과통계",
        "topic": "확률변수",
        "concept": ["이산확률변수", "분산", "기댓값"],
        "difficulty": "상",
        "problem_number": 27,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 11,
        "raw_text": "이산확률변수의 분산 V(X)를 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_확통_028",
        "title": "정규분포 활용 (4점)",
        "domain": "확률과통계",
        "topic": "정규분포",
        "concept": ["정규분포", "표준화", "확률"],
        "difficulty": "상",
        "problem_number": 28,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 11,
        "raw_text": "정규분포를 따르는 확률변수의 확률을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_확통_029",
        "title": "확률 단답 4점",
        "domain": "확률과통계",
        "topic": "확률",
        "concept": ["확률", "주사위", "동전", "시행"],
        "difficulty": "상",
        "problem_number": 29,
        "score": 4,
        "problem_type": "단답형",
        "page": 12,
        "raw_text": "이하 자연수에 대해 주사위와 동전을 사용한 시행의 확률 단답. [4점]"
    },
    {
        "id": "2026_수능_고3_확통_030",
        "title": "확통 킬러 단답 (4점)",
        "domain": "확률과통계",
        "topic": "확률 종합",
        "concept": ["킬러", "확률", "경우의 수", "복합"],
        "difficulty": "최상",
        "problem_number": 30,
        "score": 4,
        "problem_type": "단답형",
        "page": 12,
        "raw_text": "확률과 통계 선택 30번 최고난도 킬러 문제. [4점]"
    },
    # ── 미적분 선택 (23~30번) ───────────────────────────────────
    {
        "id": "2026_수능_고3_미적_023",
        "title": "삼각함수 극한 (2점)",
        "domain": "함수",
        "topic": "삼각함수 극한",
        "concept": ["극한", "tan", "삼각함수"],
        "difficulty": "하",
        "problem_number": 23,
        "score": 2,
        "problem_type": "5지선다형",
        "page": 13,
        "raw_text": "lim(x→0) tan/x 형태의 삼각함수 극한. [2점]"
    },
    {
        "id": "2026_수능_고3_미적_024",
        "title": "삼각함수 적분 (3점)",
        "domain": "함수",
        "topic": "삼각함수 적분",
        "concept": ["적분", "sin", "cos", "치환"],
        "difficulty": "중",
        "problem_number": 24,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 13,
        "raw_text": "sin·cos 형태의 정적분 값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_미적_025",
        "title": "수열 점화식과 극한 (3점)",
        "domain": "수와연산",
        "topic": "수열의 극한",
        "concept": ["수열", "점화식", "극한", "무한급수"],
        "difficulty": "중",
        "problem_number": 25,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 14,
        "raw_text": "수열이 점화식을 만족할 때 극한값을 구하는 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_미적_026",
        "title": "지수함수 미분 활용 (3점)",
        "domain": "함수",
        "topic": "지수함수 미분",
        "concept": ["지수함수", "미분", "접선"],
        "difficulty": "중",
        "problem_number": 26,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 14,
        "raw_text": "지수함수의 미분 활용 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_미적_027",
        "title": "매개변수 곡선과 직선 (4점)",
        "domain": "함수",
        "topic": "매개변수",
        "concept": ["매개변수", "곡선", "접점"],
        "difficulty": "상",
        "problem_number": 27,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 15,
        "raw_text": "매개변수로 나타낸 곡선과 직선이 만나는 점에서 값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_미적_028",
        "title": "적분과 급수 관계 (4점)",
        "domain": "함수",
        "topic": "적분의 활용",
        "concept": ["적분", "급수", "리만합"],
        "difficulty": "상",
        "problem_number": 28,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 15,
        "raw_text": "급수와 정적분 관계를 활용한 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_미적_029",
        "title": "등차·등비수열 복합 단답 (4점)",
        "domain": "수와연산",
        "topic": "수열",
        "concept": ["등차수열", "등비수열", "조건", "단답"],
        "difficulty": "상",
        "problem_number": 29,
        "score": 4,
        "problem_type": "단답형",
        "page": 16,
        "raw_text": "첫째항과 공차가 같은 등차수열과 등비수열이 조건을 만족할 때 값. [4점]"
    },
    {
        "id": "2026_수능_고3_미적_030",
        "title": "미적분 킬러 단답 (4점)",
        "domain": "함수",
        "topic": "미적분 종합",
        "concept": ["킬러", "미적분", "최고난도"],
        "difficulty": "최상",
        "problem_number": 30,
        "score": 4,
        "problem_type": "단답형",
        "page": 16,
        "raw_text": "미적분 선택 30번 최고난도 킬러 문제. [4점]"
    },
    # ── 기하 선택 (23~30번) ─────────────────────────────────────
    {
        "id": "2026_수능_고3_기하_023",
        "title": "벡터 성분 합 (2점)",
        "domain": "기하",
        "topic": "벡터",
        "concept": ["벡터", "성분", "합"],
        "difficulty": "하",
        "problem_number": 23,
        "score": 2,
        "problem_type": "5지선다형",
        "page": 17,
        "raw_text": "두 벡터에 대하여 성분의 합을 구하는 문제. [2점]"
    },
    {
        "id": "2026_수능_고3_기하_024",
        "title": "포물선 활용 (3점)",
        "domain": "기하",
        "topic": "이차곡선",
        "concept": ["포물선", "초점", "준선"],
        "difficulty": "중",
        "problem_number": 24,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 17,
        "raw_text": "포물선의 성질을 활용한 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_기하_025",
        "title": "좌표공간 대칭점과 거리 (3점)",
        "domain": "기하",
        "topic": "공간좌표",
        "concept": ["대칭", "좌표공간", "거리"],
        "difficulty": "중",
        "problem_number": 25,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 18,
        "raw_text": "좌표공간에서 평면 대칭, 원점 대칭한 점 사이 거리. [3점]"
    },
    {
        "id": "2026_수능_고3_기하_026",
        "title": "타원 활용 (3점)",
        "domain": "기하",
        "topic": "이차곡선",
        "concept": ["타원", "초점", "장축"],
        "difficulty": "중",
        "problem_number": 26,
        "score": 3,
        "problem_type": "5지선다형",
        "page": 18,
        "raw_text": "타원의 성질을 활용한 문제. [3점]"
    },
    {
        "id": "2026_수능_고3_기하_027",
        "title": "원기둥과 선분 관계 (4점)",
        "domain": "기하",
        "topic": "공간도형",
        "concept": ["원기둥", "공간도형", "선분"],
        "difficulty": "상",
        "problem_number": 27,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 19,
        "raw_text": "지름이 같은 두 원을 밑면으로 하는 원기둥과 선분 관계 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_기하_028",
        "title": "쌍곡선과 삼각형 (4점)",
        "domain": "기하",
        "topic": "이차곡선",
        "concept": ["쌍곡선", "삼각형", "넓이"],
        "difficulty": "상",
        "problem_number": 28,
        "score": 4,
        "problem_type": "5지선다형",
        "page": 19,
        "raw_text": "쌍곡선과 삼각형 조건에서 값을 구하는 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_기하_029",
        "title": "포물선 준선 단답 (4점)",
        "domain": "기하",
        "topic": "이차곡선",
        "concept": ["포물선", "초점", "준선", "단답"],
        "difficulty": "상",
        "problem_number": 29,
        "score": 4,
        "problem_type": "단답형",
        "page": 20,
        "raw_text": "포물선 위의 점에서 준선에 내린 수선 관련 단답 문제. [4점]"
    },
    {
        "id": "2026_수능_고3_기하_030",
        "title": "기하 킬러 단답 (4점)",
        "domain": "기하",
        "topic": "기하 종합",
        "concept": ["킬러", "기하", "최고난도"],
        "difficulty": "최상",
        "problem_number": 30,
        "score": 4,
        "problem_type": "단답형",
        "page": 20,
        "raw_text": "기하 선택 30번 최고난도 킬러 문제. [4점]"
    },
]

# ──────────────────────────────────────────────────────────────
def ingest():
    now = datetime.now().isoformat()
    tmp = TMP_DIR / "direct_ingest_2026.db"
    shutil.copy(DB_SRC, tmp)
    conn = sqlite3.connect(tmp)
    conn.row_factory = sqlite3.Row

    inserted, skipped = 0, 0
    for p in PROBLEMS_2026:
        existing = conn.execute("SELECT id FROM problems WHERE id=?", (p["id"],)).fetchone()
        if existing:
            skipped += 1
            continue

        tags = json.dumps([p.get("problem_type","5지선다형"), f"{p.get('score',3)}점"], ensure_ascii=False)
        conn.execute("""
            INSERT INTO problems
            (id, title, grade, domain, topic, concept, difficulty,
             source_type, year, school, exam_type,
             answer, problem_number, tags,
             page_number, raw_text, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p["id"],
            p["title"],
            "고3",
            p["domain"],
            p["topic"],
            json.dumps(p["concept"], ensure_ascii=False),
            p["difficulty"],
            "수능",
            2026,
            "수능",
            "수능",
            "",           # 정답은 나중에 입력
            p["problem_number"],
            tags,
            p["page"],
            p["raw_text"],
            now
        ))
        inserted += 1

    conn.commit()
    conn.close()
    shutil.copy(tmp, DB_SRC)
    print(f"✅ 2026 수능 인제스트 완료: {inserted}개 신규, {skipped}개 건너뜀")
    return inserted
if __name__ == "__main__":
    ingest()
