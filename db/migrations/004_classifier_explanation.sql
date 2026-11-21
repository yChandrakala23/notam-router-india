-- 004_classifier_explanation.sql  -- Person A: explainable classification
--
-- Stores WHY the merged classifier chose a label (rule, keyword guard match,
-- reasons for uncertainty) so GET /notams/relevant and the map can show it.
-- Re-runnable.

ALTER TABLE notam_event
  ADD COLUMN IF NOT EXISTS classifier_reason      TEXT,
  ADD COLUMN IF NOT EXISTS classifier_keyword     TEXT,
  ADD COLUMN IF NOT EXISTS classifier_uncertainty TEXT[] NOT NULL DEFAULT '{}';
