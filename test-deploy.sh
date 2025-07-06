#!/bin/bash
# Test deployment script

echo "🧪 Testing Benyon Sports API Deployment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found. Make sure you're in the project directory."
    exit 1
fi

echo "✅ docker-compose.yml found"

# Build and start services
echo "🚀 Building and starting services..."
docker-compose up -d --build

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 30

# Test API endpoints
echo "🧪 Testing API endpoints..."

# Test root endpoint
if curl -f http://localhost:80/ > /dev/null 2>&1; then
    echo "✅ API root endpoint is responding"
else
    echo "❌ API root endpoint is not responding"
fi

# Test health endpoint
if curl -f http://localhost:80/health > /dev/null 2>&1; then
    echo "✅ Health endpoint is responding"
else
    echo "❌ Health endpoint is not responding"
fi

# Test Keycloak
if curl -f http://localhost:8080/realms/team_online/.well-known/openid_configuration > /dev/null 2>&1; then
    echo "✅ Keycloak is responding"
else
    echo "❌ Keycloak is not responding"
fi

# Show running containers
echo "📋 Running containers:"
docker-compose ps

echo "🎉 Deployment test completed!"
echo ""
echo "Access your services:"
echo "- API: http://localhost:80"
echo "- Keycloak: http://localhost:8080"
echo ""
echo "View logs with: docker-compose logs -f"
