"""Unit tests for audio processing infrastructure.

Tests Whisper transcription client, audio storage service, and audio analysis.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.clients.speech import (
    MAX_AUDIO_FILE_SIZE_BYTES,
    TranscriptionResult,
    WhisperClient,
    WhisperError,
    validate_audio_file_size,
)
from app.core.config import Settings
from app.services.audio_analysis import (
    TARGET_WPM_MAX,
    TARGET_WPM_MIN,
    analyze_transcription,
    calculate_clarity_score,
    calculate_words_per_minute,
    count_filler_words,
)
from app.services.audio_storage import (
    MAX_AUDIO_FILE_SIZE_BYTES as STORAGE_MAX_FILE_SIZE,
)
from app.services.audio_storage import (
    AudioStorageClient,
    AudioStorageError,
    generate_audio_storage_key,
    validate_audio_mime_type,
)
from app.services.audio_storage import (
    validate_audio_file_size as storage_validate_file_size,
)


class TestWhisperClient:
    """Test Whisper API client."""

    def test_validate_audio_file_size_valid(self) -> None:
        """Test file size validation with valid size."""
        validate_audio_file_size(1024 * 1024)  # 1MB - valid

    def test_validate_audio_file_size_too_large(self) -> None:
        """Test file size validation with oversized file."""
        with pytest.raises(WhisperError, match="exceeds maximum"):
            validate_audio_file_size(MAX_AUDIO_FILE_SIZE_BYTES + 1)

    def test_whisper_client_no_api_key(self) -> None:
        """Test WhisperClient initialization without API key."""
        settings = Settings(_env_file=None, openai_api_key="")
        client = WhisperClient(settings)
        assert client._api_key == ""

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_api_key(self) -> None:
        """Test transcription fails without API key."""
        settings = Settings(_env_file=None, openai_api_key="")
        client = WhisperClient(settings)

        with pytest.raises(WhisperError, match="API key not configured"):
            await client.transcribe_audio(b"audio data", "test.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self) -> None:
        """Test successful audio transcription with mocked API."""
        settings = Settings(openai_api_key="test-key-123")
        client = WhisperClient(settings)

        mock_response_data = {
            "text": "Hello, this is a test transcription.",
            "language": "en",
            "duration": 5.2,
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await client.transcribe_audio(
                b"fake audio data",
                "test.mp3",
                "audio/mpeg",
            )

            assert isinstance(result, TranscriptionResult)
            assert result.text == "Hello, this is a test transcription."
            assert result.language == "en"
            assert result.duration == 5.2

            # Verify API call was made correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "https://api.openai.com/v1/audio/transcriptions" in str(call_args)

    @pytest.mark.asyncio
    async def test_transcribe_audio_empty_response(self) -> None:
        """Test transcription fails with empty response."""
        settings = Settings(openai_api_key="test-key-123")
        client = WhisperClient(settings)

        mock_response = Mock(spec=httpx.Response)
        mock_response.json.return_value = {"text": ""}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(WhisperError, match="empty transcription"):
                await client.transcribe_audio(b"audio data", "test.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_audio_http_error(self) -> None:
        """Test transcription handles HTTP errors."""
        settings = Settings(openai_api_key="test-key-123")
        client = WhisperClient(settings)

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429", request=Mock(), response=mock_response
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(WhisperError, match="Whisper API error"):
                await client.transcribe_audio(b"audio data", "test.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_too_large(self) -> None:
        """Test transcription rejects oversized files."""
        settings = Settings(openai_api_key="test-key-123")
        client = WhisperClient(settings)

        large_audio = b"x" * (MAX_AUDIO_FILE_SIZE_BYTES + 1)

        with pytest.raises(WhisperError, match="exceeds maximum"):
            await client.transcribe_audio(large_audio, "huge.mp3")


class TestAudioStorage:
    """Test audio storage service."""

    def test_validate_audio_file_size_valid(self) -> None:
        """Test file size validation with valid size."""
        storage_validate_file_size(1024 * 1024)  # 1MB - valid

    def test_validate_audio_file_size_too_large(self) -> None:
        """Test file size validation with oversized file."""
        with pytest.raises(AudioStorageError, match="exceeds maximum"):
            storage_validate_file_size(STORAGE_MAX_FILE_SIZE + 1)

    def test_validate_audio_mime_type_valid(self) -> None:
        """Test MIME type validation with valid formats."""
        assert validate_audio_mime_type("audio/mpeg") == "mp3"
        assert validate_audio_mime_type("audio/wav") == "wav"
        assert validate_audio_mime_type("audio/webm") == "webm"
        assert validate_audio_mime_type("audio/ogg") == "ogg"

    def test_validate_audio_mime_type_invalid(self) -> None:
        """Test MIME type validation rejects unsupported formats."""
        with pytest.raises(AudioStorageError, match="Unsupported audio format"):
            validate_audio_mime_type("video/mp4")

    def test_generate_audio_storage_key(self) -> None:
        """Test storage key generation."""
        user_id = "user123"
        session_id = "session456"
        extension = "mp3"

        key = generate_audio_storage_key(user_id, session_id, extension)

        assert key.startswith("practice-audio/")
        assert user_id in key
        assert session_id in key
        assert key.endswith(".mp3")

    @pytest.mark.asyncio
    async def test_upload_audio_success(self) -> None:
        """Test successful audio upload."""
        client = AudioStorageClient()

        audio_data = b"fake audio content" * 100
        user_id = "user123"
        session_id = "session456"

        with patch.object(client._storage, "upload_bytes", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/audio/test.mp3"

            storage_path, file_size = await client.upload_audio(
                audio_data,
                "test.mp3",
                "audio/mpeg",
                user_id,
                session_id,
            )

            assert storage_path.startswith("practice-audio/")
            assert file_size == len(audio_data)
            mock_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_audio_file_too_small(self) -> None:
        """Test upload rejects corrupted/empty files."""
        client = AudioStorageClient()

        with pytest.raises(AudioStorageError, match="corrupted or empty"):
            await client.upload_audio(
                b"tiny",
                "test.mp3",
                "audio/mpeg",
                "user123",
                "session456",
            )

    @pytest.mark.asyncio
    async def test_upload_audio_invalid_mime_type(self) -> None:
        """Test upload rejects unsupported formats."""
        client = AudioStorageClient()

        with pytest.raises(AudioStorageError, match="Unsupported audio format"):
            await client.upload_audio(
                b"x" * 1000,
                "test.txt",
                "text/plain",
                "user123",
                "session456",
            )

    @pytest.mark.asyncio
    async def test_delete_audio_success(self) -> None:
        """Test successful audio deletion."""
        client = AudioStorageClient()

        with patch.object(client._storage, "delete_object", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True

            result = await client.delete_audio("practice-audio/user123/session456/rec123.mp3")

            assert result is True
            mock_delete.assert_called_once_with("practice-audio/user123/session456/rec123.mp3")


class TestAudioAnalysis:
    """Test audio transcription analysis."""

    def test_count_filler_words_none(self) -> None:
        """Test filler word detection with clean text."""
        text = "I am confident in my abilities and ready to succeed."
        count, fillers = count_filler_words(text)

        assert count == 0
        assert len(fillers) == 0

    def test_count_filler_words_single_word_fillers(self) -> None:
        """Test detection of single-word fillers (um, uh, like)."""
        text = "Um, I think, like, we should, uh, proceed."
        count, fillers = count_filler_words(text)

        assert count == 3
        assert "um" in fillers
        assert "like" in fillers
        assert "uh" in fillers

    def test_count_filler_words_multi_word_fillers(self) -> None:
        """Test detection of multi-word fillers (you know, basically)."""
        text = "You know, basically, I think we should, you know, proceed."
        count, _fillers = count_filler_words(text)

        assert count >= 3  # "you know" appears twice, "basically" once

    def test_count_filler_words_accuracy(self) -> None:
        """Test filler word detection accuracy with complex text."""
        text = "I, um, like the idea. You know what I mean? Literally, it's basically perfect."
        count, fillers = count_filler_words(text)

        # Should detect: um, like, you know, literally, basically
        assert count >= 4
        assert "um" in fillers
        assert "like" in fillers
        assert "literally" in fillers
        assert "basically" in fillers

    def test_calculate_words_per_minute_normal_pace(self) -> None:
        """Test WPM calculation with normal speaking pace."""
        word_count = 150
        duration_seconds = 60.0  # 1 minute

        wpm = calculate_words_per_minute(word_count, duration_seconds)

        assert wpm == 150.0

    def test_calculate_words_per_minute_no_duration(self) -> None:
        """Test WPM calculation returns None without duration."""
        wpm = calculate_words_per_minute(100, None)
        assert wpm is None

        wpm = calculate_words_per_minute(100, 0.0)
        assert wpm is None

    def test_calculate_clarity_score_perfect(self) -> None:
        """Test clarity score with perfect speech (no fillers, good pace)."""
        score = calculate_clarity_score(filler_percentage=0.0, wpm=150.0)
        assert score == 100.0

    def test_calculate_clarity_score_fillers_only(self) -> None:
        """Test clarity score penalizes filler words."""
        score = calculate_clarity_score(filler_percentage=10.0, wpm=None)
        assert score == 90.0  # 100 - 10

    def test_calculate_clarity_score_too_slow(self) -> None:
        """Test clarity score penalizes speaking too slowly."""
        score = calculate_clarity_score(filler_percentage=0.0, wpm=100.0)
        assert score < 100.0  # Should be penalized for being below TARGET_WPM_MIN (120)

    def test_calculate_clarity_score_too_fast(self) -> None:
        """Test clarity score penalizes speaking too fast."""
        score = calculate_clarity_score(filler_percentage=0.0, wpm=200.0)
        assert score < 100.0  # Should be penalized for being above TARGET_WPM_MAX (180)

    def test_calculate_clarity_score_combined_penalties(self) -> None:
        """Test clarity score with both filler and pace penalties."""
        score = calculate_clarity_score(filler_percentage=15.0, wpm=100.0)
        assert score < 85.0  # Should have both penalties applied

    def test_analyze_transcription_clean_speech(self) -> None:
        """Test analysis of clean, professional speech."""
        text = "I am confident in my technical abilities and excited to contribute to this role."
        duration_seconds = 5.0

        analysis = analyze_transcription(text, duration_seconds)

        assert analysis.word_count == 14  # Counted correctly
        assert analysis.filler_word_count == 0
        assert analysis.filler_word_percentage == 0.0
        assert analysis.words_per_minute is not None
        assert analysis.clarity_score > 80.0  # Should have high clarity

    def test_analyze_transcription_with_fillers(self) -> None:
        """Test analysis detects filler words correctly."""
        text = "Um, I think, like, we should basically proceed with, you know, the plan."
        duration_seconds = 6.0

        analysis = analyze_transcription(text, duration_seconds)

        assert analysis.word_count == 13
        assert analysis.filler_word_count >= 4
        assert analysis.filler_word_percentage > 0.0
        assert len(analysis.detected_fillers) >= 4

    def test_analyze_transcription_empty_text(self) -> None:
        """Test analysis handles empty transcription gracefully."""
        analysis = analyze_transcription("", duration_seconds=10.0)

        assert analysis.word_count == 0
        assert analysis.filler_word_count == 0
        assert analysis.clarity_score == 0.0

    def test_analyze_transcription_no_duration(self) -> None:
        """Test analysis works without duration (no WPM)."""
        text = "I am confident and ready."
        analysis = analyze_transcription(text, duration_seconds=None)

        assert analysis.word_count == 5
        assert analysis.words_per_minute is None
        assert analysis.clarity_score >= 0.0  # Should still calculate based on fillers

    def test_wpm_in_target_range(self) -> None:
        """Test that target WPM range is correctly defined."""
        assert TARGET_WPM_MIN == 120
        assert TARGET_WPM_MAX == 180

        # Speech in target range should not be penalized
        score_optimal = calculate_clarity_score(0.0, 150.0)
        assert score_optimal == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
