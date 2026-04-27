ALTER TABLE stephen_dcx_file_objects
ADD COLUMN IF NOT EXISTS analysis_summary_text TEXT NOT NULL DEFAULT '';
