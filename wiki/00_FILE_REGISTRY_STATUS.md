---
tags: [file-registry, ingest, status]
updated: 2026-06-05 22:01
---

# 파일 레지스트리 현황

> Ingest Agent가 DB에 이미 반영된 시험 원본 PDF를 `file_registry`에 등록했습니다.

## 등록 완료

| file_id | 문제지 | 정답/해설 |
|---|---|---|
| H2510-NA | `sources/2025/2025 10월 고3 전국연합학력평가 수학 문제지.pdf` | `sources/2025/2025 10월 고3 전국연합학력평가 수학 정답 및 해설.pdf` |
| H2511-SU | `sources/2025/2025수능_수학문제.pdf` | `sources/2025/2025수능_수학문제정답.pdf` |
| H2605-NA | `sources/2026/2026 5월 고3 전국연합학력평가 수학 문제.pdf` | `sources/2026/2026 5월 고3 전국연합학력평가 수학 해설.pdf` |
| H2606-NA | `sources/2026/2026 대학수학능력시험 6월 모의평가 수학 문제지.pdf` | `sources/2026/2026 대학수학능력시험 6월 모의평가 수학 해설지(ebs).pdf` |
| H2609-NA | `sources/2026/2026학년도 대학수학능력시험 9월 모의평가 수학 문제 (2).pdf` | `sources/2026/2026 대학수학능력시험 9월 모의평가 수학 해설지(EBS) (2).pdf` |
| H2611-SU | `sources/2026/2026수능_수학문제.pdf` | 미등록 |

## 현재 점검 결과

- 전체 PDF: 11개
- 미등록 문제 PDF: 0개
- 원본 무결성: PASS

## 원칙

- 원본 PDF는 수정하지 않는다.
- 새 원본 파일이 들어오면 Integrity Guard 기준선 갱신 전까지 `new_protected_files`로 표시한다.
