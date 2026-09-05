SELECT
    COUNT(*) as total_events,
    SUM((event_metadata->>'llm.cost_usd')::numeric) as total_cost,
    SUM((event_metadata->>'llm.input_tokens')::int) as total_input_tokens,
    SUM((event_metadata->>'llm.output_tokens')::int) as total_output_tokens
FROM user_activity_events
WHERE event_type = 'llm_call';
