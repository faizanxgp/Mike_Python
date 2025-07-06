from fastapi import HTTPException

from app.routers.utils.misc_keycloak_utils import *
from app.routers.utils.keycloak_vars import *


async def delete_permission(username: str, access_token=None):
    try:
        headers, _ = await obtain_headers()

        permission_name = f"permission_user_{username}"
        all_permissions = (await get_all_permissions()).json()
        relevant_permission = None
        for permission in all_permissions:
            if permission.get("name") == permission_name:
                relevant_permission = permission
                break
        if not relevant_permission: raise Exception("no existing permission found for this user")
        permission_id = relevant_permission.get("id")

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                base_url + ep_delete_permission.replace("[ENTER_PERMISSION_ID]", permission_id), 
                headers=headers
                )
        if response.status_code in [200, 201, 204]:
            return {"detail": "permission deleted"}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        raise e from e

async def unassign_permission(resources: list, username: str, access_token=None):
    try:
        print(f"Starting unassign_permission for user: {username}")
        print(f"Resources to unassign: {resources}")
        
        rem_resource_ids = []
        rem_resource_dict = {} # to store resource name against each resource id
        not_found_resources = [] # to track resources that don't exist
        
        for resource_name in resources:
            resource_id = await retrieve_resource(resource_name)
            print(f"Retrieved resource for {resource_name}: {resource_id}")
            
            if not resource_id:
                not_found_resources.append(resource_name)
                print(f"Resource {resource_name} not found, added to not_found_resources")
            else:
                # Extract the resource ID from the resource object
                actual_resource_id = resource_id.get("_id") if isinstance(resource_id, dict) else resource_id
                rem_resource_ids.append(actual_resource_id)
                rem_resource_dict[actual_resource_id] = resource_name
                print(f"Resource {resource_name} found with ID: {actual_resource_id}")
                
        print("rem_resource_ids:", rem_resource_ids)
        print("not_found_resources:", not_found_resources)

        # If no valid resource IDs found, handle gracefully
        if not rem_resource_ids:
            if not_found_resources:
                return {"detail": f"No permissions unassigned. Resources not found: {not_found_resources}"}
            else:
                return {"detail": "No valid resources provided for unassignment"}

        user_policy = await retrieve_user_policy(username)
        if not user_policy:
            raise Exception("policy not found for the given username")
        policy_id = user_policy.get("id")
        if not policy_id: 
            raise Exception("policy_id not found against the given username")
        
        permission_name = f"permission_user_{username}"
        permissions_response = await get_all_permissions()
        if permissions_response.status_code != 200:
            raise Exception(f"Failed to get permissions: {permissions_response.text}")
        
        all_permissions = permissions_response.json()
        if not all_permissions or not isinstance(all_permissions, list):
            all_permissions = []
            
        relevant_permission = None
        for permission in all_permissions:
            if permission and permission.get("name") == permission_name:
                relevant_permission = permission
                break
 
        if relevant_permission:
            permission_id = relevant_permission.get("id")
            
            resources_response = await get_resources_in_permission(permission_id)
            if resources_response.status_code != 200:
                raise Exception(f"Failed to get resources in permission: {resources_response.text}")
                
            resources_in_permission = resources_response.json()
            if not resources_in_permission or not isinstance(resources_in_permission, list):
                resources_in_permission = []
                
            resource_ids = [resource.get("_id") for resource in resources_in_permission if resource]
            print("resource_ids:", resource_ids)
            
            # check if all resources to be unassigned were earlier assigned or not?
            non_existent_permissions = []
            for rem_id in rem_resource_ids:
                if rem_id not in resource_ids: non_existent_permissions.append(rem_resource_dict[rem_id])
            
            updated_resource_ids = resource_ids.copy()
            for id in resource_ids:
                if id in rem_resource_ids: updated_resource_ids.remove(id)
            print("updated resource_ids:", updated_resource_ids)
            update_payload = (
                {
                    "id":permission_id,
                    "name":permission_name,
                    "description":"",
                    "type":"resource",
                    "logic":"POSITIVE",
                    "decisionStrategy":"UNANIMOUS",
                    "resources":updated_resource_ids,
                    "policies":[policy_id],
                    "scopes":[]
                }
            )
            response = await update_permission(permission_id, update_payload)
            if response.status_code in [200, 201, 204]:
                return_string = "permissions unassigned"
                if len(non_existent_permissions): return_string += f" (if existing). Following resources were not found assigned: {non_existent_permissions}"
                if len(not_found_resources): return_string += f". Following resources do not exist: {not_found_resources}"
                return {"detail": return_string}
        else:
            if not_found_resources:
                return {"detail": f"No existing permission found for this user. Resources not found: {not_found_resources}"}
            else:
                return {"detail": "no existing permission found for this user"}

        return response

    except Exception as e:
        raise e from e
    

