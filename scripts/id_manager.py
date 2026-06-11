#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
Math LLM Wiki -- ID Manager v3.1
12자리 고유 문제 ID 파서 / 생성기 / 검증기

ID 구조: XXXX-XXXX-XX-XX  (하이픈 제외 12자리)

BLOCK1: 과정(1) + 연도2자리(2) + 과목/학년코드(1)
BLOCK2: 출처/학생코드(2) + 시험월(2)  ← 01~12 고정
BLOCK3: 문항유형(1) + 서브타입(1)
BLOCK4: 문항번호(2)

BLOCK1 4번째 자리 -- 과목/학년 코드:
  과정별 허용 학년:
    E(초등): 1 2 3 4 5 6
    M(중등): 1 2 3
    H(고등): 1 2 3  +  A G C S I Z  (선택과목)
    U(대학): 1 2 3 4
  과목코드(고등 선택):
    A => 대수
    G => 기하
    C => 미적분
    S => 확률과통계
    I => 수학1
    Z => 수학2
    0 => 구분없음

BLOCK2 7~8번 자리 -- 시험 월:
  00 => 구분없음 (교재/연습용)
  01~12 => 해당 시험 시행 월
  예) 03=3월모의  06=6월모의  09=9월모의
      04=4월(내신중간)  07=7월(내신기말)
      10=10월(내신중간)  12=12월(내신기말)
      11=11월(수능)

예시:
  H25S-KO11-QM-28  2025수능(11월) 확통 28번
  H26S-KO11-QM-28  2026수능(11월) 확통 28번
  H25C-KO11-QM-28  2025수능 미적분 28번
  H261-NA03-QM-28  2026 3월모의 28번
  M263-JS04-WM-12  정자중 중3 4월(중간고사) 서술형
  E254-DJ05-QM-10  분당중 초5 5월 10번
  U231-XX00-QM-05  대학3학년 문제 5번
============================================================
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------
# 마스터 코드
# ---------------------------------------------------------------

COURSE_CODES = {
    'E': '초등', 'M': '중등', 'H': '고등', 'U': '대학전공'
}

# 과정별 허용 학년 숫자
COURSE_GRADE_RANGE = {
    'E': set('123456'),
    'M': set('123'),
    'H': set('123'),
    'U': set('1234'),
}

SUBJECT_CODES = {
    '0': '구분없음',
    '1': '1학년',
    '2': '2학년',
    '3': '3학년',
    '4': '4학년',   # 초등4 / 대학4
    '5': '5학년',   # 초등5
    '6': '6학년',   # 초등6
    'A': '대수',
    'G': '기하',
    'C': '미적분',
    'S': '확률과통계',
    'I': '수학1',
    'Z': '수학2',
}

# 고등 전용 선택과목 코드 (학년 숫자 외)
H_SUBJECT_ONLY = set('AGCSIZ')

# 구버전 grade 4/5/6 -> v3 과목코드 (마이그레이션용, H과정 전용)
LEGACY_H_GRADE_MAP = {'4': 'S', '5': 'C', '6': 'G'}

SOURCE_CODES = {
    # 국가 시험
    'KO': ('국가수능',     'exam'),
    'NA': ('모의고사',     'exam'),
    'ED': ('교육청',       'exam'),
    # 고등학교
    'YD': ('영동고',       'school'),
    'NS': ('낙생고',       'school'),
    'DM': ('디미고',       'school'),
    'SM': ('성남외고',     'school'),
    'SH': ('서현고',       'school'),
    'BH': ('백현고',       'school'),
    # 중학교
    'DJ': ('분당중',       'school'),
    'SN': ('수내중',       'school'),
    'JJ': ('정자중',       'school'),
    'JS': ('정자중(신)',   'school'),
    'HS': ('한솔중',       'school'),
    'SC': ('신촌중',       'school'),
    'BJ': ('보정중',       'school'),
    'SL': ('신릉중',       'school'),
    'BG': ('불곡중',       'school'),
    'SY': ('상현중',       'school'),
    'SB': ('성북중',       'school'),
    # 출판·교재
    'BS': ('EBS',          'publisher'),
    'SS': ('신사고',       'publisher'),
    # 대회
    'KM': ('KMO',          'competition'),
    # 기타
    'PR': ('학교프린트',   'school'),
    'AR': ('공군',         'military'),
    'AM': ('육군',         'military'),
    'TO': ('원장저작권',   'own'),
    'TF': ('저작권프리',   'own'),
}

