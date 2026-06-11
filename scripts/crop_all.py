#!/usr/bin/env python3
"""
crop_all.py — 수학 문제 PDF 크롭 스크립트 (v19 최종)
수학의 지름길 학원 LLM-Wiki

사용법:
    python3 scripts/crop_all.py            # 전체 크롭
    python3 scripts/crop_all.py 2026       # 특정 연도만
    python3 scripts/crop_all.py 2025 수능  # 특정 연도·시험만

주요 알고리즘:
    1. PDF 텍스트 좌표로 문제 번호 위치 자동 탐지
    2. L/R 컬럼 자동 분리 (mid_x = 0.48 * 페이지너비)
    3. 하단: PDF 텍스트·도형 기반 실제 내용 끝 탐지
       - 관리 텍스트(확인사항·답안지) 동적 감지·제외
       - L컬럼에서 x0>mid_x 텍스트/도형 제외 (R컬럼 블리드 방지)
       - 도형은 last_text+200pt 이내만 포함 (답안지 그리드 제외)
    4. 상단: 구분선·이전문제 제거 (top_pad=25px)
    5. 우측(L컬럼): cr = min(갭탐지, mid_x_px) 강제 컷
    6. 수직 구분선 마스킹 (좌8%, 우12%)
    7. DPI=250 (고해상도)

수정 이력:
    v1-v11 : 기본 구현, 컬럼 분리
    v12-v13 : 상단 여백, 이전문제 블리드
    v14-v16 : PDF 기반 하단 탐지, 확인사항 제거
    v17-v18 : L/R컬럼 구분 필터 추가
    v19     : trim_right cr=min(갭,mid_x_px) 강제 컷
"""

import sys
import fitz
import re
import io
import shutil
import tempfile
from pathlib import Path
from PIL import Image
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 기본 설정 ─────────────────────────────────────────────────────
BASE      = Path(__file__).parent.parent
FINAL     = BASE / "sources" / "crops"
FINAL.mkdir(parents=True, exist_ok=True)

DPI            = 250          # 출력 해상도
HEADER_Y       = 160          # 페이지 상단 헤더 제외 기준 (pt)
FOOTER_Y       = 1075         # 하단 footer 제외 기준 (pt) — 페이지번호 박스=1082pt
DRAWING_RANGE  = 200          # 텍스트 끝 이후 도형 포함 범위 (pt)
TOP_PAD_PT     = 30           # 문제 번호·윗첨자 포함용 상단 여백 (pt) [v20: 12→30]
BOTTOM_PAD_PX  = 40           # 마지막 내용 이후 하단 여백 (px)
MID_RATIO      = 0.48         # 좌/우 컬럼 구분선 비율
MG_L_RATIO     = 0.015        # 좌측 여백 비율
XE_L_EXTRA     = 60           # L컬럼 우측 여유 (pt) — 정규분포표 등 포함용
SUBJ_PAGES     = {            # 선택과목 페이지 범위 (0-based)
    "확통":   (8, 11),
    "미적분": (12, 15),
    "기하":   (16, 19),
}

# 관리 텍스트 키워드 — 이 텍스트 이하는 문제 내용 아님
ADMIN_KW = [
    "확인 사항", "담안지", "선택과목", "이어서",
    "저작권", "선택한 과목", "이 문제지에 관한"
]


# ── 이미지 처리 함수 ──────────────────────────────────────────────

def mask_vlines(g: np.ndarray) -> np.ndarray:
    """좌·우 수직 구분선 픽셀을 흰색으로 마스킹
    ★ <128 (안티앨리어싱 포함) 임계값으로 회색 선도 제거"""
    h, w = g.shape
    masked = g.copy()
    # 오른쪽 12% — 열 30% 이상 어두우면 수직선 (안티앨리어싱 포함)
    for x in range(int(w * 0.88), w):
        if (g[:, x] < 150).sum() / h > 0.30:
            masked[:, x] = 255
    # 왼쪽 8%
    for x in range(0, int(w * 0.08)):
        if (g[:, x] < 150).sum() / h > 0.30:
            masked[:, x] = 255
    return masked


