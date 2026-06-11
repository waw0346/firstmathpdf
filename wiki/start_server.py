#!/usr/bin/env python3
"""
대시보드 서버 실행 스크립트
실행: python3 wiki/start_server.py
브라우저: http://localhost:8765/wiki/verify_dashboard.html
"""
import http.server, webbrowser, threading, os, sys
from pathlib import Path

PORT = 8765
BASE = Path(__file__).parent.parent  # math_llm 폴더
URL  = f"http://localhost:{PORT}/wiki/verify_dashboard.html"

os.chdir(str(BASE))

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass  # 로그 숨김

def open_browser():
    import time; time.sleep(0.8)
    webbrowser.open(URL)

print(f"✅ 수학 문제 검수 대시보드 서버 시작")
print(f"   주소: {URL}")
print(f"   폴더: {BASE}")
print(f"\n   브라우저가 자동으로 열립니다...")
print(f"   종료: Ctrl+C\n")

threading.Thread(target=open_browser, daemon=True).start()
try:
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
except KeyboardInterrupt:
    print("\n서버 종료")