# BLOCK2 7~8번: 시험 월 (01~12) + 00=구분없음
MONTH_LABELS = {
    '00': '구분없음',
    '01': '1월',  '02': '2월',  '03': '3월',
    '04': '4월',  '05': '5월',  '06': '6월',
    '07': '7월',  '08': '8월',  '09': '9월',
    '10': '10월', '11': '11월(수능)', '12': '12월',
}

DATA_TYPE_CODES = {
    'Q': ('객관식/단답형 문제', False, False),
    'S': ('객관식/단답형 해설', True,  False),
    'W': ('서술형/논술형 문제', False, True),
    'A': ('서술형/논술형 해설', True,  True),
}

SUB_TYPE_CODES = {
    'M': '교사용 마스터 해설',
    'A': '풀이 시리즈 A',
    'B': '풀이 시리즈 B',
    'C': '풀이 시리즈 C',
    'X': '학생 오답률 데이터',
    '0': '기본',
}

# v3.1 패턴
# BLOCK1 4번째: [0-6AGCSIZ]  (초등1~6, 중/고1~3, 대학1~4, 선택과목 A/G/C/S/I/Z, 0=없음)
# BLOCK2 후반: \d{2}  (00~12 월, 또는 TO/TF)
ID_PATTERN = re.compile(
    r'^([EMHU])(\d{2})([0-6AGCSIZ])-([A-Z]{2})(\d{2}|[A-Z]{2})-([QSWA])([MABCX0])-(\d{2})$'
)

# 구버전 패턴 (grade 4/5/6을 고등 선택과목으로 쓰던 v2)
ID_PATTERN_LEGACY = re.compile(
    r'^([EMHU])(\d{2}|[A-Z]{2})(\d)-([A-Z]{2})(\d{2}|[A-Z]{2})-([QSWA])([MABCX0])-(\d{2})$'
)


# ---------------------------------------------------------------
# 파싱 결과
# ---------------------------------------------------------------

@dataclass
class ParsedID:
    raw: str
    course: str = ''
    year: Optional[int] = None
    subject_code: str = ''       # '1'~'6' / A/G/C/S/I/Z / '0'
    source_code: str = ''
    spec_raw: str = ''           # 원본 2자리
    exam_month: Optional[int] = None
    is_student_exam: bool = False
    student_code: Optional[str] = None
    data_type: str = ''
    sub_type: str = ''
    is_solution: bool = False
    is_essay: bool = False
    is_teacher_only: bool = False
    problem_number: int = 0
    # 레이블
    course_label: str = ''
    subject_label: str = ''
    source_label: str = ''
    data_type_label: str = ''
    sub_type_label: str = ''
    spec_label: str = ''
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def is_valid(self):
        return len(self.errors) == 0

    @property
    def grade_num(self):
        if self.subject_code.isdigit():
            return int(self.subject_code)
        return 0

    def human_readable(self):
        parts = []
        parts.append(f"{self.course_label}({self.course})")
        if self.year:
            parts.append(f"{self.year}년도")
        if self.subject_label:
            parts.append(self.subject_label)
        if self.is_student_exam and self.student_code:
            parts.append(f"{self.student_code} 학생용")
        if self.spec_label and self.spec_label != '구분없음':
            parts.append(self.spec_label)
        parts.append(self.data_type_label)
        if self.sub_type_label and self.sub_type_label != '기본':
            parts.append(f"[{self.sub_type_label}]")
        parts.append(f"{self.problem_number:02d}번")
        return " / ".join(parts)