def trim_top(img: Image.Image, top_pad: int = 15) -> Image.Image:
    """상단 구분선·흰줄 제거 후 top_pad 여백 확보 [v20: 25→15]"""
    g = np.array(img.convert("L"))
    h, w = g.shape
    top = 0
    for y in range(min(60, h)):  # 스캔 범위 축소: 80→60 (이미 TOP_PAD_PT=30으로 여유 있음)
        rm = g[y].mean()
        df = (g[y] < 80).sum() / w
        if rm > 247:    # 흰줄
            top = y + 1
        elif df > 0.45: # 수평 구분선
            top = y + 1
        else:
            break
    return img.crop((0, max(0, top - top_pad), img.width, h))


def mask_top_hlines(img: Image.Image, scan_px: int = 35) -> Image.Image:
    """상단에 남은 페이지 구분 수평선을 흰색으로 마스킹한다."""
    arr = np.array(img)
    g = np.array(img.convert("L"))
    h, w = g.shape
    for y in range(min(scan_px, h)):
        if (g[y] < 80).sum() / w > 0.45:
            y0 = max(0, y - 1)
            y1 = min(h, y + 3)
            arr[y0:y1, :] = 255
    return Image.fromarray(arr)


def trim_right_col(img: Image.Image, mid_x_px: int) -> Image.Image:
    """
    L컬럼 전용 우측 트림:
    1. 흰공백(≥30px) 탐지로 R컬럼 블리드 제거
    2. cr = min(갭탐지, mid_x_px) → 항상 mid_x 이하 강제 컷
    """
    gm = mask_vlines(np.array(img.convert("L")))
    h, w = gm.shape
    cm = gm.mean(axis=0)
    cr = w
    in_white = False
    white_start = w
    for x in range(w - 1, w // 2, -1):
        if cm[x] > 248:
            if not in_white:
                in_white = True
                white_start = x
        else:
            if in_white:
                if white_start - x >= 30:
                    cr = x + 1
                    break
            in_white = False
    # ★ 핵심: 항상 mid_x_px 이하로 강제 제한
    cr = min(cr, mid_x_px)
    return img.crop((0, 0, min(w, cr + 12), h))


# ── PDF 분석 함수 ─────────────────────────────────────────────────

def get_admin_y(page: fitz.Page) -> float:
    """이 페이지에서 관리 텍스트(확인사항 등) 첫 등장 y 좌표 반환"""
    admin_y = float(FOOTER_Y)
    for b in page.get_text("blocks"):
        txt = str(b[4]).strip()
        if any(k in txt for k in ADMIN_KW):
            admin_y = min(admin_y, b[1])
    return admin_y


def get_last_content_y(doc: fitz.Document, pn: int,
                        clip: fitz.Rect, scale: float,
                        mid_x: float, is_L: bool) -> int:
    """
    클립 내 마지막 문제 내용 y좌표 (이미지 픽셀) 반환

    is_L=True : L컬럼 → x0>mid_x 텍스트·도형·이미지 제외 (R 블리드 방지)
    is_L=False: R컬럼 → x 필터 없음
    """
    page     = doc[pn]
    y0       = clip.y0
    admin_y  = get_admin_y(page)

    # 텍스트 기반 마지막 y
    last_text = y0
    for b in page.get_text("blocks", clip=clip):
        bx0, by0, bx1, by1, text = b[:5]
        if not str(text).strip() or by1 > admin_y:
            continue
        if by1 > clip.y1 + 5:  # ★ 클립 경계 넘는 다음 문제 텍스트 제외
            continue
        if is_L and bx0 > mid_x:  # L컬럼: R컬럼 텍스트 제외
            continue
        if by1 > last_text:
            last_text = by1

    # 도형 기반 (last_text + DRAWING_RANGE 이내)
    draw_limit = min(admin_y, last_text + DRAWING_RANGE)
    last = last_text
    for item in page.get_drawings():
        r = item["rect"]
        if r.y1 > draw_limit or r.y0 < clip.y0:
            continue
        if r.y1 > clip.y1 + 5:  # ★ 클립 경계 넘는 도형 제외
            continue
        if is_L and r.x0 > mid_x + 30:  # L컬럼: R컬럼 도형 제외
            continue
        if r.y1 > last:
            last = r.y1

    # 이미지 블록 기반: 그래프/도표/상자 그림은 get_drawings()에 잡히지 않는 경우가 많다.
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type") != 1:
            continue
        bx0, by0, bx1, by1 = b.get("bbox")
        if by1 > admin_y or by0 < clip.y0:
            continue
        if by1 > clip.y1 + 5:
            continue
        if bx1 < clip.x0 or bx0 > clip.x1:
            continue
        if is_L and bx0 > mid_x + 30:
            continue
        if by1 > last:
            last = by1

    return max(0, int((last - y0) * scale))


def get_problem_positions(doc: fitz.Document,
                           page_range: tuple,
                           num_filter=None) -> list:
    """PDF에서 문제 번호 위치 목록 반환 [(num, pn, x0, y0, col), ...]
    
    v20 개선: 같은 라인의 모든 텍스트(단원명, 난이도 등)를 포함해서
    문제 번호 앞뒤의 메타정보도 함께 클립 범위에 포함
    """
    mid_x  = doc[0].rect.width * MID_RATIO
    probs  = []
    for pn in range(page_range[0], page_range[1] + 1):
        for b in doc[pn].get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    m = re.match(r'^(\d{1,2})\.\s*$', span["text"].strip())
                    if m:
                        num = int(m.group(1))
                        if num_filter and num not in num_filter:
                            continue
                        x0, y0 = span["bbox"][0], span["bbox"][1]
                        if y0 < HEADER_Y:
                            continue
                        col = "L" if x0 < mid_x else "R"
                        
                        # ★ v20: 같은 라인(line) 내 모든 span의 최소 y0 찾기
                        # → 윗첨자, 분수, 단원명, 난이도 등 모두 포함
                        effective_y0 = y0
                        for s in line["spans"]:
                            if str(s.get("text", "")).strip():
                                sy0 = s["bbox"][1]
                                effective_y0 = min(effective_y0, sy0)
                        
                        probs.append((num, pn, x0, effective_y0, col))
    seen = {}
    for p in probs:
        if p[0] not in seen:
            seen[p[0]] = p
    return sorted(seen.values(), key=lambda x: x[0])


# ── 크롭 실행 함수 ────────────────────────────────────────────────

def crop_and_save(doc: fitz.Document, probs: list,
                  prefix: str, subj: str = "") -> dict:
    """문제 목록을 크롭해서 파일 저장, {num: crop_path} 반환"""
    w_pt  = doc[0].rect.width
    h_pt  = doc[0].rect.height
    mid_x = w_pt * MID_RATIO
    mg_l  = w_pt * MG_L_RATIO
    scale = DPI / 72
    mat   = fitz.Matrix(scale, scale)
    saved = {}

    for i, (num, pn, x0n, y0n, col) in enumerate(probs):
        # 다음 같은 컬럼 문제의 y (하단 경계)
        ny = h_pt * 0.975
        for j in range(i + 1, len(probs)):
            if probs[j][1] == pn and probs[j][4] == col:
                ny = probs[j][3] - 4
                break

        is_L = (col == "L")
        xs   = mg_l           if is_L else (mid_x + mg_l)
        xe   = mid_x + XE_L_EXTRA if is_L else (w_pt - 3)

        # 클립 상단: 문제 번호 및 메타정보(단원명, 난이도) 포함 [v20: 30pt 여유]
        clip = fitz.Rect(xs, max(0, y0n - TOP_PAD_PT), xe, min(h_pt, ny))

        # PDF 기반 마지막 내용 y 계산
        last_px = get_last_content_y(doc, pn, clip, scale, mid_x, is_L)
        clip_h  = int((clip.y1 - clip.y0) * scale)
        crop_h  = max(80, min(clip_h, last_px + BOTTOM_PAD_PX))

        # 픽스맵 생성 및 크롭
        pix = doc[pn].get_pixmap(matrix=mat, clip=clip, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = img.crop((0, 0, img.width, min(img.height, crop_h)))
        img = trim_top(img)
        img = mask_top_hlines(img)

        # 좌측 수직선 제거 (L·R 공통)
        g = np.array(img.convert("L"))
        gm = mask_vlines(g)
        # 좌측 8% 마스킹 적용
        img_arr = np.array(img)
        # ★ <150, 30% (안티앨리어싱 완전 제거)
        for x in range(int(img.width * 0.08)):
            if (g[:, x] < 150).sum() / img.height > 0.30:
                img_arr[:, x] = 255
        img = Image.fromarray(img_arr)

        # L컬럼: 우측 트림 (R블리드 차단)
        if is_L:
            mid_x_px = int((mid_x - xs) * scale)
            img = trim_right_col(img, mid_x_px)

        # 저장
        label = f"_{subj}_{num:03d}" if subj else f"_{num:03d}"
        fname = f"{prefix}{label}.jpg"
        tmp   = Path(tempfile.gettempdir()) / fname
        img.save(str(tmp), quality=96)
        shutil.copy(str(tmp), str(FINAL / fname))

        saved[num] = f"sources/crops/{fname}"

    return saved


# ── 메인 실행 ─────────────────────────────────────────────────────

def run(year_filter=None, exam_filter=None):
    """
    year_filter : None(전체) 또는 정수(예: 2025)
    exam_filter : None(전체) 또는 "수능"/"10월" 등
    """
    years = [2025, 2026] if year_filter is None else [int(year_filter)]

    for year in years:
        src = BASE / "sources" / str(year)
        if not src.exists():
            print(f"⚠️  sources/{year}/ 없음, 건너뜀")
            continue

        # 수능
        for pdf_path in src.glob(f"{year}수능_수학문제.pdf"):
            if exam_filter and exam_filter not in "수능":
                continue
            pfx = f"{year}_수능_고3"
            print(f"\n[{year}수능] 공통 1-22번 크롭...")
            doc = fitz.open(str(pdf_path))
            crop_and_save(doc, get_problem_positions(doc, (0, 7)), pfx)

            for subj, pages in SUBJ_PAGES.items():
                print(f"[{year}수능] {subj} 23-30번 크롭...")
                probs = get_problem_positions(doc, pages,
                                              num_filter=range(23, 31))
                crop_and_save(doc, probs, pfx, subj)
            doc.close()
            print(f"✅ [{year}수능] 완료")

        # 모의고사 (전국연합 + 수능 모의평가)
        _seen=set()
        _mock_pdfs=(list(src.glob("*전국연합*문제지*.pdf"))+
                    list(src.glob("*전국연합*문제.pdf"))+
                    list(src.glob("*모의평가*문제지*.pdf"))+
                    list(src.glob("*모의평가*수학 문제*.pdf")))
        for pdf_path in _mock_pdfs:
            if pdf_path in _seen: continue
            _seen.add(pdf_path)
            n=pdf_path.name
            if "10월" in n: month="10월"
            elif "5월" in n: month="5월"
            elif "6월" in n: month="6월"
            elif "9월" in n: month="9월"
            else: month="모의"
            if exam_filter and exam_filter not in month:
                continue
            pfx = f"{year}_{month}모의_고3"
            print(f"\n[{year} {month}모의] 공통 1-22번 크롭...")
            doc = fitz.open(str(pdf_path))
            crop_and_save(doc, get_problem_positions(doc, (0, 7)), pfx)

            for subj, pages in SUBJ_PAGES.items():
                print(f"[{year} {month}모의] {subj} 23-30번 크롭...")
                probs = get_problem_positions(doc, pages,
                                              num_filter=range(23, 31))
                crop_and_save(doc, probs, pfx, subj)
            doc.close()
            print(f"✅ [{year} {month}모의] 완료")

    print("\n✅ 전체 크롭 완료 (v19)")


if __name__ == "__main__":
    year_arg  = sys.argv[1] if len(sys.argv) > 1 else None
    exam_arg  = sys.argv[2] if len(sys.argv) > 2 else None
    run(year_filter=year_arg, exam_filter=exam_arg)
