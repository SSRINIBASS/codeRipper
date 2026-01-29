"""
LLM Client - Local embeddings with sentence-transformers and Hugging Face API for chat.
"""

import asyncio
from functools import lru_cache
from typing import Any

from huggingface_hub import InferenceClient
from sentence_transformers import SentenceTransformer
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

settings = get_settings()

# Lazy-loaded models
_embedding_model: SentenceTransformer | None = None
_hf_client: InferenceClient | None = None


def get_embedding_model() -> SentenceTransformer:
    """Get or create sentence-transformers embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def get_hf_client() -> InferenceClient:
    """Get or create Hugging Face Inference client."""
    global _hf_client
    if _hf_client is None:
        _hf_client = InferenceClient(token=settings.huggingface_api_key or None)
    return _hf_client


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count (approximation without tiktoken).
    
    Uses simple word-based estimation: ~1.3 tokens per word.
    """
    # Simple estimation: split on whitespace and punctuation
    words = text.split()
    return int(len(words) * 1.3)


async def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding for text using local sentence-transformers.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector (384 dimensions for all-MiniLM-L6-v2)
    """
    model = get_embedding_model()
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None,
        lambda: model.encode(text, convert_to_numpy=True)
    )
    
    return embedding.tolist()


async def generate_embeddings_batch(
    texts: list[str],
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        batch_size: Batch size (used for progress, model handles internally)
        
    Returns:
        List of embedding vectors
    """
    model = get_embedding_model()
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None,
        lambda: model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    )
    
    return embeddings.tolist()


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def generate_completion(
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
) -> str:
    """
    Generate a chat completion using Hugging Face Inference API.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        
    Returns:
        Generated text
    """
    client = get_hf_client()
    
    # Build prompt with system context
    if system_prompt:
        full_prompt = f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
    else:
        full_prompt = f"<s>[INST] {prompt} [/INST]"
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.text_generation(
            full_prompt,
            model=settings.llm_model,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
        )
    )
    
    return response


async def generate_chat_completion(
    messages: list[dict[str, str]],
    max_tokens: int = 2000,
    temperature: float = 0.7,
) -> str:
    """
    Generate a chat completion with message history.
    
    Args:
        messages: List of messages with role and content
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        
    Returns:
        Generated text
    """
    client = get_hf_client()
    
    # Convert messages to Mistral-style prompt
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "system":
            prompt_parts.append(f"<s>[INST] <<SYS>>\n{content}\n<</SYS>>\n\n")
        elif role == "user":
            if prompt_parts and not prompt_parts[-1].endswith("[/INST]"):
                prompt_parts.append(f"{content} [/INST]")
            else:
                prompt_parts.append(f"<s>[INST] {content} [/INST]")
        elif role == "assistant":
            prompt_parts.append(f" {content} </s>")
    
    full_prompt = "".join(prompt_parts)
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.text_generation(
            full_prompt,
            model=settings.llm_model,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
        )
    )
    
    return response
