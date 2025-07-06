"""
Keycloak Router - Authentication and authorization endpoints
Handles token validation, user info, and auth status
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Dict

from app.core.auth import jwt_required, keycloak_service

router = APIRouter()

@router.get("/user-info")
async def get_user_info(current_user: dict = Depends(jwt_required)):
    """Get current user information from token"""
    return {
        "user": current_user,
        "authenticated": True
    }

@router.get("/permissions")
async def get_user_permissions(current_user: dict = Depends(jwt_required)):
    """Get user permissions and roles"""
    try:
        permissions = await keycloak_service.get_user_permissions(current_user)
        return {
            "permissions": permissions,
            "user": current_user.get("preferred_username", "unknown")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get permissions: {str(e)}")

@router.post("/refresh-token")
async def refresh_token(request: Request):
    """Refresh access token using refresh token"""
    try:
        data = await request.json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token required")
        
        new_tokens = await keycloak_service.refresh_token(refresh_token)
        return new_tokens
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")

@router.get("/health")
async def auth_health():
    """Check authentication service health"""
    try:
        health = await keycloak_service.health_check()
        return health
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "keycloak_available": False
        }


@router.delete("/delete_permission")
# @jwt_token commented out
async def api_delete_permission(request: Request):
    try:
        username = request.state.email
        response = await delete_permission(username)
        
        return response
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"delete_permission. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/unassign_permission")
# @jwt_token commented out
async def api_unassign_permission(request: Request):
    try:
        payload = await request.json()
        resources, username = payload.get("resource_names"), payload.get("username")
        response = await unassign_permission(resources, username)
        
        return response
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"unassign_permission. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/assign_permission")
# @jwt_token commented out
async def api_assign_permission(request: Request):
    try:
        payload = await request.json()
        resources, username = payload.get("resources"), payload.get("username")
        response = await assign_permission(resources, username)
        
        if response.status_code in [200, 201, 204]:
            return {"detail": "permission assigned successfully"}
        
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"assign_permission. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/create_user")
# @jwt_token commented out
async def api_create_user(request: Request):
    try:
        payload = await request.json()
        response = await create_user(payload)
        
        # if response.status_code in [200, 201, 204]:
        #     return {"detail": "user created successfully"}
        # else:
        #     raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"create_user. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        

@router.delete("/delete_user")
# @jwt_token commented out
async def api_delete_user(request: Request):
    try:
        data = await request.json()
        username = data.get("username")
        response = await delete_user(username)
        return {"detail": response}         
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"delete_user. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        
        
@router.post("/assign_role")
# @jwt_token commented out
async def api_assign_role(request: Request):
    try:
        data = await request.json()
        username, role = data.get("username"), data.get("role")
        user_details = (await retrieve_user_details(username)).json()
        if not user_details: return HTTPException(status_code=404, detail="user not found")
        user_id = user_details[0].get("id")
        role_id = (await get_client_role(role)).json().get("id")
        payload = [{
            "id": role_id,
            "name": role
            }]
        response = await assign_client_role(payload, user_id)
        
        if response.status_code in [200, 201, 204]:
            return {"detail": "role assigned successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"assign_role. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_user_roles")
# @jwt_token commented out
async def api_get_user_roles(request: Request):
    try:
        user_id = request.state.user_id
        role_names = await get_user_roles(user_id)
        return {"detail": role_names}
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"get_user_roles. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        

@router.delete("/remove_role")
# @jwt_token commented out
async def api_remove_role(request: Request):
    try:
        data = await request.json()
        username, role = data.get("username"), data.get("role")
        user_details = (await retrieve_user_details(username)).json()
        if not user_details: return HTTPException(status_code=404, detail="user not found")
        user_id = user_details[0].get("id")
        role_id = (await get_client_role(role)).json().get("id")
        payload = [{
            "id": role_id,
            "name": role
            }]
        response = await remove_client_role(payload, user_id)
        
        if response.status_code in [200, 201, 204]:
            return {"detail": "role removed successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"remove_role. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        

@router.post("/retrieve_user_details")
async def api_retrieve_user_details(request: Request):
    try:
        data = await request.json()
        username = data.get("username")
        response:httpx.Response = await retrieve_user_details(username)
        
        if response.status_code in [200, 201, 204]:
            if response.json():
                return {"detail": response.json()[0]}
            else: 
                raise HTTPException(status_code=404, detail="no record found")
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"retrieve_user_details. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


# if action carried out by concerned user (non-admin)
@router.post("/reset_password")
# @jwt_token commented out
async def api_reset_password(request: Request):
    try:
        user_id = request.state.user_id
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in request state")
        payload = await request.json()
        response: httpx.Response = await reset_password(payload, user_id)
        if response.status_code in [200, 201, 204]:
            return {"detail": "password reset successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"reset_password. error: {tb_str}")
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


# if action carried out by admin
@router.post("/admin_reset_password")
# @jwt_token commented out
async def api_reset_password(request: Request):
    try:
        payload = await request.json()
        response: httpx.Response = await reset_password(payload)
        if response.status_code in [200, 201, 204]:
            return {"detail": "password reset successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"reset_password. error: {tb_str}")
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        

@router.post("/forgot_password")
# @jwt_token commented out
async def api_forgot_password(request: Request):
    try:
        user_id = request.state.user_id # action carried out by concerned user (non-admin)
        response:httpx.Response = await forgot_password(user_id)
        if response.status_code in [200, 201, 204]:
            return {"detail": "password reset link sent"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"forgot_password. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        

# This action will carried out by concerned user (non-admin)
@router.post("/update_user_details")
# @jwt_token commented out
async def api_update_user_details(request: Request):
    try:
        user_id = request.state.user_id
        payload = await request.json()
        response:httpx.Response = await update_user_details(payload, user_id)
        
        if response.status_code in [200, 201, 204]:
            return {"detail": "user details updated successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"update_user_details. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))
        

# This action will carried out by concerned user (non-admin)
@router.get("/logout_user")
# @jwt_token commented out
async def api_logout_user(request: Request):
    try:
        user_id = request.state.user_id 
        response:httpx.Response = await logout_user(user_id)
        
        if response.status_code in [200, 201, 204]:
            return {"detail": "user logged out successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"logout_user. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/users_status")
# @jwt_token commented out
async def api_users_status(request: Request):
    try:
        details = await users_status()
        return {"detail": details}
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"logout_user. error: {tb_str}")
        
        if isinstance (e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/replace_user_role")
# @jwt_token commented out
async def api_replace_user_role(request: Request):
    try:
        data = await request.json()
        username, new_role = data.get("username"), data.get("role")
        
        # Get user details
        user_details = (await retrieve_user_details(username)).json()
        if not user_details: 
            raise HTTPException(status_code=404, detail="user not found")
        user_id = user_details[0].get("id")
        
        # Get all current roles for the user
        current_roles = await get_user_roles(user_id)
        
        # Remove all existing roles
        if current_roles:
            # Get role details for removal
            roles_to_remove = []
            for role_name in current_roles:
                try:
                    role_details = (await get_client_role(role_name)).json()
                    roles_to_remove.append({
                        "id": role_details.get("id"),
                        "name": role_name
                    })
                except Exception as role_error:
                    print(f"Warning: Could not get details for role {role_name}: {role_error}")
                    continue
            
            # Remove all roles in one call
            if roles_to_remove:
                remove_response = await remove_client_role(roles_to_remove, user_id)
                if remove_response.status_code not in [200, 201, 204]:
                    raise HTTPException(status_code=remove_response.status_code, 
                                      detail=f"Failed to remove existing roles: {remove_response.text}")
        
        # Assign the new role
        new_role_id = (await get_client_role(new_role)).json().get("id")
        if not new_role_id:
            raise HTTPException(status_code=404, detail=f"Role '{new_role}' not found")
            
        new_role_payload = [{
            "id": new_role_id,
            "name": new_role
        }]
        assign_response = await assign_client_role(new_role_payload, user_id)
        
        if assign_response.status_code in [200, 201, 204]:
            return {"detail": f"All roles replaced. User now has role: {new_role}"}
        else:
            raise HTTPException(status_code=assign_response.status_code, 
                              detail=f"Failed to assign new role: {assign_response.text}")
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"replace_user_role. error: {tb_str}")
        
        if isinstance(e, HTTPException):
            raise e
        else:            raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle_user_status")
# @jwt_token commented out
async def api_toggle_user_status(request: Request):
    """
    API endpoint to enable or disable a user in Keycloak.
    
    Expected JSON payload:
    {
        "username": "user@example.com",
        "action": "disable"  # or "enable"
    }
    """
    try:
        payload = await request.json()
        username = payload.get("username")
        action = payload.get("action")
        
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        
        if not action:
            raise HTTPException(status_code=400, detail="Action is required")
        
        if action.lower() not in ["enable", "disable"]:
            raise HTTPException(status_code=400, detail="Action must be either 'enable' or 'disable'")
        
        response = await toggle_user_status(username, action)
        
        return response
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"toggle_user_status. error: {tb_str}")
        
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/login_events")
# @jwt_token commented out
async def api_login_events(request: Request):
    """
    API endpoint to retrieve LOGIN events for a specific user or all users.
    
    Expected JSON payload:
    {
        "username": "user@example.com"  # Optional - if not provided, returns events for all users
    }
    
    Returns login events for the specified user or all users if no username is provided.
    """
    try:
        try:
            payload = await request.json()
        except:
            payload = {}  # Handle empty request body
            
        username = payload.get("username") if payload else None
        
        response = await get_login_events(username)
        
        return response
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"login_events. error: {tb_str}")
        
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/get_user_permissions")
# @jwt_token commented out
async def api_get_user_permissions(request: Request):
    """
    API endpoint to retrieve all permissions (resources) granted to a specific user.
    
    Expected JSON payload:
    {
        "username": "user@example.com"  # Required - username to get permissions for
    }
    
    Returns all resources/permissions granted to the specified user including:
    - resource_name: Name of the resource
    - resource_id: Unique identifier of the resource
    - resource_type: Type of the resource (e.g., "urn:benyon:resource")
    """
    try:
        data = await request.json()
        username = data.get("username")
        
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        
        response = await get_user_permissions(username)
        
        return response
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"get_user_permissions. error: {tb_str}")
        
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/create_resource")
# @jwt_token commented out
async def api_create_resource(request: Request):
    """
    API endpoint to create a new resource in Keycloak.
    
    Expected JSON payload:
    {
        "name": "resource_name",           # Required - unique resource name
        "type": "resource_type"            # Required - type of resource (e.g., "file", "dir", "api")
    }
    
    Note: 
    - displayName will be automatically set to the same value as name
    - Other fields (icon_uri, ownerManagedAccess, attributes, scopes) will use default values
    
    Returns success message if resource is created successfully.
    """
    try:
        payload = await request.json()
        response = await create_resource_api(payload)
        
        if response.status_code in [200, 201, 204]:
            return {"detail": "resource created successfully"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"create_resource. error: {tb_str}")
        
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))