# Benyon Sports API - Deployment Guide

## 🚀 Quick Deploy on Ubuntu Server

### Prerequisites
- Ubuntu Server with Docker and Docker Compose installed
- Domain names configured (optional, can use IP addresses)

### 1. Clone/Upload Project
```bash
# Upload your project files to the server
# Or clone from your repository:
git clone <your-repo-url>
cd Python
```

### 2. Configure Environment
```bash
# Edit .env file with your actual values
nano .env

# Update domain names in nginx.conf
nano nginx/nginx.conf
# Replace yourdomain.com with your actual domain
```

### 3. Deploy Services
```bash
# Build and start all services
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Access Your Services
- **API Backend**: `http://api.yourdomain.com` (or `http://your-server-ip:80`)
- **Keycloak Admin**: `http://auth.yourdomain.com` (or `http://your-server-ip:8080`)
- **Frontend**: `http://app.yourdomain.com` (placeholder ready for React app)

### 5. Default Credentials
- **Keycloak Admin**: admin / admin123
- **PostgreSQL**: keycloak / keycloak123

## 📁 Project Structure
```
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container build instructions
├── docker-compose.yml     # Multi-service orchestration
├── .env                   # Environment variables
├── .dockerignore          # Docker build exclusions
├── nginx/
│   └── nginx.conf         # Reverse proxy configuration
├── app/
│   ├── core/
│   │   ├── config.py      # Application configuration
│   │   └── auth.py        # Authentication module
│   ├── services/
│   │   ├── file_service.py      # File operations
│   │   └── keycloak_service.py  # Authentication service
│   └── routers/
│       ├── files.py       # File management endpoints
│       └── keycloak.py    # Auth endpoints
└── data/                  # File storage (mounted as volumes)
    ├── remote/            # Uploaded files
    ├── backup/            # Deleted files backup
    └── preview/           # Generated previews
```

## 🔧 Management Commands

### View Logs
```bash
docker-compose logs -f benyon-backend
docker-compose logs -f keycloak
docker-compose logs -f nginx
```

### Restart Services
```bash
docker-compose restart benyon-backend
docker-compose restart
```

### Update Application
```bash
git pull origin main
docker-compose up -d --build benyon-backend
```

### Backup Data
```bash
# Backup file data
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Backup database
docker-compose exec postgres pg_dump -U keycloak keycloak > keycloak-backup.sql
```

## 🎯 API Endpoints

### Authentication
- `GET /api/auth/user-info` - Get current user info
- `GET /api/auth/permissions` - Get user permissions
- `POST /api/auth/refresh-token` - Refresh access token

### File Management  
- `POST /api/files/upload` - Upload files
- `GET /api/files/list` - List all files
- `GET /api/files/search?query=...` - Search files
- `GET /api/files/download/{filename}` - Download file
- `GET /api/files/preview/{filename}?page=1` - Preview file
- `DELETE /api/files/{filename}` - Delete file
- `GET /api/files/info/{filename}` - Get file info

### Health Checks
- `GET /` - API status
- `GET /health` - Health check
- `GET /api/auth/health` - Auth service health

## 🔒 Security Features
- JWT token authentication via Keycloak
- Role-based access control
- CORS protection
- File type validation
- Size limits (100MB max)
- Non-root container execution

## 📈 Performance Optimizations
- Layered Docker builds with caching
- Minimal dependencies
- Async/await for all operations
- Efficient file handling
- Service separation for scalability

Ready for production deployment! 🎉