async def assign_permission(resources: list, username: str, access_token=None):
    try:
        new_resource_ids = []
        for resource_info in resources:
            resource_name = resource_info.get("name")
            resource_type = resource_info.get("type")
            
            if not resource_name or not resource_type:
                raise Exception(f"Resource must have both 'name' and 'type' fields. Found: {resource_info}")
            
            resource_object = await retrieve_resource(resource_name)
            if not resource_object:
                # Resource doesn't exist, create it automatically
                print(f"Resource '{resource_name}' with type '{resource_type}' not found, creating new resource...")
                
                # Create resource with the specified type from input
                resource_payload = {
                    "name": resource_name,
                    "displayName": resource_name,
                    "type": resource_type,  # Use the type from input payload
                    "icon_uri": "",
                    "ownerManagedAccess": False,
                    "attributes": {},
                    "scopes": []
                }
                
                # Create the resource
                create_response = await create_resource(resource_payload, access_token)
                if create_response.status_code not in [200, 201, 204]:
                    raise Exception(f"Failed to create resource '{resource_name}': {create_response.text}")
                
                print(f"Successfully created resource '{resource_name}' with type '{resource_type}'")
                
                # Retrieve the newly created resource to get its ID
                resource_object = await retrieve_resource(resource_name)
                if not resource_object:
                    raise Exception(f"Failed to retrieve newly created resource '{resource_name}'")
            
            # Extract the resource ID from the resource object
            resource_id = resource_object.get("_id") if isinstance(resource_object, dict) else resource_object
            new_resource_ids.append(resource_id)

        # Try to retrieve user policy, create if it doesn't exist
        user_policy = await retrieve_user_policy(username)
        if not user_policy or not user_policy.get("id"):
            # Policy doesn't exist, create it
            print(f"User policy not found for {username}, creating new policy...")
            
            # Get user details to extract user ID
            user_details_response = await retrieve_user_details(username)
            if user_details_response.status_code not in [200, 201, 204]:
                raise Exception(f"Failed to retrieve user details for {username}")
            
            user_details = user_details_response.json()
            if not user_details:
                raise Exception(f"User {username} not found")
            
            user_id = user_details[0].get("id")
            if not user_id:
                raise Exception(f"User ID not found for {username}")
            
            # Create the user policy
            policy_payload = {
                "name": f"policy_user_{username}",
                "description": "",
                "users": [user_id],
                "logic": "POSITIVE"
            }
            
            policy_response = await create_user_policy(policy_payload, access_token)
            if policy_response.status_code not in [200, 201, 204]:
                raise Exception(f"Failed to create user policy for {username}: {policy_response.text}")
            
            print(f"Successfully created user policy for {username}")
            
            # Retrieve the newly created policy to get its ID
            user_policy = await retrieve_user_policy(username)
            if not user_policy or not user_policy.get("id"):
                raise Exception(f"Failed to retrieve newly created policy for {username}")
        
        policy_id = user_policy.get("id")
        
        permission_name = f"permission_user_{username}"
        all_permissions = (await get_all_permissions()).json()
        relevant_permission = None
        for permission in all_permissions:
            if permission.get("name") == permission_name:
                relevant_permission = permission
                break

        if relevant_permission:
            permission_id = relevant_permission.get("id")
            resource_ids = []
            resources_in_permission = (await get_resources_in_permission(permission_id)).json()
            resource_ids = [resource.get("_id") for resource in resources_in_permission]
            resource_ids.extend(new_resource_ids)
            update_payload = (
                {
                    "id":permission_id,
                    "name":permission_name,
                    "description":"",
                    "type":"resource",
                    "logic":"POSITIVE",
                    "decisionStrategy":"UNANIMOUS",
                    "resources":resource_ids,
                    "policies":[policy_id],
                    "scopes":[]
                }
            )
            response = await update_permission(permission_id, update_payload)
        else:
            create_payload = (
                {
                    "resources":new_resource_ids,
                    "policies":[policy_id],
                    "name":permission_name,
                    "description":"",
                    "decisionStrategy":"UNANIMOUS"
                }
            )
            response = await create_permission(create_payload)

        return response

    except Exception as e:
        raise e from e


