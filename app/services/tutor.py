"""
Tutor Service - Q&A with anti-hallucination enforcement.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AnswerNotFoundError, SessionNotFoundError
from app.core.llm import count_tokens, generate_chat_completion
from app.models import TutorMessage, TutorSession
from app.schemas import AskResponse, CodeReference
from app.services import check_api_readiness
from app.services.search import search_code

settings = get_settings()
logger = structlog.get_logger(__name__)

TUTOR_SYSTEM_PROMPT = """You are a code tutor helping developers understand a codebase.
You MUST follow these rules strictly:

1. ONLY answer based on the provided code context
2. ALWAYS cite specific files and line numbers for every claim
3. If you cannot find the answer in the provided context, say: "This could not be found in the repository."
4. Never make up or assume information not in the context
5. Be concise but thorough

Format your response as JSON with this structure:
{
  "answer": "Your explanation here",
  "references": [{"file": "path/to/file.py", "lines": "10-25", "symbol": "function_name"}],
  "confidence": 0.85,
  "answered": true
}

If you cannot answer, use:
{
  "answer": "This could not be found in the repository.",
  "references": [],
  "confidence": 0.0,
  "answered": false
}"""


async def create_session(
    db: AsyncSession,
    repo_id: str,
    initial_context: str | None = None,
) -> TutorSession:
    """Create a new tutor session for a repository."""
    # Verify repo is ready
    repo = await check_api_readiness(db, repo_id, "session")
    
    # Generate repo context summary
    context_summary = f"""Repository: {repo.owner}/{repo.name}
Language: {repo.primary_language or 'Multiple'}
Files: {repo.total_files or 0}
Indexed Chunks: {repo.total_chunks or 0}"""
    
    if initial_context:
        context_summary += f"\nFocus Area: {initial_context}"
    
    session = TutorSession(
        id=str(uuid4()),
        repo_id=repo_id,
        repo_context_summary=context_summary,
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    await logger.ainfo(
        "tutor_session_created",
        session_id=session.id,
        repo_id=repo_id,
    )
    
    return session


async def get_session(
    db: AsyncSession,
    session_id: str,
) -> TutorSession:
    """Get a tutor session by ID."""
    result = await db.execute(
        select(TutorSession).where(TutorSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise SessionNotFoundError(session_id)
    
    # Check expiry
    ttl_hours = settings.session_ttl_hours
    age = datetime.now(timezone.utc) - session.last_activity_at.replace(
        tzinfo=timezone.utc
    )
    if age.total_seconds() > ttl_hours * 3600:
        raise SessionNotFoundError(session_id)  # Expired
    
    return session


async def ask_question(
    db: AsyncSession,
    repo_id: str,
    session_id: str,
    question: str,
) -> AskResponse:
    """
    Ask a question to the tutor.
    
    Implements anti-hallucination by grounding answers in code context.
    """
    # Get session
    session = await get_session(db, session_id)
    
    # Verify repo matches
    if session.repo_id != repo_id:
        raise SessionNotFoundError(session_id)
    
    # Search for relevant code
    results, _ = await search_code(
        db,
        repo_id,
        question,
        limit=5,
        min_score=settings.similarity_threshold,
    )
    
    # Check if we have enough context
    if not results:
        # No relevant code found
        return AskResponse(
            session_id=session_id,
            question=question,
            answer="This could not be found in the repository.",
            references=[],
            confidence=0.0,
            answered=False,
        )
    
    # Build context from search results
    code_context = "\n\n---\n\n".join(
        f"File: {r.file_path} (lines {r.start_line}-{r.end_line})\n"
        f"Symbol: {r.symbol or 'N/A'}\n"
        f"```{r.language or ''}\n{r.content}\n```"
        for r in results
    )
    
    # Get conversation history
    history = await get_recent_messages(db, session_id)
    
    # Build messages
    messages = [{"role": "system", "content": TUTOR_SYSTEM_PROMPT}]
    
    # Add conversation context
    if session.rolling_conversation_summary:
        messages.append({
            "role": "system",
            "content": f"Previous conversation summary: {session.rolling_conversation_summary}",
        })
    
    # Add recent history
    for msg in history[-settings.max_conversation_history :]:
        messages.append({"role": msg.role, "content": msg.content})
    
    # Add current question with context
    user_message = f"""Code Context:
{code_context}

Question: {question}

Remember: Answer ONLY based on the code context above. Cite specific files and lines."""
    
    messages.append({"role": "user", "content": user_message})
    
    # Generate response
    response_text = await generate_chat_completion(messages, temperature=0.3)
    
    # Parse response
    try:
        response_data = json.loads(response_text)
        answer = response_data.get("answer", response_text)
        references = [
            CodeReference(
                file=ref.get("file", ""),
                lines=ref.get("lines", ""),
                symbol=ref.get("symbol"),
            )
            for ref in response_data.get("references", [])
        ]
        confidence = response_data.get("confidence", 0.5)
        answered = response_data.get("answered", True)
    except json.JSONDecodeError:
        # Fallback if response isn't valid JSON
        answer = response_text
        references = [
            CodeReference(file=r.file_path, lines=f"{r.start_line}-{r.end_line}")
            for r in results[:3]
        ]
        confidence = 0.5
        answered = True
    
    # Store messages
    user_msg = TutorMessage(
        session_id=session_id,
        role="user",
        content=question,
    )
    db.add(user_msg)
    await db.flush()  # Flush individually to avoid asyncpg batch UUID issue
    
    assistant_msg = TutorMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        references=json.dumps([r.model_dump() for r in references]),
    )
    db.add(assistant_msg)
    
    # Update rolling summary if needed
    await update_rolling_summary(db, session)
    
    await db.commit()
    
    await logger.ainfo(
        "tutor_question_answered",
        session_id=session_id,
        question=question[:50],
        answered=answered,
        confidence=confidence,
    )
    
    return AskResponse(
        session_id=session_id,
        question=question,
        answer=answer,
        references=references,
        confidence=confidence,
        answered=answered,
    )


async def get_recent_messages(
    db: AsyncSession,
    session_id: str,
    limit: int = 10,
) -> list[TutorMessage]:
    """Get recent messages from a session."""
    result = await db.execute(
        select(TutorMessage)
        .where(TutorMessage.session_id == session_id)
        .order_by(TutorMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(result.scalars().all())
    messages.reverse()  # Chronological order
    return messages


async def update_rolling_summary(
    db: AsyncSession,
    session: TutorSession,
) -> None:
    """Update the rolling conversation summary."""
    # Get recent messages
    messages = await get_recent_messages(db, session.id, limit=10)
    
    if len(messages) < 4:
        return  # Not enough history yet
    
    # Build summary from messages
    summary_parts = []
    for msg in messages[-6:]:
        if msg.role == "user":
            summary_parts.append(f"Q: {msg.content[:100]}")
        else:
            summary_parts.append(f"A: {msg.content[:100]}")
    
    summary = " | ".join(summary_parts)
    
    # Truncate to token limit
    while count_tokens(summary) > settings.max_conversation_tokens:
        summary = summary[100:]  # Trim from start
    
    session.rolling_conversation_summary = summary
