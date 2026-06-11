@echo off
chcp 65001 > nul
echo ============================================
echo  수학 문제 PDF 자동 인제스트 v4.0
echo ============================================
echo.
echo 문제 PDF 파일 경로를 입력하세요:
set /p Q_PDF="문제 PDF: "
echo.
echo 정답 PDF 파일 경로를 입력하세요 (없으면 Enter):
set /p A_PDF="정답 PDF: "
echo.

cd /d "%~dp0"

if "%A_PDF%"=="" (
    python scripts\ingest_pdf_v4.py --q "%Q_PDF%"
) else (
    python scripts\ingest_pdf_v4.py --q "%Q_PDF%" --a "%A_PDF%"
)

echo.
echo ============================================
echo  완료! Obsidian에서 Ctrl+R 눌러 새로고침
echo ============================================
pause
