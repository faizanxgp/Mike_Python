from decouple import Config, RepositoryEnv

secrets = Config(RepositoryEnv("secrets.env"))

KEYCLOAK_URL = secrets("KEYCLOAK_URL")
KEYCLOAK_REALM_NAME = secrets("KEYCLOAK_REALM_NAME")
KEYCLOAK_BACKEND_CLIENT_ID = secrets("KEYCLOAK_BACKEND_CLIENT_ID")
KEYCLOAK_BACKEND_CLIENT_SECRET = secrets("KEYCLOAK_BACKEND_CLIENT_SECRET")

base_url = secrets("base_url")
realm_name = secrets("realm_name")
backend_client_name = secrets("backend_client_name")
backend_client_id = secrets("backend_client_id")
frontend_client_id = secrets("frontend_client_id")
backend_client_secret = secrets("backend_client_secret")

ep_access_token = f"/realms/{realm_name}/protocol/openid-connect/token"
ep_create_user = f"/admin/realms/{realm_name}/users"
ep_retrieve_user = f"/admin/realms/{realm_name}/users"
ep_reset_password = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]/reset-password"
ep_forgot_password = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]/execute-actions-email"
ep_update_user_details = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]"
ep_logout_user  = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]/logout"
ep_get_all_users = f"/admin/realms/{realm_name}/users"
ep_check_user_active = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]/sessions"
ep_get_client_role = f"/admin/realms/{realm_name}/clients/{frontend_client_id}/roles/[ENTER_ROLE]" # to extract role id based on role name
ep_assign_client_role = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]/role-mappings/clients/{frontend_client_id}"
ep_get_user_roles = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]/role-mappings/clients/{frontend_client_id}" # get all client-level roles assigned to user
ep_delete_user = f"/admin/realms/{realm_name}/users/[ENTER_USER_ID]"
ep_create_user_policy = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/policy/user"
ep_retrieve_policy = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/policy/"
ep_delete_user_policy = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/policy/"
ep_create_resource_url = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/resource"
ep_retrieve_resource = f"/realms/{realm_name}/authz/protection/resource_set"
ep_get_all_resources = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/resource"
ep_delete_resource = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/resource/"
ep_create_permission = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/permission/resource"
ep_get_all_permissions = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/permission/"
ep_resources_in_permission = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/policy/[ENTER_PERMISSION_ID]/resources"
ep_update_permission = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/permission/resource/[ENTER_PERMISSION_ID]"
ep_delete_permission = f"/admin/realms/{realm_name}/clients/{backend_client_id}/authz/resource-server/permission/[ENTER_PERMISSION_ID]"
ep_events = f"/admin/realms/{realm_name}/events"
