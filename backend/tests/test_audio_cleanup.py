"""Unit tests for audio cleanup worker task."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.workers.tasks.audio_cleanup import AudioStorageClient, cleanup_expired_audio


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def sample_expired_recordings():
    """Sample expired audio recordings."""
    now = datetime.utcnow()
    return [
        {
            "id": uuid4(),
            "storage_path": "audio/user1/session1/recording1.webm",
            "user_id": uuid4(),
            "expires_at": now - timedelta(days=1),
        },
        {
            "id": uuid4(),
            "storage_path": "audio/user2/session2/recording2.webm",
            "user_id": uuid4(),
            "expires_at": now - timedelta(days=7),
        },
        {
            "id": uuid4(),
            "storage_path": "audio/user3/session3/recording3.webm",
            "user_id": uuid4(),
            "expires_at": now - timedelta(hours=1),
        },
    ]


class TestAudioStorageClient:
    """Test AudioStorageClient interface."""

    @pytest.mark.asyncio
    async def test_delete_audio_success(self):
        """Test successful audio file deletion."""
        client = AudioStorageClient()

        with patch.object(client._storage, "delete_object", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True

            result = await client.delete_audio("audio/test.webm")

            assert result is True
            mock_delete.assert_called_once_with("audio/test.webm")

    @pytest.mark.asyncio
    async def test_delete_audio_not_found(self):
        """Test audio file not found in storage."""
        client = AudioStorageClient()

        with patch.object(client._storage, "delete_object", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = False

            result = await client.delete_audio("audio/nonexistent.webm")

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_audio_handles_errors(self):
        """Test error handling during deletion."""
        client = AudioStorageClient()

        with patch.object(client._storage, "delete_object", new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = Exception("Storage error")

            result = await client.delete_audio("audio/test.webm")

            assert result is False


class TestCleanupExpiredAudio:
    """Test cleanup_expired_audio worker function."""

    def test_cleanup_respects_expiry_date(self, mock_db_session, sample_expired_recordings):
        """Test that cleanup only processes expired recordings."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_expired_recordings
        # Mock both SELECT and DELETE
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        # Create a mock storage client WITH delete_audio as AsyncMock
        mock_storage_client = MagicMock()
        mock_storage_client.delete_audio = AsyncMock(return_value=True)

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            # Patch the class to return our mock when instantiated
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            result = cleanup_expired_audio()

            # Verify query was called with correct parameters
            execute_calls = mock_db_session.execute.call_args_list
            assert len(execute_calls) >= 1

            # Check that query filters by expires_at < now
            query_call = execute_calls[0]
            assert "expires_at" in str(query_call[0][0]).lower()
            # Check params dict contains now and limit
            params = query_call.kwargs.get("params", {})
            assert "now" in params
            assert "limit" in params

            # Verify stats
            assert result["deleted_count"] == 3
            assert result["failed_count"] == 0

    def test_cleanup_batch_limit(self, mock_db_session):
        """Test that cleanup respects batch limit of 1000."""
        # Create 1500 recordings but expect only 1000 to be processed
        large_batch = [
            {
                "id": uuid4(),
                "storage_path": f"audio/user{i}/recording.webm",
                "user_id": uuid4(),
            }
            for i in range(1500)
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = large_batch[:1000]  # DB will limit to 1000
        # Mock SELECT and DELETE
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        # Create mock storage client with AsyncMock
        mock_storage_client = MagicMock()
        mock_storage_client.delete_audio = AsyncMock(return_value=True)

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            result = cleanup_expired_audio()

            # Verify query includes LIMIT 1000
            query_call = mock_db_session.execute.call_args_list[0]
            assert "limit" in str(query_call[0][0]).lower()
            params = query_call.kwargs.get("params", {})
            assert params.get("limit") == 1000

            # Verify only 1000 were processed
            assert result["deleted_count"] == 1000

    def test_cleanup_no_expired_recordings(self, mock_db_session):
        """Test cleanup when no expired recordings exist."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch(
            "app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session
        ):
            result = cleanup_expired_audio()

            assert result["deleted_count"] == 0
            assert result["failed_count"] == 0

    def test_cleanup_audit_logging(self, mock_db_session, sample_expired_recordings, caplog):
        """Test that audit logs are generated for GDPR compliance."""
        import logging

        # Set caplog level before running test
        caplog.set_level(logging.INFO, logger="app.workers.tasks.audio_cleanup")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [sample_expired_recordings[0]]
        # Mock SELECT and DELETE
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        # Create mock storage client with AsyncMock
        mock_storage_client = MagicMock()
        mock_storage_client.delete_audio = AsyncMock(return_value=True)

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            cleanup_expired_audio()

            # Verify audit log contains required fields in extra data
            audit_log_found = False
            for record in caplog.records:
                if "Audio recording deleted for GDPR compliance" in record.message:
                    audit_log_found = True
                    # Check extra data is logged (pytest caplog has these in __dict__)
                    assert hasattr(record, "recording_id")
                    assert hasattr(record, "user_id")
                    assert hasattr(record, "storage_path")
                    assert hasattr(record, "deleted_at")
                    assert hasattr(record, "reason")
                    assert record.reason == "expired_retention_period"
                    break

            assert audit_log_found, (
                f"GDPR audit log not found. Found logs: {[r.message for r in caplog.records]}"
            )

    def test_cleanup_stats_returned_correctly(self, mock_db_session, sample_expired_recordings):
        """Test that stats are returned correctly."""
        # Mix of successful and failed deletions
        recordings = sample_expired_recordings[:2]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = recordings
        # Mock both SELECT and DELETE
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        # First deletion succeeds, second fails
        mock_storage_client = MagicMock()
        call_count = [0]

        async def side_effect_delete(path: str):
            call_count[0] += 1
            if call_count[0] == 1:
                return True
            raise Exception("Storage error")

        mock_storage_client.delete_audio = side_effect_delete

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            result = cleanup_expired_audio()

            # One succeeded (and was committed to DB), one failed
            assert result["deleted_count"] == 1
            assert result["failed_count"] == 1

    def test_cleanup_handles_storage_client_errors(
        self, mock_db_session, sample_expired_recordings
    ):
        """Test graceful handling of storage client errors."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [sample_expired_recordings[0]]
        # Mock both SELECT and DELETE (though DELETE won't be reached)
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        async def mock_delete_audio(path: str) -> bool:
            raise Exception("Connection failed")

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch.object(AudioStorageClient, "delete_audio", new=mock_delete_audio),
        ):
            result = cleanup_expired_audio()

            # Should handle error gracefully - no successes, one failure
            assert result["deleted_count"] == 0
            assert result["failed_count"] == 1

    def test_cleanup_deletes_db_records_after_storage(
        self, mock_db_session, sample_expired_recordings
    ):
        """Test that DB records are deleted after successful storage deletion."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_expired_recordings
        # Mock SELECT and then DELETE
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        # Create mock storage client with AsyncMock
        mock_storage_client = MagicMock()
        mock_storage_client.delete_audio = AsyncMock(return_value=True)

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            cleanup_expired_audio()

            # Verify DB delete was called
            execute_calls = mock_db_session.execute.call_args_list
            # Should be 2 calls: 1 for SELECT, 1 for DELETE
            assert len(execute_calls) == 2

            # Verify DELETE statement
            delete_call = execute_calls[1]
            assert "delete" in str(delete_call[0][0]).lower()
            assert "practice_audio_recordings" in str(delete_call[0][0]).lower()

            # Verify commit was called
            mock_db_session.commit.assert_called_once()

    def test_cleanup_db_rollback_on_delete_failure(
        self, mock_db_session, sample_expired_recordings
    ):
        """Test that DB transaction is rolled back on delete failure."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [sample_expired_recordings[0]]

        # Mock execute to succeed on SELECT but fail on DELETE
        def execute_side_effect(stmt, params=None):
            stmt_str = str(stmt).lower()
            if "select" in stmt_str:
                return mock_result
            elif "delete" in stmt_str:
                raise Exception("DB delete failed")
            return MagicMock()

        mock_db_session.execute.side_effect = execute_side_effect

        # Create mock storage client with AsyncMock
        mock_storage_client = MagicMock()
        mock_storage_client.delete_audio = AsyncMock(return_value=True)

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            result = cleanup_expired_audio()

            # Verify rollback was called
            mock_db_session.rollback.assert_called()

            # Stats should reflect failure (storage succeeded but DB failed)
            assert result["deleted_count"] == 0
            assert (
                result["failed_count"] == 0
            )  # Not counted as failed since storage worked, just DB failed

    def test_cleanup_handles_total_failure(self, mock_db_session):
        """Test handling of complete job failure."""
        with patch(
            "app.workers.tasks.audio_cleanup.SyncSessionLocal",
            side_effect=Exception("DB connection failed"),
        ):
            result = cleanup_expired_audio()

            # Should return zero stats on failure
            assert result["deleted_count"] == 0
            assert result["failed_count"] == 0

    def test_cleanup_closes_db_session(self, mock_db_session):
        """Test that DB session is always closed."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch(
            "app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session
        ):
            cleanup_expired_audio()

            mock_db_session.close.assert_called_once()

    def test_cleanup_orphaned_records_removed(self, mock_db_session, sample_expired_recordings):
        """Test that orphaned DB records are removed even if storage deletion fails."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [sample_expired_recordings[0]]
        # Mock SELECT and DELETE
        mock_db_session.execute.side_effect = [mock_result, MagicMock()]

        # Create mock storage client with AsyncMock
        mock_storage_client = MagicMock()
        mock_storage_client.delete_audio = AsyncMock(
            return_value=False
        )  # Storage deletion returns False

        with (
            patch("app.workers.tasks.audio_cleanup.SyncSessionLocal", return_value=mock_db_session),
            patch("app.workers.tasks.audio_cleanup.AudioStorageClient") as mock_client_class,
        ):
            mock_client_class.return_value = mock_storage_client

            cleanup_expired_audio()

            # DB record should still be deleted to avoid orphans
            execute_calls = mock_db_session.execute.call_args_list
            assert len(execute_calls) == 2  # SELECT and DELETE

            delete_call = execute_calls[1]
            assert "delete" in str(delete_call[0][0]).lower()
