-- H2611-SU original answer/solution reference backfill.
-- This migration records source file paths only; it does not modify original PDFs
-- or problem/explanation content.

UPDATE file_registry
SET file_path_a = CASE
        WHEN file_path_a IS NULL OR file_path_a = ''
        THEN 'sources/2026/2026 대학수학능력시험 수학 해설지(EBS).pdf'
        ELSE file_path_a
    END,
    file_path_s = CASE
        WHEN file_path_s IS NULL OR file_path_s = ''
        THEN 'sources/2026/2026 대학수학능력시험 수학 해설지(EBS).pdf'
        ELSE file_path_s
    END
WHERE file_id = 'H2611-SU';