async def create_user(payload, access_token=None):
    try:
        headers, _ = await obtain_headers(access_token)
        role = payload.pop("role", None)
        password = payload.pop("password", None)
        if not payload.get("username"):
            payload["username"] = payload.get("email")
        username = payload["username"]
        
        # create user in keycloak
        async with httpx.AsyncClient() as client:
            response = await client.post(base_url + ep_create_user, json=payload, headers=headers)
        if response.status_code not in [200, 201, 204]:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        # create policy for the user
        policy_payload = (
            {
                "name":f"policy_user_{payload.get('username')}",
                "description":"",
                "users":[(await retrieve_user_details(username)).json()[0].get("id")],
                "logic":"POSITIVE"
            }
        )
        response = await create_user_policy(policy_payload)
        if response.status_code not in [200, 201, 204]:
            raise HTTPException(status_code=response.status_code, detail=response.text)
                
        # set the role for the user
        username = payload.get("username")
        user_id = (await retrieve_user_details(username)).json()[0].get("id")
        role_id = (await get_client_role(role)).json().get("id")
        role_payload = [{
            "id": role_id,
            "name": role
            }]
        response = await assign_client_role(role_payload, user_id)
        if response.status_code not in [200, 201, 204]:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        # set password for the user
        password_payload = {
                            "username": username,
                            "type": "password",
                            "value": password,
                            "temporary": False
                        }
        response = await reset_password(password_payload)
        if response.status_code not in [200, 201, 204]:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        return response
    except Exception as e:
        raise e from e


async def delete_user(username, access_token=None):
    try:
        all_users = (await get_all_users()).json()
        user_id = None
        for user in all_users:
            if user.get("username") == username:
                user_id = user.get("id")
                break
        if not user_id: raise Exception(f"user with username {username} not found")
        
        cleanup_results = []
        
        # Step 1: Cleanup user permissions (if they exist)
        try:
            permission_result = await delete_permission(username, access_token)
            cleanup_results.append("permission deleted")
            print(f"Successfully deleted permissions for user: {username}")
        except Exception as perm_error:
            cleanup_results.append("permission not found or already deleted")
            print(f"Warning: Could not delete permissions for user {username}: {perm_error}")
        
        # Step 2: Cleanup user policy (if it exists)
        try:
            user_policy = await retrieve_user_policy(username, access_token)
            if user_policy and user_policy.get("id"):
                policy_id = user_policy.get("id")
                await delete_user_policy(policy_id, access_token)
                cleanup_results.append("policy deleted")
                print(f"Successfully deleted policy for user: {username}")
            else:
                cleanup_results.append("policy not found")
                print(f"No policy found for user: {username}")
        except Exception as policy_error:
            cleanup_results.append("policy not found or already deleted")
            print(f"Warning: Could not delete policy for user {username}: {policy_error}")
        
        # Step 3: Delete the user
        headers, _ = await obtain_headers(access_token)
        async with httpx.AsyncClient() as client:
            response = await client.delete(base_url + ep_delete_user.replace("[ENTER_USER_ID]", user_id), headers=headers)
        
        if response.status_code in [200, 201, 204]:
            cleanup_summary = ", ".join(cleanup_results)
            return f"user deleted successfully ({cleanup_summary})"
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
    except Exception as e:
        raise e from e


