@echo off
echo ========================================
echo  Obsidian 검수 결과 → DB 반영
echo ========================================
cd /d "%~dp0"
python scripts\sync_from_obsidian.py
echo.
echo ========================================
echo  완료! Obsidian에서 00_VERIFY.md 확인
echo ========================================
pause
