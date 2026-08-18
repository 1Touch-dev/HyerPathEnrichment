"""RQ introspection: mocks rq.Queue/Worker, no live Redis needed in CI
(RULE.md: 'No live external calls in CI') (phase2_admin_module.md §9.8)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_get_queues_overview_uses_existing_queue_priorities():
    from app.modules.admin.queues_service import get_queues_overview

    # INDIRECT (judgment call): the plan's sketch does not mock
    # FailedJobRegistry, but get_queues_overview() constructs a REAL
    # rq.registry.FailedJobRegistry(queue=mock_queue) and calls len() on it,
    # which issues real Redis commands (ZCARD/cleanup) against whatever
    # MagicMock get_redis_connection() returns — those calls return more
    # MagicMocks, not ints, and len() raises TypeError. Mocking
    # FailedJobRegistry too (as the retry test below already does) keeps this
    # test hermetic and passing while preserving the plan's stated intent:
    # "one snapshot per name in QUEUE_PRIORITIES — no new queue introduced."
    with patch("app.modules.admin.queues_service.get_redis_connection") as mock_conn:
        with patch("app.modules.admin.queues_service.Worker.all", return_value=[]):
            with patch("app.modules.admin.queues_service.Queue") as mock_queue_cls:
                with patch(
                    "app.modules.admin.queues_service.FailedJobRegistry"
                ) as mock_registry_cls:
                    mock_queue = MagicMock()
                    mock_queue.job_ids = []
                    mock_queue.__len__.return_value = 0
                    mock_queue_cls.return_value = mock_queue

                    mock_registry = MagicMock()
                    mock_registry.__len__.return_value = 0
                    mock_registry_cls.return_value = mock_registry

                    mock_conn.return_value = MagicMock()

                    snapshots = get_queues_overview()
                    # One snapshot per name in QUEUE_PRIORITIES — no new queue introduced.
                    from app.workers.queue import QUEUE_PRIORITIES

                    assert len(snapshots) == len(QUEUE_PRIORITIES)
                    assert {s.name for s in snapshots} == set(QUEUE_PRIORITIES.keys())
                    for snapshot in snapshots:
                        assert snapshot.queued_count == 0
                        assert snapshot.failed_count == 0
                        assert snapshot.workers_listening == 0
                        assert snapshot.oldest_queued_age_seconds is None


def test_get_queues_overview_reports_oldest_queued_age():
    from app.modules.admin.queues_service import get_queues_overview
    from app.workers.queue import QUEUE_PRIORITIES

    first_queue_name = next(iter(QUEUE_PRIORITIES))

    with patch("app.modules.admin.queues_service.get_redis_connection") as mock_conn:
        with patch("app.modules.admin.queues_service.Worker.all", return_value=[]):
            with patch("app.modules.admin.queues_service.Queue") as mock_queue_cls:
                with patch(
                    "app.modules.admin.queues_service.FailedJobRegistry"
                ) as mock_registry_cls:
                    mock_registry = MagicMock()
                    mock_registry.__len__.return_value = 0
                    mock_registry_cls.return_value = mock_registry
                    mock_conn.return_value = MagicMock()

                    def _queue_factory(name, connection=None):
                        queue = MagicMock()
                        if name == first_queue_name:
                            queue.job_ids = ["job-abc"]
                            fake_job = MagicMock()
                            from datetime import UTC, datetime, timedelta

                            fake_job.enqueued_at = datetime.now(UTC) - timedelta(seconds=30)
                            queue.fetch_job.return_value = fake_job
                        else:
                            queue.job_ids = []
                        queue.__len__.return_value = len(queue.job_ids)
                        return queue

                    mock_queue_cls.side_effect = _queue_factory

                    snapshots = get_queues_overview()
                    by_name = {s.name: s for s in snapshots}
                    assert by_name[first_queue_name].queued_count == 1
                    assert by_name[first_queue_name].oldest_queued_age_seconds >= 30


def test_retry_failed_job_calls_registry_requeue():
    from app.modules.admin.queues_service import retry_failed_job

    with patch("app.modules.admin.queues_service.get_redis_connection"):
        with patch("app.modules.admin.queues_service.Queue"):
            with patch("app.modules.admin.queues_service.FailedJobRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_job_ids.return_value = ["job-1"]
                mock_registry_cls.return_value = mock_registry

                result = retry_failed_job("email", "job-1")
                assert result is True
                mock_registry.requeue.assert_called_once_with("job-1")


def test_retry_failed_job_returns_false_when_job_not_in_registry():
    from app.modules.admin.queues_service import retry_failed_job

    with patch("app.modules.admin.queues_service.get_redis_connection"):
        with patch("app.modules.admin.queues_service.Queue"):
            with patch("app.modules.admin.queues_service.FailedJobRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_job_ids.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = retry_failed_job("email", "missing-job")
                assert result is False
                mock_registry.requeue.assert_not_called()


def test_list_failed_jobs_maps_job_fields():
    from app.modules.admin.queues_service import list_failed_jobs

    with patch("app.modules.admin.queues_service.get_redis_connection"):
        with patch("app.modules.admin.queues_service.Queue") as mock_queue_cls:
            with patch("app.modules.admin.queues_service.FailedJobRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_job_ids.return_value = ["job-1"]
                mock_registry_cls.return_value = mock_registry

                mock_job = MagicMock()
                mock_job.id = "job-1"
                mock_job.func_name = "app.workers.tasks.some_task"
                mock_job.enqueued_at = None
                mock_job.ended_at = None
                mock_job.exc_info = "Traceback (most recent call last): boom"

                mock_queue = MagicMock()
                mock_queue.fetch_job.return_value = mock_job
                mock_queue_cls.return_value = mock_queue

                results = list_failed_jobs("email", limit=50)
                assert len(results) == 1
                assert results[0].job_id == "job-1"
                assert results[0].queue_name == "email"
                assert results[0].exc_info == "Traceback (most recent call last): boom"
