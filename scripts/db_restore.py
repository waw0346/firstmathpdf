#!/usr/bin/env python3
"""
db_restore.py — DB 스냅샷 관리 & 복원 시스템
수학의 지름길 학원 LLM-Wiki

사용법:
  python3 scripts/db_restore.py --list
  python3 scripts/db_restore.py --snapshot "작업설명"
  python3 scripts/db_restore.py --restore snap_20260530_090758_v1.db
  python3 scripts/db_restore.py --date 2026-05-30
"""
import sqlite3, shutil, sys, re, argparse
from pathlib import Path
from datetime import datetime, date

BASE   = Path(__file__).parent.parent
DB     = BASE / "db" / "problems.db"
SNAP   = BASE / "db" / "snapshots"
LOG    = BASE / "DBTASKLOG.md"
ADMIN_PIN = "cp"   # 관리자 확인 키워드 (확장 가능)

SNAP.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────
def admin_confirm(action: str) -> bool:
    """관리자 확인 절차"""
    print(f"\n⚠️  '{action}' 작업은 관리자 확인이 필요합니다.")
    print("관리자(cp) 이니셜을 입력하세요: ", end="")
    inp = input().strip().lower()
    if inp != ADMIN_PIN:
        print("❌ 인증 실패. 작업이 취소됐습니다.")
        return False
    print("✅ 관리자 인증 완료")
    return True

# ──────────────────────────────────────────────────────────────
def get_db_info(db_path: Path) -> dict:
    """DB 기본 정보 조회"""
    try:
        conn = sqlite3.connect(str(db_path))
        n = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        ans_ok = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE answer!='' AND answer IS NOT NULL"
        ).fetchone()[0]
        img_ok = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE crop_path!='' AND crop_path IS NOT NULL"
        ).fetchone()[0]
        conn.close()
        return {"total": n, "answers": ans_ok, "images": img_ok}
    except Exception as e:
        return {"total": 0, "answers": 0, "images": 0, "error": str(e)}

# ──────────────────────────────────────────────────────────────
def list_snapshots():
    """스냅샷 목록 출력"""
    snaps = sorted(SNAP.glob("snap_*.db"), reverse=True)
    if not snaps:
        print("스냅샷 없음")
        return
    print(f"\n{'파일명':55} {'날짜':17} {'문제수':6} {'크기':8}")
    print("─" * 92)
    for f in snaps:
        info = get_db_info(f)
        # 파일명에서 날짜 추출
        m = re.search(r'snap_(\d{8})_(\d{6})', f.name)
        if m:
            d = m.group(1); t = m.group(2)
            dt_str = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}"
        else:
            dt_str = "?"
        sz = f"{f.stat().st_size // 1024}KB"
        print(f"  {f.name:53} {dt_str:17} {info['total']:6} {sz:8}")
    print(f"\n총 {len(snaps)}개 스냅샷")

