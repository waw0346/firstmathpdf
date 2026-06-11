@echo off
chcp 65001 > nul
echo ============================================
echo  ?ˆ˜?•™?˜ ì§?ë¦„ê¸¸ ?•™?› LLM-Wiki
echo  ? „ì²? ?¬ë¡? + Obsidian ?™ê¸°í™”
echo ============================================
cd /d "%~dp0"

echo.
echo [1/3] PDF ë¬¸ì œ ?¬ë¡? (v19)...
python scripts\crop_all.py
if errorlevel 1 goto error

echo.
echo [2/3] Obsidian ë§ˆí¬?‹¤?š´ ?™ê¸°í™”...
python scripts\obsidian_sync.py
if errorlevel 1 goto error

echo.
echo [3/3] ?’ˆì§? ê²?ì¦?...
python scripts\verify.py
if errorlevel 1 goto error

echo.
echo ============================================
echo  ?™„ë£?! Obsidian?—?„œ Ctrl+R ?ˆŒ?Ÿ¬ ?ƒˆë¡œê³ ì¹?
echo ============================================
pause
exit /b 0

:error
echo.
echo ?Œ ?˜¤ë¥˜ê?? ë°œìƒ?–ˆ?Šµ?‹ˆ?‹¤.
pause
exit /b 1
