SELECT
    id,
    ai_score,
    score_breakdown,
    length(ai_feedback) as feedback_length,
    ai_feedback IS NOT NULL as has_feedback
FROM question_attempts
WHERE id = 'af3173fe-52bd-4258-a359-f92ae19b3b22';
