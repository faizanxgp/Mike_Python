"""
Authentication module - JWT token validation and user authentication
"""

from functools import wraps
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.keycloak_service import keycloak_service

security = HTTPBearer()

async def jwt_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to validate JWT token and return user info
    """
    try:
        token = credentials.credentials
        user_info, permissions = await keycloak_service.verify_token(token)
        
        # Add permissions to user info
        user_info["permissions"] = permissions
        
        return user_info
    
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

def require_role(required_role: str):
    """
    Decorator to require specific role for endpoint access
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs (injected by dependency)
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Check if user has required role
            user_roles = current_user.get("realm_access", {}).get("roles", [])
            client_roles = []
            
            # Get client roles
            resource_access = current_user.get("resource_access", {})
            for client, access in resource_access.items():
                client_roles.extend(access.get("roles", []))
            
            all_roles = user_roles + client_roles
            
            if required_role not in all_roles and "admin" not in all_roles:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Role '{required_role}' required for this operation"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_permission(required_permission: str):
    """
    Decorator to require specific permission for endpoint access
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            permissions = current_user.get("permissions", [])
            
            if required_permission not in permissions and "api_all_endpoints" not in permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission '{required_permission}' required for this operation"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