async def assign_client_role(payload, user_id: str, access_token=None):
    try:
        headers, _ = await obtain_headers()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                base_url + ep_assign_client_role.replace("[ENTER_USER_ID]", user_id), 
                json=payload, headers=headers
                )

        return response
    except Exception as e:
        raise e from e


async def remove_client_role(payload, user_id: str, access_token=None):
    headers, _ = await obtain_headers()
    async with httpx.AsyncClient() as client:
        response = await client.request("DELETE",
            base_url + ep_assign_client_role.replace("[ENTER_USER_ID]", user_id), 
            json=payload, headers=headers
            )

    return response


async def get_user_roles(user_id: str, access_token=None):
    try:
        headers, _ = await obtain_headers()
        roles = (await get_user_role_details(user_id)).json()
        role_names = [role.get("name") for role in roles]
        print("role_names:", role_names)
        return role_names
    except Exception as e:
        raise e from e


async def retrieve_user_details(username, access_token=None):
    try:
        headers, _ = await obtain_headers(access_token)
        query_params = {
        "username": username,
        "exact": True
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url + ep_retrieve_user, params=query_params, headers=headers)
        return response
    except Exception as e:
        raise e from e


async def reset_password(payload, user_id=None, access_token=None):
    """
    Resets the password for the user specified by username in payload or by user_id.
    """
    if not user_id:
        username = payload.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="username required")
        # retrieve user_id from keycloak
        user_details_response = await retrieve_user_details(username)
        user_details = user_details_response.json()
        if not user_details or not user_details[0].get("id"):
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user_details[0]["id"]
        # Remove username from payload before sending to Keycloak
        payload = {k: v for k, v in payload.items() if k != "username"}
    headers, _ = await obtain_headers(access_token)
    async with httpx.AsyncClient() as client:
        response = await client.put(
            base_url + ep_reset_password.replace("[ENTER_USER_ID]", user_id),
            json=payload, headers=headers
        )
    return response


async def forgot_password(user_id, access_token=None):
    headers, _ = await obtain_headers(access_token)
    payload = ["UPDATE_PASSWORD"]
    async with httpx.AsyncClient() as client:
        response = await client.put(
            base_url + ep_forgot_password.replace("[ENTER_USER_ID]", user_id), 
            json=payload, headers=headers
            )

    return response


async def update_user_details(payload, user_id, access_token=None):
    headers, _ = await obtain_headers(access_token)
    async with httpx.AsyncClient() as client:
        response = await client.put(
            base_url + ep_update_user_details.replace("[ENTER_USER_ID]", user_id), 
            json=payload, headers=headers
            )

    return response


async def logout_user(user_id, access_token=None):
    headers, _ = await obtain_headers(access_token)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            base_url + ep_logout_user.replace("[ENTER_USER_ID]", user_id), 
            headers=headers
            )

    return response


async def users_status(access_token=None):
    all_users = (await get_all_users()).json()
    print("all_users:", all_users)
    user_ids = [user.get("id") for user in all_users]
    usernames = [user.get("username") for user in all_users]
    full_names = [user.get("firstName") + " " + user.get("lastName") for user in all_users]
    emails = [user.get("email") for user in all_users]
    enabled_statuses = [user.get("enabled", True) for user in all_users]  # Default to True if not present
    
    details = {}
    for i, id in enumerate(user_ids):
        active_sessions = (await check_user_active(id)).json()
        session_status = "active" if (len(active_sessions)>0) else "inactive"
        user_roles = await get_user_roles(id)
        role_name = user_roles[0] if user_roles else ""
        details[usernames[i]] = {
            "full_name": full_names[i],
            "email": emails[i], 
            "role": role_name, 
            "session_status": session_status,
            "enabled": enabled_statuses[i]
        }
    
    return details

