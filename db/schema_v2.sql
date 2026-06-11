-- ============================================================
-- Math LLM Wiki — DB Schema v2
-- 12자리 고유 ID 체계 (H251-JH10-SM-01) 완전 반영
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- 마스터 코드 테이블 (룩업 테이블)
-- ──────────────────────────────────────────────────────────────

-- 과정 코드
CREATE TABLE IF NOT EXISTS master_course (
    code  TEXT PRIMARY KEY,  -- E/M/H/U
    label TEXT NOT NULL      -- 초등/중등/고등/대학
);
INSERT OR IGNORE INTO master_course VALUES
    ('E','초등'),('M','중등'),('H','고등'),('U','대학·전공');

-- 영역 코드
CREATE TABLE IF NOT EXISTS master_domain (
    code  TEXT PRIMARY KEY,  -- AL/GE/CA/ST/CO/CT
    label TEXT NOT NULL,     -- 대수/기하/미적분/확통/공수1/공수2
    course TEXT              -- 주로 사용하는 과정
);
INSERT OR IGNORE INTO master_domain VALUES
    ('AL','대수','H'),('GE','기하','H'),('CA','미적분','H'),
    ('ST','확률과통계','H'),('CO','공업수학1','U'),('CT','공업수학2','U'),
    ('AR','산술','E'),('FR','분수','E'),('EQ','방정식','M'),
    ('FN','함수','M'),('SQ','수열','H');

-- 출처 코드
CREATE TABLE IF NOT EXISTS master_source (
    code        TEXT PRIMARY KEY,   -- KO/NA/YD/JH...
    label       TEXT NOT NULL,      -- 국가수능/모의고사/영동고...
    source_type TEXT NOT NULL,      -- exam/school/publisher/student/military
    note        TEXT
);
INSERT OR IGNORE INTO master_source VALUES
    ('KO','국가수능','exam','수능 본시험'),
    ('NA','모의고사','exam','전국연합학력평가'),
    ('ED','교육청','exam','교육청 주관'),
    ('YD','영동고','school',NULL),
    ('NS','낙생고','school',NULL),
    ('DJ','분당중','school',NULL),
    ('SN','수내중','school',NULL),
    ('JJ','정자중','school',NULL),
    ('BS','EBS','publisher',NULL),
    ('SS','신사고','publisher',NULL),
    ('KM','KMO','competition','한국수학올림피아드'),
    ('PR','학교프린트','school',NULL),
    ('AR','공군','military',NULL),
    ('AM','육군','military',NULL),
    ('TO','원장저작권','own','수학의 지름길 저작'),
    ('TF','저작권프리','own',NULL);

-- 학생 코드 (개별 확장)
CREATE TABLE IF NOT EXISTS master_student (
    code       TEXT PRIMARY KEY,  -- JH/JW...
    name_kr    TEXT NOT NULL,     -- 정호/진우
    name_en    TEXT,
    grade      TEXT,              -- 현재 학년
    enrolled   TEXT,              -- 등록일 YYYY-MM-DD
    note       TEXT
);

-- 학기/시행 스펙 코드
CREATE TABLE IF NOT EXISTS master_spec (
    code  TEXT PRIMARY KEY,  -- 11/12/21/22/TO/TF
    label TEXT NOT NULL
);
INSERT OR IGNORE INTO master_spec VALUES
    ('11','1학기 중간'),('12','1학기 기말'),
    ('21','2학기 중간'),('22','2학기 기말'),
    ('TO','원장저작권'),('TF','저작권프리');
-- 01~12 월별은 동적 (별도 컬럼으로 처리)

-- ──────────────────────────────────────────────────────────────
-- 핵심 문제 테이블 (v2)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS problems_v2 (

    -- ▶ 기본 식별
    id              TEXT PRIMARY KEY,   -- H251-JH10-SM-01  (12자리+하이픈)
    legacy_id       TEXT,               -- 기존 ID (2025_수능_고3_001) 호환용

    -- ▶ BLOCK 1: 대상 정보 (자리 1~4)
    course          TEXT NOT NULL,      -- E/M/H/U
    domain_code     TEXT,               -- AL/GE/CA/ST/25/26 (영역코드 or 연도)
    year            INTEGER,            -- 실제 연도 (2025, 2026...)
    grade_num       INTEGER,            -- 학년 숫자 1/2/3/4/0

    -- ▶ BLOCK 2: 출처 및 세부 스펙 (자리 5~8)
    source_code     TEXT,               -- KO/NA/YD/JH/JW... (master_source or master_student)
    is_student_exam INTEGER DEFAULT 0,  -- 1이면 개인 시험지
    student_code    TEXT,               -- master_student.code FK
    spec_code       TEXT,               -- 11/12/21/22 or TO/TF
    exam_month      INTEGER,            -- 1~12 (월별 시행 시)
    exam_date       TEXT,               -- 상세 일자 YYYY-MM-DD (노트 속성용)

    -- ▶ BLOCK 3: 문항 형태 (자리 9~10)
    data_type       TEXT NOT NULL,      -- Q/S/W/A
    sub_type        TEXT,               -- M/A/B/C/X
    is_solution     INTEGER DEFAULT 0,  -- 1이면 해설본 (S/A)
    is_essay        INTEGER DEFAULT 0,  -- 1이면 서술형 (W/A)
    is_teacher_only INTEGER DEFAULT 0,  -- 1이면 교사용 (sub_type=M)

    -- ▶ BLOCK 4: 문항 번호 (자리 11~12)
    problem_number  INTEGER NOT NULL,   -- 1~99

    -- ▶ 교육과정 분류 (기존 컬럼 유지)
    title           TEXT,
    domain          TEXT,               -- 수와연산/함수/기하/확률과통계...
    topic           TEXT,               -- 미분/적분/지수와로그...
    concept         TEXT,               -- JSON array ["등비수열","극한"]
    difficulty      TEXT,               -- 하/중/상/최상
    answer          TEXT,
    tags            TEXT,               -- JSON array

    -- ▶ 출처 표시 (human-readable)
    school          TEXT,               -- "수능" / "영동고" / "정호 학생 10월"
    exam_type       TEXT,               -- "수능" / "1학기중간" / "개인평가"

    -- ▶ 파일 경로
    source_pdf      TEXT,               -- 원본 PDF 경로
    crop_path       TEXT,               -- 크롭 이미지 경로
    md_path         TEXT,               -- 위키 마크다운 경로
    page_number     INTEGER,

    -- ▶ 해설 관련
    solution_steps  INTEGER,            -- 풀이 단계 수
    raw_text        TEXT,               -- OCR/LLM 추출 원문

    -- ▶ 메타
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT,

    -- FK
    FOREIGN KEY (student_code) REFERENCES master_student(code),
    FOREIGN KEY (source_code)  REFERENCES master_source(code)
);