# ──────────────────────────────────────────────────────────────
def make_snapshot(note: str) -> str:
    """현재 DB 스냅샷 생성"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    # 태그: 특수문자 제거, 공백→_
    tag = re.sub(r'[^\w가-힣]', '_', note)[:30]
    fname = f"snap_{ts}_{tag}.db"
    dest = SNAP / fname
    shutil.copy(str(DB), str(dest))
    info = get_db_info(dest)
    sz = dest.stat().st_size // 1024
    print(f"\n📸 스냅샷 생성 완료")
    print(f"   파일: {fname}")
    print(f"   문제: {info['total']}개 | 정답: {info['answers']}개 | 이미지: {info['images']}개")
    print(f"   크기: {sz}KB")
    _append_log(fname, note, info['total'], sz)
    return fname

# ──────────────────────────────────────────────────────────────
def restore_snapshot(fname: str):
    """스냅샷으로 복원"""
    snap_path = SNAP / fname
    if not snap_path.exists():
        print(f"❌ 스냅샷 없음: {fname}")
        sys.exit(1)

    info_snap = get_db_info(snap_path)
    info_cur  = get_db_info(DB)
    print(f"\n복원 정보:")
    print(f"  현재 DB: {info_cur['total']}문제")
    print(f"  복원 DB: {info_snap['total']}문제 ({fname})")

    if not admin_confirm(f"DB 복원 → {fname}"):
        sys.exit(1)

    # 현재 DB를 emergency 스냅샷으로 저장
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    emg = SNAP / f"snap_{ts}_BEFORE_RESTORE.db"
    shutil.copy(str(DB), str(emg))
    print(f"  💾 복원 전 현재 DB 자동저장: {emg.name}")

    # 복원
    shutil.copy(str(snap_path), str(DB))
    info_after = get_db_info(DB)
    print(f"\n✅ 복원 완료: {info_after['total']}문제")
    _append_log(fname, f"[RESTORE] {fname}으로 복원", info_after['total'],
                DB.stat().st_size // 1024)

# ──────────────────────────────────────────────────────────────
def restore_by_date(target_date: str):
    """날짜로 가장 가까운 스냅샷 찾아 복원"""
    snaps = sorted(SNAP.glob("snap_*.db"))
    candidates = []
    for f in snaps:
        m = re.search(r'snap_(\d{8})_(\d{6})', f.name)
        if m:
            d = m.group(1); t = m.group(2)
            dt = datetime.strptime(f"{d}{t}", "%Y%m%d%H%M%S")
            candidates.append((dt, f))

    if not candidates:
        print("❌ 복원 가능한 스냅샷 없음")
        sys.exit(1)

    target = datetime.strptime(target_date, "%Y-%m-%d")
    # 목표 날짜 이전 중 가장 최근
    before = [(dt, f) for dt, f in candidates if dt.date() <= target.date()]
    if not before:
        print(f"❌ {target_date} 이전 스냅샷 없음")
        print("사용 가능한 가장 오래된 스냅샷:")
        dt, f = candidates[0]
        print(f"  {f.name} ({dt.strftime('%Y-%m-%d %H:%M')})")
        sys.exit(1)

    dt, best = max(before, key=lambda x: x[0])
    print(f"✅ {target_date}에 가장 가까운 스냅샷: {best.name} ({dt.strftime('%Y-%m-%d %H:%M')})")
    restore_snapshot(best.name)

# ──────────────────────────────────────────────────────────────
def _append_log(fname: str, note: str, n_problems: int, size_kb: int):
    """DBTASKLOG.md 자동 업데이트"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not LOG.exists():
        return
    content = LOG.read_text(encoding='utf-8')
    # 스냅샷 목록 테이블에 행 추가
    new_row = f"| {fname} | {now} | {n_problems} | {size_kb}KB | {note} |\n"
    marker = "| 파일명 | 날짜 | 문제수 | 크기 | 설명 |"
    if marker in content:
        # 테이블 다음 줄(헤더+구분선) 이후에 삽입
        idx = content.find(marker)
        end = content.find('\n', idx)
        end2 = content.find('\n', end + 1)  # 구분선 줄 끝
        content = content[:end2+1] + new_row + content[end2+1:]
        LOG.write_text(content, encoding='utf-8')

# ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='DB 스냅샷 관리')
    parser.add_argument('--list',    action='store_true', help='스냅샷 목록')
    parser.add_argument('--snapshot',metavar='NOTE',      help='스냅샷 생성')
    parser.add_argument('--restore', metavar='FILENAME',  help='파일명으로 복원')
    parser.add_argument('--date',    metavar='YYYY-MM-DD',help='날짜로 복원')
    args = parser.parse_args()

    if args.list:
        list_snapshots()
    elif args.snapshot:
        make_snapshot(args.snapshot)
    elif args.restore:
        restore_snapshot(args.restore)
    elif args.date:
        restore_by_date(args.date)
    else:
        parser.print_help()
        print("\n현재 DB 정보:")
        info = get_db_info(DB)
        print(f"  문제: {info['total']}개 | 정답: {info['answers']}개 | 이미지: {info['images']}개")
        print(f"\n스냅샷 수: {len(list(SNAP.glob('snap_*.db')))}개")

if __name__ == "__main__":
    main()
