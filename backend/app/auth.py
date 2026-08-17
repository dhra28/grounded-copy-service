from fastapi import Header, HTTPException, status

from app.config import settings


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> bool:
    """Dependency for protected routes. Compares against SERVICE_API_KEY
    from .env — this is our API's own key, not the LLM provider's key.
    Reviewers get this one key and use it for every call."""
    if x_api_key != settings.service_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass it as the X-API-Key header.",
        )
    return True