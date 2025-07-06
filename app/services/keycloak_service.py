"""
Keycloak Service - Handles authentication and authorization with Keycloak
"""

import time
from typing import Dict, Optional
from keycloak import KeycloakOpenID, KeycloakAdmin
from fastapi import HTTPException

from app.core.config import (
    KEYCLOAK_URL, 
    KEYCLOAK_REALM_NAME, 
    KEYCLOAK_BACKEND_CLIENT_ID, 
    KEYCLOAK_BACKEND_CLIENT_SECRET
)


class KeycloakService:
    """Service for Keycloak operations"""
    
    def __init__(self):
        self.keycloak_openid = KeycloakOpenID(
            server_url=KEYCLOAK_URL,
            client_id=KEYCLOAK_BACKEND_CLIENT_ID,
            realm_name=KEYCLOAK_REALM_NAME,
            client_secret_key=KEYCLOAK_BACKEND_CLIENT_SECRET
        )
    
    async def verify_token(self, token: str) -> tuple[Dict, list]:
        """Verify and decode JWT token"""
        try:
            # Decode and validate token
            decoded_token = await self.keycloak_openid.a_decode_token(token, validate=True)
            
            # Introspect token for additional validation
            introspection = await self.keycloak_openid.a_introspect(token)
            
            if not introspection.get("active"):
                raise Exception("Token is not active")
            
            # Check expiration
            if time.time() > introspection.get('exp', 0):
                raise Exception("Token has expired")
            
            # Get permissions
            try:
                auth_status = self.keycloak_openid.uma_permissions(token)
                permissions = [
                    perm_dict.get("rsname", "") 
                    for perm_dict in auth_status 
                    if "rsname" in perm_dict
                ]
            except Exception:
                permissions = []
            
            return introspection, permissions
        
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
    
    async def get_user_permissions(self, user_info: Dict) -> list:
        """Get user permissions from user info"""
        try:
            # Extract roles from token
            realm_access = user_info.get("realm_access", {})
            roles = realm_access.get("roles", [])
            
            # Extract resource access
            resource_access = user_info.get("resource_access", {})
            client_roles = []
            for client, access in resource_access.items():
                client_roles.extend(access.get("roles", []))
            
            return {
                "realm_roles": roles,
                "client_roles": client_roles,
                "all_roles": list(set(roles + client_roles))
            }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get permissions: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> Dict:
        """Refresh access token"""
        try:
            token_response = await self.keycloak_openid.a_refresh_token(refresh_token)
            return {
                "access_token": token_response["access_token"],
                "refresh_token": token_response.get("refresh_token", refresh_token),
                "expires_in": token_response.get("expires_in", 300)
            }
        
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")
    
    async def health_check(self) -> Dict:
        """Check Keycloak service health"""
        try:
            # Try to get well-known configuration
            well_known = await self.keycloak_openid.a_well_known()
            
            return {
                "status": "healthy",
                "keycloak_available": True,
                "realm": KEYCLOAK_REALM_NAME,
                "issuer": well_known.get("issuer", "unknown")
            }
        
        except Exception as e:
            return {
                "status": "unhealthy",
                "keycloak_available": False,
                "error": str(e)
            }


# Global service instance
keycloak_service = KeycloakService()
