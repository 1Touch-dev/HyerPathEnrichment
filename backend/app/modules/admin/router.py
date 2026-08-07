"""Admin API routes for cost monitoring."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import VerifiedUser
from app.auth.models import User
from app.observability.cost_tracking import (
    get_daily_cost,
    get_daily_llm_cost,
    get_monthly_cost,
    get_monthly_llm_cost,
    get_total_cost,
    get_user_costs,
)

router = APIRouter(prefix="/api/admin/costs", tags=["admin"])


# Response models
class CostSummary(BaseModel):
    """Cost summary for a time period."""

    tokens: int = Field(..., description="Total tokens processed")
    embeddings: int | None = Field(None, description="Number of embeddings (embedding costs only)")
    input_tokens: int | None = Field(None, description="Input tokens (LLM costs only)")
    output_tokens: int | None = Field(None, description="Output tokens (LLM costs only)")
    cost_usd: float = Field(..., description="Total cost in USD")


class DailyCostResponse(BaseModel):
    """Daily cost breakdown."""

    date: str
    embeddings: CostSummary
    llm: CostSummary
    total_cost_usd: float


class MonthlyCostResponse(BaseModel):
    """Monthly cost breakdown."""

    month: str
    embeddings: CostSummary
    llm: CostSummary
    total_cost_usd: float


class TotalCostResponse(BaseModel):
    """All-time cost breakdown."""

    embeddings: CostSummary
    llm: CostSummary
    total_cost_usd: float


class UserCost(BaseModel):
    """User cost information."""

    user_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class TopUsersResponse(BaseModel):
    """Top users by cost."""

    users: list[UserCost]


class CostBreakdownResponse(BaseModel):
    """Cost breakdown by operation."""

    daily: DailyCostResponse
    monthly: MonthlyCostResponse
    total: TotalCostResponse


def require_superuser(user: VerifiedUser) -> User:
    """Require user to be a superuser.

    Args:
        user: Current verified user

    Returns:
        User object if superuser

    Raises:
        HTTPException: 403 if not a superuser
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user


@router.get("/daily", response_model=DailyCostResponse)
async def get_daily_costs(
    date: str | None = None,
    _user: User = Depends(require_superuser),
) -> DailyCostResponse:
    """Get daily costs (embeddings + LLM).

    Args:
        date: ISO date string (YYYY-MM-DD), defaults to today
        _user: Superuser dependency

    Returns:
        Daily cost breakdown
    """
    if date is None:
        date = datetime.now(UTC).date().isoformat()

    embedding_costs = await get_daily_cost(date)
    llm_costs = await get_daily_llm_cost(date)

    return DailyCostResponse(
        date=date,
        embeddings=CostSummary(
            tokens=embedding_costs["tokens"],
            embeddings=embedding_costs["embeddings"],
            input_tokens=None,
            output_tokens=None,
            cost_usd=embedding_costs["cost_usd"],
        ),
        llm=CostSummary(
            tokens=llm_costs["input_tokens"] + llm_costs["output_tokens"],
            embeddings=None,
            input_tokens=llm_costs["input_tokens"],
            output_tokens=llm_costs["output_tokens"],
            cost_usd=llm_costs["cost_usd"],
        ),
        total_cost_usd=embedding_costs["cost_usd"] + llm_costs["cost_usd"],
    )


@router.get("/monthly", response_model=MonthlyCostResponse)
async def get_monthly_costs(
    month: str | None = None,
    _user: User = Depends(require_superuser),
) -> MonthlyCostResponse:
    """Get monthly costs (embeddings + LLM).

    Args:
        month: Month string (YYYY-MM), defaults to current month
        _user: Superuser dependency

    Returns:
        Monthly cost breakdown
    """
    if month is None:
        month = datetime.now(UTC).strftime("%Y-%m")

    embedding_costs = await get_monthly_cost(month)
    llm_costs = await get_monthly_llm_cost(month)

    return MonthlyCostResponse(
        month=month,
        embeddings=CostSummary(
            tokens=embedding_costs["tokens"],
            embeddings=embedding_costs["embeddings"],
            input_tokens=None,
            output_tokens=None,
            cost_usd=embedding_costs["cost_usd"],
        ),
        llm=CostSummary(
            tokens=llm_costs["input_tokens"] + llm_costs["output_tokens"],
            embeddings=None,
            input_tokens=llm_costs["input_tokens"],
            output_tokens=llm_costs["output_tokens"],
            cost_usd=llm_costs["cost_usd"],
        ),
        total_cost_usd=embedding_costs["cost_usd"] + llm_costs["cost_usd"],
    )


