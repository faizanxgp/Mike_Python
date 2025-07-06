# Test deployment script for Windows
Write-Host "🧪 Testing Benyon Sports API Deployment..." -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Check if docker-compose.yml exists
if (!(Test-Path "docker-compose.yml")) {
    Write-Host "❌ docker-compose.yml not found. Make sure you're in the project directory." -ForegroundColor Red
    exit 1
}

Write-Host "✅ docker-compose.yml found" -ForegroundColor Green

# Build and start services
Write-Host "🚀 Building and starting services..." -ForegroundColor Cyan
docker-compose up -d --build

# Wait for services to start
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Test API endpoints
Write-Host "🧪 Testing API endpoints..." -ForegroundColor Cyan

# Test root endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:80/" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ API root endpoint is responding" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ API root endpoint is not responding" -ForegroundColor Red
}

# Test health endpoint
try {
    $response = Invoke-WebRequest -Uri "http://localhost:80/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Health endpoint is responding" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Health endpoint is not responding" -ForegroundColor Red
}

# Test Keycloak
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/realms/team_online/.well-known/openid_configuration" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Keycloak is responding" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Keycloak is not responding" -ForegroundColor Red
}

# Show running containers
Write-Host "📋 Running containers:" -ForegroundColor Cyan
docker-compose ps

Write-Host "🎉 Deployment test completed!" -ForegroundColor Green
Write-Host ""
Write-Host "Access your services:" -ForegroundColor Yellow
Write-Host "- API: http://localhost:80"
Write-Host "- Keycloak: http://localhost:8080"
Write-Host ""
Write-Host "View logs with: docker-compose logs -f" -ForegroundColor Yellow