-- ──────────────────────────────────────────────────────────────
-- 해설 테이블 (다중 풀이 지원)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS solutions (
    id              TEXT PRIMARY KEY,   -- H251-JH10-SM-01 (sub_type=M/A/B/C)
    problem_id      TEXT NOT NULL,      -- 연결된 문제 ID (data_type=Q or W)
    solution_type   TEXT NOT NULL,      -- M(마스터)/A/B/C(풀이시리즈)
    content         TEXT,               -- 해설 본문 (마크다운)
    steps           TEXT,               -- JSON: 단계별 풀이
    created_by      TEXT DEFAULT 'claude',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (problem_id) REFERENCES problems_v2(id)
);

-- ──────────────────────────────────────────────────────────────
-- 오답 데이터 테이블 (학생용 X 서브타입)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS student_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code    TEXT NOT NULL,
    problem_id      TEXT NOT NULL,
    answer_given    TEXT,
    is_correct      INTEGER,            -- 0/1
    error_type      TEXT,               -- 계산실수/개념오류/풀이미숙/시간부족
    exam_date       TEXT,               -- YYYY-MM-DD
    note            TEXT,
    FOREIGN KEY (student_code)  REFERENCES master_student(code),
    FOREIGN KEY (problem_id)    REFERENCES problems_v2(id)
);

-- ──────────────────────────────────────────────────────────────
-- 유사문제 테이블 (기존 호환)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS similar_problems (
    problem_id      TEXT NOT NULL,
    similar_id      TEXT NOT NULL,
    similarity      REAL,
    PRIMARY KEY (problem_id, similar_id)
);

-- ──────────────────────────────────────────────────────────────
-- 편의 뷰 (자주 쓰는 쿼리 단순화)
-- ──────────────────────────────────────────────────────────────

-- 문제 전용 뷰 (해설 제외)
CREATE VIEW IF NOT EXISTS v_questions AS
SELECT * FROM problems_v2
WHERE data_type IN ('Q','W') AND is_solution = 0;

-- 학생별 시험 현황
CREATE VIEW IF NOT EXISTS v_student_exams AS
SELECT
    p.student_code,
    s.name_kr   AS student_name,
    p.year,
    p.exam_month,
    p.exam_date,
    p.exam_type,
    COUNT(*)    AS problem_count,
    p.difficulty
FROM problems_v2 p
LEFT JOIN master_student s ON p.student_code = s.code
WHERE p.is_student_exam = 1
GROUP BY p.student_code, p.year, p.exam_month, p.exam_type;

-- 난이도·단원 분포
CREATE VIEW IF NOT EXISTS v_topic_stats AS
SELECT
    course, domain, topic, difficulty,
    COUNT(*) AS cnt,
    AVG(solution_steps) AS avg_steps
FROM problems_v2
WHERE is_solution = 0
GROUP BY course, domain, topic, difficulty;

-- ──────────────────────────────────────────────────────────────
-- 인덱스
-- ──────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pv2_course      ON problems_v2(course);
CREATE INDEX IF NOT EXISTS idx_pv2_year        ON problems_v2(year);
CREATE INDEX IF NOT EXISTS idx_pv2_student     ON problems_v2(student_code);
CREATE INDEX IF NOT EXISTS idx_pv2_domain      ON problems_v2(domain);
CREATE INDEX IF NOT EXISTS idx_pv2_difficulty  ON problems_v2(difficulty);
CREATE INDEX IF NOT EXISTS idx_pv2_month       ON problems_v2(exam_month);
CREATE INDEX IF NOT EXISTS idx_pv2_dtype       ON problems_v2(data_type, sub_type);
