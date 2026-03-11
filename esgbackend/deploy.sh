#!/bin/bash

# AI Network Processor Deployment Script
# Usage: ./deploy.sh [option]
# Options: docker, local, pip

set -e

echo "🚀 AI Network Processor Deployment Script"
echo "=========================================="

# Function to deploy with Docker
deploy_docker() {
    echo "📦 Building and deploying with Docker..."
    
    # Stop existing container if running
    docker-compose down 2>/dev/null || true
    
    # Build and start
    docker-compose up --build -d
    
    echo "✅ Docker deployment complete!"
    echo "🌐 API available at: http://localhost:8000"
    echo "📊 Health check: http://localhost:8000/health"
    echo "📝 Logs: docker-compose logs -f"
}

# Function to deploy locally
deploy_local() {
    echo "🏠 Setting up local deployment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    # Kill existing uvicorn processes
    pkill -f "uvicorn.*main:app" 2>/dev/null || true
    
    # Start the application
    echo "Starting application..."
    cd telemetry
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 > ../uvicorn.log 2>&1 &
    
    echo "✅ Local deployment complete!"
    echo "🌐 API available at: http://localhost:8000"
    echo "📝 Logs: tail -f uvicorn.log"
    echo "🔍 Process: ps aux | grep uvicorn"
}

# Function to install as pip package
deploy_pip() {
    echo "📦 Installing as pip package..."
    
    # Build and install
    pip install -e .
    
    echo "✅ Pip installation complete!"
    echo "🚀 Run with: ai-network-processor"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [docker|local|pip]"
    echo ""
    echo "Options:"
    echo "  docker  - Deploy using Docker containers"
    echo "  local   - Deploy locally with virtual environment"
    echo "  pip     - Install as pip package"
    echo ""
    echo "If no option is provided, Docker deployment will be used."
}

# Main deployment logic
case "${1:-docker}" in
    "docker")
        deploy_docker
        ;;
    "local")
        deploy_local
        ;;
    "pip")
        deploy_pip
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        echo "❌ Unknown option: $1"
        show_usage
        exit 1
        ;;
esac

echo ""
echo "🎉 Deployment completed successfully!"