# ---------------------------------------------------------------
# 파서
# ---------------------------------------------------------------

def parse_id(raw_id):
    p = ParsedID(raw=raw_id)
    cleaned = raw_id.strip().upper()
    m = ID_PATTERN.match(cleaned)

    # 구버전 H과정 grade 4/5/6 자동 마이그레이션
    if not m:
        m_leg = ID_PATTERN_LEGACY.match(cleaned)
        if m_leg:
            course, domain_raw, grade, src, spec, dtype, subtype, num = m_leg.groups()
            if course == 'H' and domain_raw.isdigit() and grade in LEGACY_H_GRADE_MAP:
                new_id = build_id(course, domain_raw, LEGACY_H_GRADE_MAP[grade],
                                  src, spec, dtype, subtype, int(num))
                p.warnings.append(f"구버전 자동변환: {raw_id} -> {new_id}")
                return parse_id(new_id)
        p.errors.append(f"ID 형식 불일치: '{raw_id}' (예: H25S-KO11-QM-28)")
        return p

    course, year2, subj, src, spec, dtype, subtype, num = m.groups()

    # 구버전 H과정 grade 4/5/6 → 선택과목 코드 자동 변환 (새 패턴에도 매칭됨)
    if course == 'H' and subj in LEGACY_H_GRADE_MAP:
        new_subj = LEGACY_H_GRADE_MAP[subj]
        new_id = build_id(course, year2, new_subj, src, spec, dtype, subtype, int(num))
        p.warnings.append(f"구버전 자동변환: {raw_id} -> {new_id} (grade {subj} -> {new_subj})")
        return parse_id(new_id)

    # BLOCK 1
    p.course        = course
    p.year          = 2000 + int(year2)
    p.subject_code  = subj
    p.course_label  = COURSE_CODES.get(course, course)
    p.subject_label = SUBJECT_CODES.get(subj, subj)

    # 과정별 학년 유효성 검사
    allowed = COURSE_GRADE_RANGE.get(course, set())
    if subj.isdigit() and subj != '0':
        if subj not in allowed:
            p.errors.append(
                f"{COURSE_CODES.get(course, course)} 과정에서 {subj}학년은 유효하지 않습니다. "
                f"허용: {sorted(allowed)}"
            )
    elif subj in H_SUBJECT_ONLY and course != 'H':
        p.warnings.append(
            f"선택과목 코드 '{subj}'({SUBJECT_CODES[subj]})는 고등(H) 전용입니다."
        )

    # BLOCK 2
    p.source_code = src
    p.spec_raw    = spec

    if src in SOURCE_CODES:
        p.source_label    = SOURCE_CODES[src][0]
        p.is_student_exam = False
    else:
        p.student_code    = src
        p.source_label    = f"{src} 학생 개인시험지"
        p.is_student_exam = True

    # 월 파싱 (01~12) + 00 + TO/TF
    if spec.isdigit():
        spec_int = int(spec)
        if spec_int == 0:
            p.spec_label = '구분없음'
        elif 1 <= spec_int <= 12:
            p.exam_month = spec_int
            p.spec_label = MONTH_LABELS.get(spec, f"{spec_int}월")
        else:
            p.errors.append(f"월 코드 범위 오류: '{spec}' (01~12 또는 00)")
    elif spec in ('TO', 'TF'):
        p.spec_label = '원장저작권' if spec == 'TO' else '저작권프리'
    else:
        p.spec_label = spec

    # BLOCK 3
    p.data_type = dtype
    p.sub_type  = subtype
    if dtype in DATA_TYPE_CODES:
        label, p.is_solution, p.is_essay = DATA_TYPE_CODES[dtype]
        p.data_type_label = label
    else:
        p.errors.append(f"알 수 없는 데이터 타입: '{dtype}'")

    p.sub_type_label  = SUB_TYPE_CODES.get(subtype, subtype)
    p.is_teacher_only = (subtype == 'M')
    p.problem_number  = int(num)

    return p


