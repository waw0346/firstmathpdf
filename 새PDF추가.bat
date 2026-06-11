@echo off
chcp 65001 > nul
echo ============================================
echo  새 PDF 추가 워크플로우
echo ============================================
cd /d "%~dp0"
echo.
echo PDF 파일을 sources\연도\ 폴더에 복사했습니까?
echo 예: sources\2024\2024수능_수학문제.pdf
echo.
set /p YEAR="처리할 연도를 입력하세요 (예: 2024): "
echo.
echo [1/4] 스냅샷 생성 (안전망)...
python scripts\db_restore.py --snapshot "PDF추가_%YEAR%_전"

echo.
echo [2/4] 크롭 실행...
python scripts\crop_all.py %YEAR%

echo.
echo [3/4] Obsidian 동기화...
python scripts\obsidian_sync.py

echo.
echo [4/4] 품질 검증...
python scripts\verify.py

echo.
echo ============================================
echo  완료! 이제 Obsidian에서 검수하세요.
echo  검수 후: 검수완료_DB반영.bat 실행
echo ============================================
pause
