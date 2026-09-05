SELECT
    id,
    ai_score,
    substring(ai_feedback, 1, 200) as feedback_preview
FROM question_attempts
WHERE ai_score IS NOT NULL
ORDER BY attempted_at DESC
LIMIT 5;
