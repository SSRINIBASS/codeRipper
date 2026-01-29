"""
Tutor API - Session and Q&A endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware import validate_api_key
from app.models import APIKey
from app.schemas import (
    AskRequest,
    AskResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionInfoResponse,
)
from app.services.tutor import ask_question, create_session, get_session

router = APIRouter(prefix="/tutor", tags=["Tutor"])


@router.post("/{repo_id}/session", response_model=SessionCreateResponse)
async def create_tutor_session(
    repo_id: Annotated[str, Path(description="Repository ID")],
    request: SessionCreateRequest = SessionCreateRequest(),
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> SessionCreateResponse:
    """
    Create a new tutor session for a repository.
    
    Requires INDEXED state. Sessions expire after 24 hours of inactivity.
    """
    session = await create_session(
        db,
        repo_id,
        initial_context=request.initial_context,
    )
    
    return SessionCreateResponse(
        session_id=session.id,
        repo_id=repo_id,
        repo_context_summary=session.repo_context_summary or "",
        created_at=session.created_at,
    )


@router.post("/{repo_id}/ask", response_model=AskResponse)
async def ask_tutor(
    repo_id: Annotated[str, Path(description="Repository ID")],
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> AskResponse:
    """
    Ask the tutor a question about the repository.
    
    Answers are grounded in the actual codebase. If the answer cannot
    be found in the code, the tutor will explicitly say so.
    
    Anti-hallucination rules:
    - All claims must cite code references
    - Confidence threshold of 0.65 for relevant results
    - No assumptions beyond the indexed code
    """
    return await ask_question(
        db,
        repo_id,
        request.session_id,
        request.question,
    )


@router.get("/{repo_id}/session/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(
    repo_id: Annotated[str, Path(description="Repository ID")],
    session_id: Annotated[str, Path(description="Session ID")],
    db: AsyncSession = Depends(get_db),
    api_key: Annotated[APIKey | None, Depends(validate_api_key)] = None,
) -> SessionInfoResponse:
    """
    Get information about a tutor session.
    """
    from sqlalchemy import func, select
    from app.models import TutorMessage
    
    session = await get_session(db, session_id)
    
    # Count messages
    result = await db.execute(
        select(func.count()).where(TutorMessage.session_id == session_id)
    )
    message_count = result.scalar() or 0
    
    return SessionInfoResponse(
        session_id=session.id,
        repo_id=session.repo_id,
        repo_context_summary=session.repo_context_summary or "",
        rolling_conversation_summary=session.rolling_conversation_summary,
        message_count=message_count,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
    )
