"""Integration tests for Week 2 foundation features."""


def test_import_all_week2_modules():
    """Verify all Week 2 modules can be imported without errors."""
    # Session tracking
    from app.modules.admin.router import router as admin_router
    from app.modules.sessions.router import router as sessions_router

    # Cost monitoring
    from app.observability.cost_tracking import track_llm_cost

    # Feedback generation
    from app.services.feedback_generator import generate_interview_feedback
    from app.services.session_manager import SessionManager

    # All imports successful
    assert SessionManager is not None
    assert generate_interview_feedback is not None
    assert track_llm_cost is not None
    assert admin_router is not None
    assert sessions_router is not None
    print("✅ All Week 2 module imports successful")


def test_week2_models_loaded():
    """Verify all Week 2 database models are loaded."""
    from app.auth.models import User
    from app.modules.sessions.models import PracticeSession, QuestionAttempt

    # Check relationships exist
    assert hasattr(PracticeSession, "user")
    assert hasattr(PracticeSession, "attempts")
    assert hasattr(QuestionAttempt, "user")
    assert hasattr(QuestionAttempt, "session")
    assert hasattr(User, "practice_sessions")
    assert hasattr(User, "question_attempts")

    print("✅ All Week 2 model relationships configured")
