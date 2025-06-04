#!/bin/bash

# Temporal UI Startup Script with Custom Search Attributes
# This script starts Temporal services and configures custom search attributes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEMPORAL_ADDRESS="localhost:7233"
TEMPORAL_UI_URL="http://localhost:8080"
CONFIG_DIR="$(dirname "$0")/../config"
PROJECT_ROOT="$(dirname "$0")/.."

echo -e "${BLUE}🚀 Starting Temporal with Custom Search Attributes...${NC}"

# Function to check if Temporal is running
check_temporal_health() {
    echo -e "${YELLOW}⏳ Checking Temporal server health...${NC}"
    for i in {1..30}; do
        if curl -s "http://localhost:8080/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Temporal server is healthy${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    echo -e "${RED}❌ Temporal server health check failed${NC}"
    return 1
}

# Function to register custom search attributes
register_search_attributes() {
    echo -e "${YELLOW}📝 Registering custom search attributes...${NC}"
    
    # Wait for Temporal to be ready
    sleep 5
    
    # Register CustomProgress attribute
    echo -e "${BLUE}Registering CustomProgress attribute...${NC}"
    docker exec temporal-admin-tools tctl --address temporal:7233 cluster add-search-attributes \
        --name CustomProgress --type Text || echo -e "${YELLOW}CustomProgress may already exist${NC}"
    
    # Register CustomTag attribute
    echo -e "${BLUE}Registering CustomTag attribute...${NC}"
    docker exec temporal-admin-tools tctl --address temporal:7233 cluster add-search-attributes \
        --name CustomTag --type Text || echo -e "${YELLOW}CustomTag may already exist${NC}"
    
    echo -e "${GREEN}✅ Custom search attributes registration completed${NC}"
}

# Function to display search attributes
show_search_attributes() {
    echo -e "${YELLOW}📋 Current search attributes:${NC}"
    docker exec temporal-admin-tools tctl --address temporal:7233 cluster get-search-attributes
}

# Function to start Temporal services
start_temporal() {
    echo -e "${YELLOW}🐳 Starting Temporal services with Docker Compose...${NC}"
    cd "$PROJECT_ROOT"
    
    # Stop any existing services
    docker-compose down
    
    # Start services
    docker-compose up -d
    
    echo -e "${GREEN}✅ Temporal services started${NC}"
}

# Function to show service status
show_status() {
    echo -e "${YELLOW}📊 Service Status:${NC}"
    docker-compose ps
    echo ""
    echo -e "${BLUE}🌐 Temporal UI: ${TEMPORAL_UI_URL}${NC}"
    echo -e "${BLUE}🔧 Temporal Server: ${TEMPORAL_ADDRESS}${NC}"
}

# Function to open UI in browser (macOS)
open_ui() {
    if command -v open > /dev/null 2>&1; then
        echo -e "${YELLOW}🌐 Opening Temporal UI in browser...${NC}"
        sleep 3
        open "$TEMPORAL_UI_URL"
    fi
}

# Function to show usage examples
show_examples() {
    echo -e "${BLUE}📚 Usage Examples:${NC}"
    echo ""
    echo -e "${YELLOW}1. Search by Custom Progress:${NC}"
    echo "   CustomProgress:\"video_generation:processing:75\""
    echo ""
    echo -e "${YELLOW}2. Search by Custom Tag:${NC}"
    echo "   CustomTag:\"benchmark_test_high_priority\""
    echo ""
    echo -e "${YELLOW}3. Combined Search:${NC}"
    echo "   WorkflowStatus:RUNNING AND CustomTag:\"production\""
    echo ""
    echo -e "${YELLOW}4. Progress Range Search:${NC}"
    echo "   CustomProgress:\"*:processing:*\""
    echo ""
    echo -e "${BLUE}💡 Tip: Use the Temporal UI at ${TEMPORAL_UI_URL} to explore workflows${NC}"
}

# Main execution
main() {
    echo -e "${GREEN}🎯 Temporal Custom Search Attributes Setup${NC}"
    echo "================================================"
    
    # Start Temporal services
    start_temporal
    
    # Check health
    if check_temporal_health; then
        # Register custom search attributes
        register_search_attributes
        
        # Show current search attributes
        show_search_attributes
        
        # Show service status
        show_status
        
        # Show usage examples
        show_examples
        
        # Open UI in browser
        open_ui
        
        echo ""
        echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
        echo -e "${BLUE}Access Temporal UI at: ${TEMPORAL_UI_URL}${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop services${NC}"
        
        # Keep script running to show logs
        echo ""
        echo -e "${YELLOW}📋 Following Temporal logs (Ctrl+C to stop):${NC}"
        docker-compose logs -f temporal
    else
        echo -e "${RED}❌ Failed to start Temporal services${NC}"
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    "start")
        main
        ;;
    "stop")
        echo -e "${YELLOW}🛑 Stopping Temporal services...${NC}"
        cd "$PROJECT_ROOT"
        docker-compose down
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
    "status")
        show_status
        ;;
    "attributes")
        show_search_attributes
        ;;
    "examples")
        show_examples
        ;;
    "register")
        register_search_attributes
        ;;
    "help")
        echo "Usage: $0 [start|stop|status|attributes|examples|register|help]"
        echo ""
        echo "Commands:"
        echo "  start      - Start Temporal services and register search attributes"
        echo "  stop       - Stop Temporal services"
        echo "  status     - Show service status"
        echo "  attributes - Show current search attributes"
        echo "  examples   - Show search query examples"
        echo "  register   - Register custom search attributes only"
        echo "  help       - Show this help message"
        ;;
    *)
        main
        ;;
esac