import time
import traceback
from functools import wraps
from datetime import datetime
from fastapi import HTTPException, Request
from keycloak import KeycloakOpenID
from jwcrypto.jwt import JWTExpired
from jwcrypto.jws import InvalidJWSObject, InvalidJWSSignature

from app.core.config import (
    KEYCLOAK_URL,
    KEYCLOAK_REALM_NAME, 
    KEYCLOAK_BACKEND_CLIENT_ID,
    KEYCLOAK_BACKEND_CLIENT_SECRET
)


class KeycloakAuth:
    def __init__(self):
        self.keycloak_openid = KeycloakOpenID(
            server_url=KEYCLOAK_URL,
            client_id=KEYCLOAK_BACKEND_CLIENT_ID,
            realm_name=KEYCLOAK_REALM_NAME,
            client_secret_key=KEYCLOAK_BACKEND_CLIENT_SECRET
        )
    
    async def verify_token(self, token: str):
        """Verify and decode Keycloak token"""
        dec_tok = await self.keycloak_openid.a_decode_token(token, validate=True)
        intr_tok = await self.keycloak_openid.a_introspect(token)
        
        if not intr_tok.get("active"):
            raise Exception("inactive auth token")
            
        if time.time() > intr_tok.get('exp'):
            raise Exception("auth token expired")
        
        auth_status = self.keycloak_openid.uma_permissions(token)
        permissions = [
            permissions_dict[i] 
            for permissions_dict in auth_status 
            for i in permissions_dict 
            if i == "rsname"
        ]
        
        return intr_tok, permissions


# Global auth instance
auth = KeycloakAuth()


def require_auth(required_role: str = None):
    """
    Decorator for protecting endpoints with Keycloak authentication
    
    Args:
        required_role: Optional role requirement
    """
    def decorator(fn):
        @wraps(fn)
        async def decorated(request: Request, *args, **kwargs):
            headers = request.headers
            
            # Extract token
            try:
                if "Authorization" not in headers:
                    raise HTTPException(
                        status_code=401, 
                        detail="Missing authorization token"
                    )
                    
                token = headers.get('Authorization').split(" ")[1]
            except (IndexError, AttributeError):
                raise HTTPException(
                    status_code=401, 
                    detail="Invalid authorization header format"
                )
            
            # Verify token and extract user info
            try:
                intr_tok, permissions = await auth.verify_token(token)
                
                # Set request state
                request.state.permissions = permissions
                request.state.roles = intr_tok.get("resource_access", {}).get("benyon_fe", {}).get("roles", [])
                request.state.user_id = intr_tok.get("sub")
                request.state.username = intr_tok.get("name")
                request.state.email = intr_tok.get("email")
                
                # Check role requirement
                if required_role and required_role not in request.state.roles:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Insufficient permissions. Required role: {required_role}"
                    )
                
            except HTTPException:
                raise
            except Exception as e:
                tb_str = traceback.format_exc()
                print(f"\n{datetime.now()} Authentication error: {tb_str}\n")
                
                if isinstance(e, (InvalidJWSObject, InvalidJWSSignature)):
                    raise HTTPException(status_code=401, detail="Invalid auth token")
                elif isinstance(e, JWTExpired):
                    raise HTTPException(status_code=401, detail="Auth token expired")
                else:
                    raise HTTPException(status_code=401, detail=str(e))
            
            return await fn(request, *args, **kwargs)
        return decorated
    return decorator
