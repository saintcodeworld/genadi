#!/bin/bash

# MemeMarket System Startup Script
# This script starts all services using Docker Compose

echo "🚀 Starting MemeMarket System..."
echo "================================"
echo ""
echo "Program ID: CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7"
echo "Network: Devnet"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Check if keypair exists
if [ ! -f ~/.config/solana/id.json ]; then
    echo "⚠️  Warning: Solana keypair not found at ~/.config/solana/id.json"
    echo "   The Crank service needs this to sign transactions."
    read -p "   Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Navigate to project directory
cd "$(dirname "$0")"

echo "📦 Building and starting services..."
echo ""

# Start services
docker-compose up -d

echo ""
echo "✅ Services started!"
echo ""
echo "📊 Service Status:"
docker-compose ps
echo ""
echo "🌐 Access Points:"
echo "   - Backend API: http://localhost:8001"
echo "   - Redis: localhost:6379"
echo ""
echo "📝 Useful Commands:"
echo "   - View logs: docker-compose logs -f"
echo "   - Stop system: docker-compose down"
echo "   - Restart service: docker-compose restart <service>"
echo ""
echo "📖 See DOCKER_SETUP.md for full documentation"