async def toggle_user_status(username: str, action: str, access_token=None):
    """
    Enable or disable a user in Keycloak.
    
    Args:
        username (str): The username of the user to enable/disable
        action (str): "enable" to enable the user, "disable" to disable the user
        access_token: Optional access token for authentication
    
    Returns:
        dict: Response indicating success or failure
    """
    try:
        # Get user details to find the user ID
        user_response = await retrieve_user_details(username)
        
        if user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, 
                              detail=f"Failed to retrieve user details: {user_response.text}")
        
        user_data = user_response.json()
        if not user_data:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        
        user_id = user_data[0].get("id")
        if not user_id:
            raise HTTPException(status_code=404, detail=f"User ID not found for username '{username}'")
        
        # Determine the enabled status based on action
        if action.lower() == "enable":
            enabled = True
        elif action.lower() == "disable":
            enabled = False
        else:
            raise HTTPException(status_code=400, detail="Action must be either 'enable' or 'disable'")
        
        # Prepare payload to update user status
        payload = {
            "enabled": enabled
        }
        
        # Update user status
        response = await update_user_details(payload, user_id, access_token)
        
        if response.status_code in [200, 201, 204]:
            status_text = "enabled" if enabled else "disabled"
            return {"detail": f"User '{username}' has been {status_text} successfully"}
        else:
            raise HTTPException(status_code=response.status_code, 
                              detail=f"Failed to update user status: {response.text}")
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


async def get_login_events(username: str = None, access_token=None):
    """
    Retrieve LOGIN events for a specific user by username or for all users.
    
    Args:
        username (str, optional): Username to filter events for. If None, returns events for all users.
        access_token (str, optional): Access token for authentication
        
    Returns:
        list: List of dictionaries containing username and timestamp pairs
    """
    try:
        if username:
            # Get login events for specific user
            # Get user details to extract user ID
            user_response = await retrieve_user_details(username, access_token)
            
            if user_response.status_code != 200:
                raise HTTPException(status_code=user_response.status_code, 
                                  detail=f"Failed to retrieve user details: {user_response.text}")
            
            user_data = user_response.json()
            if not user_data:
                raise HTTPException(status_code=404, detail=f"User '{username}' not found")
                
            user_id = user_data[0].get("id")
            if not user_id:
                raise HTTPException(status_code=500, detail="User ID not found in user data")
            
            # Get LOGIN events for the user
            events_response = await get_events(user_id=user_id, event_type="LOGIN", access_token=access_token)
        else:
            # Get login events for all users
            events_response = await get_events(event_type="LOGIN", access_token=access_token)
        
        if events_response.status_code != 200:
            raise HTTPException(status_code=events_response.status_code, 
                              detail=f"Failed to retrieve events: {events_response.text}")
        
        events_data = events_response.json()
        
        if username:
            # For specific user - filter events from past 24 hours
            from datetime import datetime, timedelta
            
            # Calculate 24 hours ago timestamp in milliseconds
            now = datetime.now()
            twenty_four_hours_ago = now - timedelta(hours=24)
            cutoff_timestamp = int(twenty_four_hours_ago.timestamp() * 1000)
            
            # Filter events from past 24 hours
            recent_timestamps = [event.get("time") for event in events_data 
                               if event.get("time") and event.get("time") >= cutoff_timestamp]
            recent_timestamps.sort()  # Sort in chronological order (oldest to newest)
            
            # Convert timestamps to ISO format
            formatted_timestamps = []
            for timestamp in recent_timestamps:
                dt = datetime.fromtimestamp(timestamp / 1000)
                iso_format = dt.strftime('%Y-%m-%dT%H:%M:%S')
                formatted_timestamps.append(iso_format)
            
            # Format response as list of dictionaries with username and timestamp pairs
            response_list = []
            for timestamp in formatted_timestamps:
                response_list.append({username: timestamp})
            
            return response_list
        else:
            # For all users - collect all events from past 24 hours
            from datetime import datetime, timedelta
            
            # Calculate 24 hours ago timestamp in milliseconds
            now = datetime.now()
            twenty_four_hours_ago = now - timedelta(hours=24)
            cutoff_timestamp = int(twenty_four_hours_ago.timestamp() * 1000)
            
            # Get all users to map user IDs to usernames
            all_users_response = await get_all_users(access_token)
            if all_users_response.status_code != 200:
                raise HTTPException(status_code=all_users_response.status_code, 
                                  detail=f"Failed to retrieve users: {all_users_response.text}")
            
            all_users = all_users_response.json()
            user_id_to_username = {user.get("id"): user.get("username") for user in all_users if user.get("id") and user.get("username")}
            
            # Collect all events from past 24 hours with usernames and timestamps
            all_events = []
            for event in events_data:
                if (event.get("time") and event.get("userId") and 
                    event.get("time") >= cutoff_timestamp):
                    user_id = event.get("userId")
                    username = user_id_to_username.get(user_id)
                    if username:  # Only include if username is found
                        all_events.append({
                            "username": username,
                            "timestamp": event.get("time")
                        })
            
            # Sort all events chronologically (oldest to newest)
            all_events.sort(key=lambda x: x["timestamp"])
            
            # Convert to required format and convert timestamps to ISO format
            response_list = []
            for event in all_events:
                dt = datetime.fromtimestamp(event["timestamp"] / 1000)
                iso_format = dt.strftime('%Y-%m-%dT%H:%M:%S')
                response_list.append({event["username"]: iso_format})
            
            return response_list
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