# ---------------------------------------------------------------
# ID 생성기
# ---------------------------------------------------------------

def build_id(course, year2, subject,
             source_or_student, month_or_spec,
             data_type, sub_type, problem_num):
    """
    12자리 ID 생성 (v3.1)
    month_or_spec: '00'~'12' (월) 또는 'TO'/'TF'
    """
    b1 = f"{course.upper()}{year2}{subject.upper()}"
    b2 = f"{source_or_student.upper()}{month_or_spec}"
    b3 = f"{data_type.upper()}{sub_type.upper()}"
    b4 = f"{problem_num:02d}"
    return f"{b1}-{b2}-{b3}-{b4}"


def legacy_to_new_id(legacy_id, data_type='Q', sub_type='M'):
    """
    레거시 ID (2025_수능_고3_확통_028) -> v3.1 ID

    예:
      2025_수능_고3_001      -> H253-KO11-QM-01
      2025_수능_고3_확통_028 -> H25S-KO11-QM-28
      2025_수능_고3_미적_028 -> H25C-KO11-QM-28
      2026_3월_고3_001       -> H263-NA03-QM-01
    """
    parts = legacy_id.split('_')
    year2  = str(parts[0])[-2:]
    source = 'KO'
    month  = '11'   # 수능 기본값 11월
    grade  = '3'

    if '모의' in legacy_id or '모고' in legacy_id:
        source = 'NA'
        # 월 추출 시도
        for part in parts:
            if part.endswith('월') and part[:-1].isdigit():
                month = f"{int(part[:-1]):02d}"
                break
        else:
            month = '00'
    elif '교육청' in legacy_id:
        source = 'ED'
        month  = '00'

    for part in parts:
        if part.startswith('고') and len(part) == 2:
            grade = part[1]
        elif part.startswith('중') and len(part) == 2:
            grade = part[1]

    SUBJECT_MAP = [
        ('확률과통계', 'S'), ('확통', 'S'),
        ('미적분', 'C'), ('미적', 'C'),
        ('기하', 'G'),
        ('수학1', 'I'), ('수1', 'I'),
        ('수학2', 'Z'), ('수2', 'Z'),
        ('대수', 'A'),
    ]
    subject = grade
    for keyword, code in SUBJECT_MAP:
        if keyword in legacy_id:
            subject = code
            break

    num = int(parts[-1]) if parts[-1].isdigit() else 0
    return build_id('H', year2, subject, source, month, data_type, sub_type, num)


def validate_id(raw_id):
    p = parse_id(raw_id)
    return p.is_valid, p.errors


