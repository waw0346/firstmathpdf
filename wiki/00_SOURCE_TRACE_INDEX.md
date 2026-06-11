---
tags: [source-trace, db, crop, audit]
---

# 원본 역추적 인덱스

> 원본 문제, 원본 정답, 원본 해설은 변경하지 않는다. 이 문서는 크롭 이미지가 어느 원본 PDF와 페이지 범위에서 생성되었는지 별도 색인으로 추적하기 위한 결과이다.

## 결과

- DB crop 대상: 276
- 역추적 가능 행: 276
- 역추적 불가 행: 0
- 적용 상태: dry-run only
- PDF 매칭 실패: 0
- 문제 위치 탐지 실패: 0
- 다음 문제 경계 위험: 0
- 이미지 블록 포함 문제: 43

## 추가된 색인 필드

- `problem_id`
- `source_pdf_path`
- `source_pdf_name`
- `source_page_number`
- `source_column`
- `source_subject_code`
- `source_page_range`
- `crop_path`
- `crop_y0_pt`
- `crop_y1_pt`
- `gap_to_boundary_pt`
- `image_block_count`
- `trace_method`
- `verified_at`

## 운영 원칙

- 문제 본문, 정답, 기존 해설은 수정하지 않는다.
- DB 본문 컬럼을 덮어쓰지 않고 `problem_source_trace` 테이블에만 원본 역추적 정보를 둔다.
- 신규 PDF ingest 후에는 이 스크립트를 실행해 PDF 매칭, 위치 탐지, 이미지 포함, 경계 위험을 동시에 점검한다.
- `scripts/ingest_pdf_v4.py`는 기본적으로 ingest 완료 후 `source_trace_index.py --apply`와 `crop_pipeline_audit.py`를 실행한다.
- `agents/ingest_agent.py --source-trace`로 같은 색인을 수동 갱신할 수 있다.