async def get_user_permissions(username: str, access_token=None):
    """
    Get all permissions (resources) granted to a specific user.
    
    Args:
        username (str): The username to get permissions for
        access_token (str, optional): Access token for authentication
        
    Returns:
        dict: Dictionary containing resource details and summary information
    """
    try:
        # Get the raw resources data
        resources = await get_user_permissions_by_username(username, access_token)
        
        if not resources:
            return {
                "username": username,
                "total_permissions": 0,
                "resources": []
            }
        
        # Get detailed resource information including types
        all_resources_detailed = await get_all_resources_detailed(access_token)
        
        # Format the response with resource names, IDs, and types
        formatted_resources = []
        for resource in resources:
            resource_id = resource.get("_id")
            resource_details = all_resources_detailed.get(resource_id, {})
            
            formatted_resources.append({
                "resource_name": resource.get("name"),
                "resource_id": resource_id,
                "resource_type": resource_details.get("type", "unknown")
            })
        
        return {
            "username": username,
            "total_permissions": len(formatted_resources),
            "resources": formatted_resources
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))


async def create_resource_api(payload: dict, access_token=None):
    """
    Create a new resource in Keycloak
    
    Args:
        payload: Dictionary containing resource details
        access_token: Optional access token for authentication
    
    Expected payload structure:
    {
        "name": "resource_name",  # Required - unique resource name
        "type": "resource_type"   # Required - e.g., "file", "dir", "api", etc.
    }
    
    Returns:
        HTTPResponse from Keycloak
    """
    try:
        # Validate required fields
        required_fields = ["name", "type"]
        for field in required_fields:
            if field not in payload:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Set resource payload with required fields and default values
        resource_payload = {
            "name": payload["name"],
            "displayName": payload["name"],  # Set displayName same as name
            "type": payload["type"],
            "icon_uri": "",
            "ownerManagedAccess": False,
            "attributes": {},
            "scopes": []
        }
        
        # Check if resource already exists
        existing_resource = await retrieve_resource(payload["name"])
        if existing_resource:
            raise HTTPException(status_code=409, detail=f"Resource with name '{payload['name']}' already exists")
        
        # Create the resource
        response = await create_resource(resource_payload, access_token)
        
        return response
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=500, detail=str(e))