# ---------------------------------------------------------------
# CLI 테스트
# ---------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 68)
    print("ID Manager v3.1 -- 학년 확장 + 월(01~12) 시험 코드")
    print("=" * 68)

    test_cases = [
        # 고등 수능
        ("H25S-KO11-QM-28", "2025수능(11월) 확통 28번"),
        ("H26S-KO11-QM-28", "2026수능(11월) 확통 28번"),
        ("H25C-KO11-QM-28", "2025수능 미적분 28번"),
        ("H25G-KO11-QM-28", "2025수능 기하 28번"),
        ("H25I-KO11-QM-05", "2025수능 수학1 5번"),
        ("H25Z-KO11-QM-08", "2025수능 수학2 8번"),
        ("H25A-KO11-QM-10", "2025수능 대수 10번"),
        ("H253-KO11-QM-15", "2025수능 고3 공통 15번"),
        # 모의고사
        ("H261-NA03-QM-28", "2026 3월모의 28번"),
        ("H263-NA06-QM-15", "2026 6월모의 15번"),
        ("H263-NA09-QM-21", "2026 9월모의 21번"),
        # 중학교 내신
        ("M263-JS04-WM-12", "정자중(신) 중3 4월(중간고사) 서술형"),
        ("M263-SN07-QM-05", "수내중 중3 7월(1학기기말) 5번"),
        ("M262-BG10-QM-08", "불곡중 중2 10월(중간고사) 8번"),
        ("M261-SY12-QM-10", "상현중 중1 12월(2학기기말) 10번"),
        # 초등 (1~6학년)
        ("E254-DJ05-QM-10", "분당중 초5 5월 10번"),
        ("E231-PR04-QM-03", "학교프린트 초3 4월 3번"),
        ("E266-BS00-QM-15", "EBS 초6 교재 15번"),
        # 대학
        ("U231-TO00-QM-05", "원장저작권 대학3학년 5번"),
        ("U241-AM00-QM-10", "육군 대학4학년 10번"),
        # 학생 개인
        ("H25S-JH11-SM-01", "정호학생 수능(11월) 확통 교사용"),
    ]

    for tid, desc in test_cases:
        p = parse_id(tid)
        status = "OK  " if p.is_valid else "FAIL"
        print(f"\n  [{status}] {tid}  ({desc})")
        if p.is_valid:
            print(f"         {p.human_readable()}")
            if p.warnings:
                for w in p.warnings:
                    print(f"         경고: {w}")
        else:
            for e in p.errors:
                print(f"         오류: {e}")

    print("\n" + "=" * 68)
    print("과정별 학년 유효성 검사")
    print("=" * 68)
    invalid_cases = [
        ("E274-DJ05-QM-01", "초등 7학년? (오류)"),
        ("M264-SN04-QM-01", "중학교 4학년? (오류)"),
        ("H265-KO11-QM-01", "고등 5학년? (오류)"),
        ("U255-TO00-QM-01", "대학 5학년? (오류)"),
        ("H25S-KO11-QM-01", "고등 확통 (정상)"),
        ("E256-DJ05-QM-01", "초등 6학년 (정상)"),
        ("U241-TO00-QM-01", "대학 4학년 (정상)"),
    ]
    for tid, desc in invalid_cases:
        p = parse_id(tid)
        result = "OK" if p.is_valid else "BLOCKED"
        print(f"  [{result:7s}] {tid}  {desc}")
        if not p.is_valid:
            for e in p.errors:
                print(f"             -> {e}")

    print("\n" + "=" * 68)
    print("레거시 -> v3.1 변환")
    print("=" * 68)
    cases = [
        ("2025_수능_고3_001",      "H253-KO11-QM-01"),
        ("2025_수능_고3_확통_028", "H25S-KO11-QM-28"),
        ("2025_수능_고3_미적_028", "H25C-KO11-QM-28"),
        ("2025_수능_고3_기하_028", "H25G-KO11-QM-28"),
        ("2026_수능_고3_확통_028", "H26S-KO11-QM-28"),
    ]
    all_ok = True
    for lid, expected in cases:
        got = legacy_to_new_id(lid)
        ok = "OK  " if got == expected else "FAIL"
        if got != expected:
            all_ok = False
        print(f"  [{ok}] {lid:35s} -> {got}")
    print(f"\n  결과: {'전체 통과!' if all_ok else '일부 실패'}")

    print("\n" + "=" * 68)
    print("구버전 H grade 4/5/6 자동 마이그레이션")
    print("=" * 68)
    for old in ["H254-KO11-QM-28", "H255-KO11-QM-28",
                "H256-KO11-QM-28", "H264-KO11-QM-28"]:
        p = parse_id(old)
        print(f"  {old} -> {p.raw}  ({'OK' if p.is_valid else 'FAIL'})")

    print("\n" + "=" * 68)
    print("시험 월 코드 전체")
    print("=" * 68)
    for k, v in sorted(MONTH_LABELS.items()):
        usage = ""
        if k == '00': usage = " (교재/연습용)"
        elif k == '03': usage = " (3월 모의)"
        elif k == '06': usage = " (6월 모의)"
        elif k == '07': usage = " (1학기 기말)"
        elif k == '09': usage = " (9월 모의)"
        elif k == '10': usage = " (2학기 중간)"
        elif k == '11': usage = " (수능)"
        elif k == '12': usage = " (2학기 기말)"
        print(f"  {k} -> {v}{usage}")
