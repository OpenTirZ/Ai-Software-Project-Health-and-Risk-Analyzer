"""
FastAPI dependency: get the currently authenticated user from the
Authorization: Bearer <token> header.

Usage in a route:
    from Backend.auth.dependencies import get_current_user

    @router.get("/protected")
    def protected_route(current_user: dict = Depends(get_current_user)):
        ...
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from Backend.auth.security import decode_access_token
from Backend.persistence import get_user

_bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    Dependency that validates the Bearer token and returns the user document.

    Raises:
        401 Unauthorized – token missing, invalid, or expired.
        401 Unauthorized – user no longer exists in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = get_user(user_id)
    if user is None:
        raise credentials_exception

    return user
