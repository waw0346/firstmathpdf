#!/usr/bin/env python3
"""
id_manager_v4.py — 수학 문제 파일 명명 시스템 v4.0
수학의 지름길 학원

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
파일 유형별 형식:
  ① 수능·모의    : H[연도2][월2]-[출처2]
  ② 학교 내신   : H[학년][연도2][월2]-[지역2][학교한글2]
  ③ 학생 맞춤   : H[학년][연도2][월2]-[지역2][학교한글2]_[이름]_[용도]
  ④ 개념 파일   : [종류]-[학년]-[연도2]-[과목]
  ⑤ 경시대회    : H[학년]-[연도2]-[대회코드]

사용법:
  python3 scripts/id_manager_v4.py --type exam   --year 2025 --month 11 --source SU
  python3 scripts/id_manager_v4.py --type school --year 2026 --month 6  --grade 1 --region SN --school 성남외
  python3 scripts/id_manager_v4.py --type student --year 2026 --month 6 --grade 2 --region SN --school 성남외 --name 진우 --purpose 기말
  python3 scripts/id_manager_v4.py --type concept --year 2026 --grade H2 --subject A --kind CON
  python3 scripts/id_manager_v4.py --parse "H22606-SN성남외_진우_기말"
  python3 scripts/id_manager_v4.py --list-codes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import re
import argparse
from dataclasses import dataclass
from typing import Optional

# ══════════════════════════════════════════════════════════════
# 코드 테이블
# ══════════════════════════════════════════════════════════════

SOURCE_CODES = {
    # 국가·공공기관
    "SU": "수능 (대학수학능력시험)",
    "NA": "전국연합학력평가",
    "EG": "EBS 연계 교재",
    # 경시대회·올림피아드
    "ST": "성대경시대회 (성균관대)",
    "KC": "KMC 한국수학경시대회",
    "KO": "한국수학올림피아드 (KMO)",
    "IO": "국제수학올림피아드 (IMO)",
    "AM": "AMC / AIME (미국)",
    "AP": "기타 경시대회",
    # 출판사·교재
    "EB": "EBS 교재",
    "IT": "이투스",
    "MG": "메가스터디",
    "JS": "수학의정석 (진수당)",
    "BL": "블랙라벨",
    "RP": "RPM",
    "SE": "쎈 (좋은책신사고)",
    "HA": "해법수학",
}

REGION_CODES = {
    "SN": "성남",  "BD": "분당",  "SW": "수원",
    "SE": "서울",  "YI": "용인",  "IN": "인천",
    "GY": "경기",  "BS": "부산",  "DG": "대구",
}

SUBJECT_CODES = {
    "P1": "공통1 (고1 1학기, 공통수학1)",
    "P2": "공통2 (고1 2학기, 공통수학2)",
    "A":  "대수 (Algebra, 舊 수학Ⅰ)",
    "C1": "미적분Ⅰ (Calculus I, 舊 수학Ⅱ)",
    "C2": "미적분Ⅱ (Calculus II, 심화선택)",
    "SS": "확률과통계 (Statistics)",
    "G":  "기하 (Geometry)",
}

CONCEPT_KINDS = {
    "CON": "개념 (Concept)",
    "FOR": "공식 (Formula)",
    "EXM": "예제 (Example)",
    "SUM": "요약 (Summary)",
}

PURPOSE_CODES = {
    "기말": "기말고사 대비",
    "중간": "중간고사 대비",
    "단원": "단원별 학습",
    "오답": "오답 정리",
    "취약": "취약 단원 집중",
    "모의": "모의고사 대비",
}

FILE_SUFFIX = {
    "_Q": "문제지 (Question)",
    "_A": "정답 (Answer)",
    "_S": "해설 (Solution)",
}

MONTH_NAMES = {
    "03": "3월모의", "04": "1학기중간", "05": "5월모의",
    "06": "6월모의평가", "07": "1학기기말", "09": "9월모의평가",
    "10": "10월모의",  "11": "수능·2학기중간", "12": "2학기기말",
    "00": "연도미상",
}


# ══════════════════════════════════════════════════════════════
# ID 생성 함수
# ══════════════════════════════════════════════════════════════

def make_exam_id(year: int, month: int, source: str) -> str:
    """① 수능·모의 파일 ID"""
    y = str(year)[-2:]
    m = f"{month:02d}"
    src = source.upper()
    if src not in SOURCE_CODES:
        raise ValueError(f"출처 코드 오류: {src}. 사용 가능: {list(SOURCE_CODES.keys())}")
    return f"H{y}{m}-{src}"


def make_school_id(year: int, month: int, grade: int,
                   region: str, school: str) -> str:
    """② 학교 내신 파일 ID"""
    y = str(year)[-2:]
    m = f"{month:02d}"
    reg = region.upper()
    sch = school  # 학교명 그대로 (2~3글자)
    if reg not in REGION_CODES:
        raise ValueError(f"지역 코드 오류: {reg}. 사용 가능: {list(REGION_CODES.keys())}")
    if grade not in [1, 2, 3]:
        raise ValueError("학년은 1, 2, 3 중 하나")
    return f"H{grade}{y}{m}-{reg}{sch}"


def make_student_id(year: int, month: int, grade: int,
                    region: str, school: str,
                    name: str, purpose: str) -> str:
    """③ 학생 맞춤 문제지 파일 ID"""
    base = make_school_id(year, month, grade, region, school)
    return f"{base}_{name}_{purpose}"


def make_concept_id(year: int, grade_str: str,
                    subject: str, kind: str = "CON") -> str:
    """④ 개념 파일 ID  (grade_str: H1, H2, HX, H13 등)"""
    y = str(year)[-2:]
    k = kind.upper()
    s = subject.upper()
    if k not in CONCEPT_KINDS:
        raise ValueError(f"개념 종류 오류: {k}. 사용 가능: {list(CONCEPT_KINDS.keys())}")
    if s not in SUBJECT_CODES:
        raise ValueError(f"과목 코드 오류: {s}. 사용 가능: {list(SUBJECT_CODES.keys())}")
    g = grade_str.upper()
    return f"{k}-{g}-{y}-{s}"


def make_competition_id(year: int, grade: int, source: str) -> str:
    """⑤ 경시대회 파일 ID"""
    y = str(year)[-2:]
    src = source.upper()
    if src not in SOURCE_CODES:
        raise ValueError(f"출처 코드 오류: {src}")
    return f"H{grade}-{y}-{src}"


def make_item_id(file_id: str, number: int,
                 item_type: str = "Q") -> str:
    """문제 항목 12자리 ID"""
    return f"{file_id}-{item_type}{number:03d}"


# ══════════════════════════════════════════════════════════════
# 파싱 함수
# ══════════════════════════════════════════════════════════════

def parse_id(code: str) -> dict:
    """파일 ID 또는 항목 ID를 파싱해서 의미 반환"""
    info = {"원본": code, "유형": "알 수 없음"}

    # ④ 개념 파일: CON-H2-26-A
    m = re.match(r'^(CON|FOR|EXM|SUM)-([A-Z0-9H]+)-(\d{2})-([A-Z0-9]+)$', code)
    if m:
        kind, grade, y, subj = m.groups()
        info.update({
            "유형": "개념파일",
            "종류": CONCEPT_KINDS.get(kind, kind),
            "학년": grade,
            "연도": f"20{y}",
            "과목": SUBJECT_CODES.get(subj, subj),
        })
        return info

    # ⑤ 경시대회: H3-26-KO
    m = re.match(r'^H([123])-(\d{2})-([A-Z]{2,3})$', code)
    if m:
        grade, y, src = m.groups()
        info.update({
            "유형": "경시대회",
            "학년": f"고{grade}",
            "연도": f"20{y}",
            "출처": SOURCE_CODES.get(src, src),
        })
        return info

    # 학생 맞춤: H22606-SN성남외_진우_기말
    m = re.match(r'^H([123])(\d{2})(\d{2})-([A-Z]{2})(.{2})_(.+)_(.+)$', code)
    if m:
        grade, y, month, region, school, name, purpose = m.groups()
        info.update({
            "유형": "학생맞춤",
            "학년": f"고{grade}",
            "연도": f"20{y}",
            "월": MONTH_NAMES.get(month, f"{month}월"),
            "지역": REGION_CODES.get(region, region),
            "학교": school,
            "학생": name,
            "용도": PURPOSE_CODES.get(purpose, purpose),
        })
        return info

    # 내신: H12506-SN성남외
    m = re.match(r'^H([123])(\d{2})(\d{2})-([A-Z]{2})(.{2})$', code)
    if m:
        grade, y, month, region, school = m.groups()
        info.update({
            "유형": "내신시험",
            "학년": f"고{grade}",
            "연도": f"20{y}",
            "월": MONTH_NAMES.get(month, f"{month}월"),
            "지역": REGION_CODES.get(region, region),
            "학교": school,
        })
        return info

    # 수능·모의: H2511-SU
    m = re.match(r'^H(\d{2})(\d{2})-([A-Z]{2,4})(-[A-Z]\d{3})?$', code)
    if m:
        y, month, src, item = m.groups()
        info.update({
            "유형": "수능·모의",
            "연도": f"20{y}",
            "월": MONTH_NAMES.get(month, f"{month}월"),
            "출처": SOURCE_CODES.get(src, src),
        })
        if item:
            info["항목"] = item.lstrip('-')
        return info

    return info


# ══════════════════════════════════════════════════════════════
# 유효성 검증
# ══════════════════════════════════════════════════════════════

def validate(code: str) -> tuple[bool, str]:
    """ID 유효성 검사 → (True/False, 메시지)"""
    parsed = parse_id(code)
    if parsed["유형"] == "알 수 없음":
        return False, f"인식 불가능한 형식: {code}"
    return True, f"✅ 유효 ({parsed['유형']})"


# ══════════════════════════════════════════════════════════════
# 코드표 출력
# ══════════════════════════════════════════════════════════════

def print_all_codes():
    print("\n" + "="*60)
    print("📋 수학 파일 명명 시스템 v4.0 — 전체 코드표")
    print("="*60)

    print("\n【출처 코드】")
    for k, v in SOURCE_CODES.items():
        print(f"  {k:4} = {v}")

    print("\n【지역 코드】")
    for k, v in REGION_CODES.items():
        print(f"  {k:4} = {v}")

    print("\n【과목 코드】")
    for k, v in SUBJECT_CODES.items():
        print(f"  {k:4} = {v}")

    print("\n【개념 파일 종류】")
    for k, v in CONCEPT_KINDS.items():
        print(f"  {k:4} = {v}")

    print("\n【파일 접미사】")
    for k, v in FILE_SUFFIX.items():
        print(f"  {k:4} = {v}")

    print("\n【파일 유형별 형식】")
    examples = [
        ("① 수능·모의",   "H[연도2][월2]-[출처2]",                       "H2511-SU"),
        ("② 학교내신",   "H[학년][연도2][월2]-[지역2][학교2]",            "H12506-SN성남외"),
        ("③ 학생맞춤",   "H[학년][연도2][월2]-[지역2][학교2]_[이름]_[용도]","H22606-SN성남외_진우_기말"),
        ("④ 개념파일",   "[종류]-[학년]-[연도2]-[과목]",                  "CON-H2-26-A"),
        ("⑤ 경시대회",   "H[학년]-[연도2]-[대회코드]",                    "H3-26-KO"),
    ]
    for name, fmt, example in examples:
        print(f"  {name:10} {fmt:42} 예) {example}")
    print()


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="수학 파일 명명 시스템 v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--type",    choices=["exam","school","student","concept","competition"])
    parser.add_argument("--year",    type=int, help="연도 (예: 2026)")
    parser.add_argument("--month",   type=int, help="월 (예: 6)")
    parser.add_argument("--grade",   type=int, help="학년 1/2/3")
    parser.add_argument("--grade-str", help="개념파일 학년 (H1/H2/HX/H13 등)")
    parser.add_argument("--source",  help="출처 코드 (SU/NA/ST/KO 등)")
    parser.add_argument("--region",  help="지역 코드 (SN/BD 등)")
    parser.add_argument("--school",  help="학교명 한글 2자리")
    parser.add_argument("--name",    help="학생 이름")
    parser.add_argument("--purpose", help="용도 (기말/중간/오답 등)")
    parser.add_argument("--subject", help="과목 코드 (A/C1/SS/G 등)")
    parser.add_argument("--kind",    default="CON", help="개념파일 종류 (CON/FOR/SUM)")
    parser.add_argument("--parse",   help="ID 파싱")
    parser.add_argument("--validate",help="ID 검증")
    parser.add_argument("--item",    type=int, help="항목 번호 (12자리 ID 생성)")
    parser.add_argument("--list-codes", action="store_true", help="전체 코드표 출력")
    args = parser.parse_args()

    if args.list_codes:
        print_all_codes()
        return

    if args.parse:
        info = parse_id(args.parse)
        print(f"\n파싱 결과: {args.parse}")
        for k, v in info.items():
            if k != "원본": print(f"  {k:8}: {v}")
        return

    if args.validate:
        ok, msg = validate(args.validate)
        print(f"{msg}: {args.validate}")
        return

    # ID 생성
    file_id = None
    try:
        if args.type == "exam":
            file_id = make_exam_id(args.year, args.month, args.source)
        elif args.type == "school":
            file_id = make_school_id(args.year, args.month, args.grade, args.region, args.school)
        elif args.type == "student":
            file_id = make_student_id(args.year, args.month, args.grade,
                                      args.region, args.school, args.name, args.purpose)
        elif args.type == "concept":
            gs = args.grade_str or f"H{args.grade}"
            file_id = make_concept_id(args.year, gs, args.subject, args.kind)
        elif args.type == "competition":
            file_id = make_competition_id(args.year, args.grade, args.source)

        if file_id:
            print(f"\n✅ 파일 ID: {file_id}")
            print(f"   문제지:  {file_id}_Q.pdf")
            print(f"   정답:    {file_id}_A.pdf")
            print(f"   해설:    {file_id}_S.pdf")
            if args.item:
                item_id = make_item_id(file_id, args.item)
                print(f"   항목ID:  {item_id}")
    except (ValueError, TypeError) as e:
        print(f"❌ 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print_all_codes()
    else:
        main()