@router.get("/total", response_model=TotalCostResponse)
async def get_total_costs(
    _user: User = Depends(require_superuser),
) -> TotalCostResponse:
    """Get all-time costs (embeddings + LLM).

    Args:
        _user: Superuser dependency

    Returns:
        All-time cost breakdown
    """
    embedding_costs = await get_total_cost()
    
    # Get LLM total from all-time counters
    try:
        from app.workers.queue import get_redis_connection
        redis = get_redis_connection()
        llm_data = redis.hgetall("llm:cost:total")
        
        if llm_data:
            llm_costs = {
                "input_tokens": int(llm_data.get(b"input_tokens", 0)),
                "output_tokens": int(llm_data.get(b"output_tokens", 0)),
                "cost_usd": float(llm_data.get(b"cost_usd", 0.0)),
            }
        else:
            llm_costs = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    except Exception:
        llm_costs = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    return TotalCostResponse(
        embeddings=CostSummary(
            tokens=embedding_costs["tokens"],
            embeddings=embedding_costs["embeddings"],
            input_tokens=None,
            output_tokens=None,
            cost_usd=embedding_costs["cost_usd"],
        ),
        llm=CostSummary(
            tokens=llm_costs["input_tokens"] + llm_costs["output_tokens"],
            embeddings=None,
            input_tokens=llm_costs["input_tokens"],
            output_tokens=llm_costs["output_tokens"],
            cost_usd=llm_costs["cost_usd"],
        ),
        total_cost_usd=embedding_costs["cost_usd"] + llm_costs["cost_usd"],
    )


@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(
    limit: int = 10,
    _user: User = Depends(require_superuser),
) -> TopUsersResponse:
    """Get top users by cost.

    Args:
        limit: Maximum number of users to return
        _user: Superuser dependency

    Returns:
        Top users by cost
    """
    users = await get_user_costs(limit=limit)
    
    return TopUsersResponse(
        users=[UserCost(**user) for user in users]
    )


@router.get("/breakdown", response_model=CostBreakdownResponse)
async def get_cost_breakdown(
    _user: User = Depends(require_superuser),
) -> CostBreakdownResponse:
    """Get comprehensive cost breakdown by operation.

    Args:
        _user: Superuser dependency

    Returns:
        Full cost breakdown
    """
    today = datetime.now(UTC).date().isoformat()
    month = datetime.now(UTC).strftime("%Y-%m")

    # Get daily costs
    embedding_daily = await get_daily_cost(today)
    llm_daily = await get_daily_llm_cost(today)

    # Get monthly costs
    embedding_monthly = await get_monthly_cost(month)
    llm_monthly = await get_monthly_llm_cost(month)

    # Get total costs
    embedding_total = await get_total_cost()
    
    # Get LLM total
    try:
        from app.workers.queue import get_redis_connection
        redis = get_redis_connection()
        llm_total_data = redis.hgetall("llm:cost:total")
        
        if llm_total_data:
            llm_total = {
                "input_tokens": int(llm_total_data.get(b"input_tokens", 0)),
                "output_tokens": int(llm_total_data.get(b"output_tokens", 0)),
                "cost_usd": float(llm_total_data.get(b"cost_usd", 0.0)),
            }
        else:
            llm_total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    except Exception:
        llm_total = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    return CostBreakdownResponse(
        daily=DailyCostResponse(
            date=today,
            embeddings=CostSummary(
                tokens=embedding_daily["tokens"],
                embeddings=embedding_daily["embeddings"],
                input_tokens=None,
                output_tokens=None,
                cost_usd=embedding_daily["cost_usd"],
            ),
            llm=CostSummary(
                tokens=llm_daily["input_tokens"] + llm_daily["output_tokens"],
                embeddings=None,
                input_tokens=llm_daily["input_tokens"],
                output_tokens=llm_daily["output_tokens"],
                cost_usd=llm_daily["cost_usd"],
            ),
            total_cost_usd=embedding_daily["cost_usd"] + llm_daily["cost_usd"],
        ),
        monthly=MonthlyCostResponse(
            month=month,
            embeddings=CostSummary(
                tokens=embedding_monthly["tokens"],
                embeddings=embedding_monthly["embeddings"],
                input_tokens=None,
                output_tokens=None,
                cost_usd=embedding_monthly["cost_usd"],
            ),
            llm=CostSummary(
                tokens=llm_monthly["input_tokens"] + llm_monthly["output_tokens"],
                embeddings=None,
                input_tokens=llm_monthly["input_tokens"],
                output_tokens=llm_monthly["output_tokens"],
                cost_usd=llm_monthly["cost_usd"],
            ),
            total_cost_usd=embedding_monthly["cost_usd"] + llm_monthly["cost_usd"],
        ),
        total=TotalCostResponse(
            embeddings=CostSummary(
                tokens=embedding_total["tokens"],
                embeddings=embedding_total["embeddings"],
                input_tokens=None,
                output_tokens=None,
                cost_usd=embedding_total["cost_usd"],
            ),
            llm=CostSummary(
                tokens=llm_total["input_tokens"] + llm_total["output_tokens"],
                embeddings=None,
                input_tokens=llm_total["input_tokens"],
                output_tokens=llm_total["output_tokens"],
                cost_usd=llm_total["cost_usd"],
            ),
            total_cost_usd=embedding_total["cost_usd"] + llm_total["cost_usd"],
        ),
    )
