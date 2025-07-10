import os
from decouple import config

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Keycloak Configuration
KEYCLOAK_URL = config("KEYCLOAK_URL", default="http://keycloak:8080")
KEYCLOAK_REALM_NAME = config("KEYCLOAK_REALM_NAME", default="team_online")
KEYCLOAK_BACKEND_CLIENT_ID = config("KEYCLOAK_BACKEND_CLIENT_ID", default="benyon_be")
KEYCLOAK_BACKEND_CLIENT_SECRET = config("KEYCLOAK_BACKEND_CLIENT_SECRET", default="")

# Application Configuration
PORT = config("PORT", default=8000, cast=int)
ENVIRONMENT = config("ENVIRONMENT", default="development")
DEBUG = config("DEBUG", default=True, cast=bool)

# File Storage Paths
DATA_DIR = os.path.join(BASE_DIR, "data")
REMOTE_DIR = os.path.join(DATA_DIR, "remote")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")
PREVIEW_DIR = os.path.join(DATA_DIR, "preview")

# CORS Configuration
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://96.30.199.117:3000",
    "http://96.30.199.117:8080",
    "https://app.yourdomain.com",
    "https://auth.yourdomain.com",
]

# Ensure directories exist
os.makedirs(REMOTE_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)
