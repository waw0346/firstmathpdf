# Git 저장소 초기화 방법

> 이 폴더에서 **PowerShell** 또는 **Git Bash**를 열고 아래 명령어를 실행하세요.

## 1단계: 저장소 초기화

```powershell
cd C:\Users\oem\Documents\math_llm
git init
git config user.email "waw0346@gmail.com"
git config user.name "captin"
```

## 2단계: 첫 커밋

```powershell
git add .
git commit -m "초기 커밋: 2025 수능 28문제 + 위키 시스템"
```

## 3단계: GitHub 연결 (선택)

```powershell
# GitHub에서 Private 저장소 생성 후:
git remote add origin https://github.com/YOUR_ID/math-wiki.git
git push -u origin main
```

## 연도별 커밋 워크플로

```powershell
# 새 연도 PDF 추가할 때마다:
python scripts/ingest.py --dir sources/2024/
python scripts/embed.py --update-new
python scripts/wiki_builder.py --all
python scripts/export_json.py

git add .
git commit -m "2024 수능/학교시험 추가: XX문제"
```

## 브랜치 전략 (선택)

```powershell
git checkout -b feature/2024-suneung   # 새 연도 작업
git checkout main                       # 안정 버전
git merge feature/2024-suneung         # 병합
```
