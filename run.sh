#!/bin/bash
#
# Caos Vision - Interactive Setup and Deployment Script
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration file
ENV_FILE=".env"
ENV_EXAMPLE="env.example"

# Functions
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║                      CAOS VISION                          ║"
    echo "║              Multi-Stream Video Wall                      ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✔${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✖${NC} $1"
}

prompt() {
    local prompt_text="$1"
    local default_value="$2"
    local var_name="$3"
    local is_password="$4"

    if [ -n "$default_value" ]; then
        if [ "$is_password" = "true" ]; then
            echo -ne "${CYAN}$prompt_text${NC} [****]: "
        else
            echo -ne "${CYAN}$prompt_text${NC} [$default_value]: "
        fi
    else
        echo -ne "${CYAN}$prompt_text${NC}: "
    fi

    if [ "$is_password" = "true" ]; then
        read -s input
        echo ""
    else
        read input
    fi

    if [ -z "$input" ]; then
        eval "$var_name='$default_value'"
    else
        eval "$var_name='$input'"
    fi
}

prompt_yes_no() {
    local prompt_text="$1"
    local default="$2"
    local var_name="$3"

    if [ "$default" = "y" ]; then
        echo -ne "${CYAN}$prompt_text${NC} [Y/n]: "
    else
        echo -ne "${CYAN}$prompt_text${NC} [y/N]: "
    fi

    read input
    input=$(echo "$input" | tr '[:upper:]' '[:lower:]')

    if [ -z "$input" ]; then
        input="$default"
    fi

    if [ "$input" = "y" ] || [ "$input" = "yes" ]; then
        eval "$var_name=true"
    else
        eval "$var_name=false"
    fi
}

generate_secret() {
    openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64
}

check_dependencies() {
    print_step "Checking dependencies..."

    local missing=()

    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi

    if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
        missing+=("docker-compose")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        print_error "Missing dependencies: ${missing[*]}"
        echo ""
        echo "Please install the missing dependencies and try again."
        exit 1
    fi

    print_success "All dependencies found"
}

load_existing_config() {
    if [ -f "$ENV_FILE" ]; then
        print_warning "Existing configuration found"
        prompt_yes_no "Do you want to use the existing configuration?" "y" USE_EXISTING

        if [ "$USE_EXISTING" = "true" ]; then
            source "$ENV_FILE"
            return 0
        fi
    fi
    return 1
}

configure() {
    print_step "Configuration"
    echo ""

    # Admin credentials
    echo -e "${YELLOW}── Admin Credentials ──${NC}"
    prompt "Admin username" "admin" ADMIN_USER
    prompt "Admin password" "" ADMIN_PASS "true"

    while [ -z "$ADMIN_PASS" ]; do
        print_error "Password cannot be empty"
        prompt "Admin password" "" ADMIN_PASS "true"
    done

    echo ""

    # Security
    echo -e "${YELLOW}── Security ──${NC}"
    prompt_yes_no "Generate a random secret key?" "y" GEN_SECRET

    if [ "$GEN_SECRET" = "true" ]; then
        SECRET_KEY=$(generate_secret)
        print_success "Secret key generated"
    else
        prompt "Secret key (min 32 characters)" "" SECRET_KEY
        while [ ${#SECRET_KEY} -lt 32 ]; do
            print_error "Secret key must be at least 32 characters"
            prompt "Secret key" "" SECRET_KEY
        done
    fi

    echo ""

    # Network
    echo -e "${YELLOW}── Network ──${NC}"
    prompt "Port to expose the service" "64500" PORT

    echo ""

    # Proxy/Tunnel
    echo -e "${YELLOW}── Proxy Configuration ──${NC}"
    prompt_yes_no "Is this behind a reverse proxy (nginx, traefik, etc.)?" "n" BEHIND_PROXY
    prompt_yes_no "Are you using Cloudflare Tunnel?" "n" CLOUDFLARE_TUNNEL

    if [ "$BEHIND_PROXY" = "true" ] || [ "$CLOUDFLARE_TUNNEL" = "true" ]; then
        prompt "Allowed origins (comma-separated, or * for all)" "*" ALLOWED_ORIGINS
    else
        ALLOWED_ORIGINS="*"
    fi

    echo ""

    # Advanced
    echo -e "${YELLOW}── Advanced ──${NC}"
    prompt_yes_no "Enable debug mode?" "n" DEBUG
    prompt "Session expiration (seconds)" "3600" SESSION_EXPIRE_SECONDS
    prompt "Rate limit attempts" "5" RATE_LIMIT_ATTEMPTS
    prompt "Rate limit window (seconds)" "300" RATE_LIMIT_WINDOW

    echo ""
}

write_env_file() {
    print_step "Writing configuration to $ENV_FILE..."

    cat > "$ENV_FILE" << EOF
# Caos Vision Configuration
# Generated by run.sh on $(date)

# Application
DEBUG=$DEBUG
SECRET_KEY=$SECRET_KEY

# Redis (internal, don't change unless you know what you're doing)
REDIS_URL=redis://valkey:6379/0

# Authentication
ADMIN_USER=$ADMIN_USER
ADMIN_PASS=$ADMIN_PASS

# Session
SESSION_EXPIRE_SECONDS=$SESSION_EXPIRE_SECONDS

# Security
ALLOWED_ORIGINS=$ALLOWED_ORIGINS
RATE_LIMIT_ATTEMPTS=$RATE_LIMIT_ATTEMPTS
RATE_LIMIT_WINDOW=$RATE_LIMIT_WINDOW

# Proxy
CLOUDFLARE_TUNNEL=$CLOUDFLARE_TUNNEL
BEHIND_PROXY=$BEHIND_PROXY
EOF

    chmod 600 "$ENV_FILE"
    print_success "Configuration saved"
}

update_port() {
    if [ "$PORT" != "64500" ]; then
        print_step "Updating port configuration..."

        # Create override file for custom port
        cat > "docker-compose.override.yaml" << EOF
---
services:
  caos-vision:
    ports:
      - "${PORT}:8000"
EOF
        print_success "Port configured to $PORT"
    fi
}

build_and_run() {
    print_step "Building and starting services..."
    echo ""

    # Determine docker compose command
    if command -v docker compose &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Build
    echo -e "${YELLOW}Building containers...${NC}"
    $COMPOSE_CMD build --no-cache

    echo ""

    # Start
    echo -e "${YELLOW}Starting services...${NC}"
    $COMPOSE_CMD up -d

    echo ""
    print_success "Services started successfully!"
}

show_status() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  DEPLOYMENT COMPLETE                      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Viewer URL:${NC}  http://localhost:${PORT}/"
    echo -e "  ${CYAN}Admin URL:${NC}   http://localhost:${PORT}/admin"
    echo -e "  ${CYAN}Login URL:${NC}   http://localhost:${PORT}/login"
    echo ""
    echo -e "  ${CYAN}Username:${NC}    $ADMIN_USER"
    echo -e "  ${CYAN}Password:${NC}    (as configured)"
    echo ""
    echo -e "  ${YELLOW}Commands:${NC}"
    echo -e "    View logs:     docker compose logs -f"
    echo -e "    Stop:          docker compose down"
    echo -e "    Restart:       docker compose restart"
    echo -e "    Reconfigure:   ./run.sh"
    echo ""
}

dev_mode() {
    print_step "Starting development mode with live reload..."
    echo ""

    # Determine docker compose command
    if command -v docker compose &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Build and start with dev configuration
    echo -e "${YELLOW}Building containers...${NC}"
    $COMPOSE_CMD -f docker-compose.dev.yaml build

    echo ""
    echo -e "${YELLOW}Starting services with live reload...${NC}"
    $COMPOSE_CMD -f docker-compose.dev.yaml up

    echo ""
}

show_help() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --configure, -c    Run configuration wizard only"
    echo "  --start, -s        Start services (requires existing .env)"
    echo "  --dev, -d          Start in development mode with live reload"
    echo "  --stop             Stop services"
    echo "  --restart          Restart services"
    echo "  --logs, -l         Show logs"
    echo "  --status           Show service status"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Without options, runs the full setup wizard."
}

# Main script
main() {
    cd "$(dirname "$0")"

    case "${1:-}" in
        --configure|-c)
            print_banner
            configure
            write_env_file
            update_port
            print_success "Configuration complete. Run '$0 --start' to start services."
            ;;
        --start|-s)
            if [ ! -f "$ENV_FILE" ]; then
                print_error "No configuration found. Run '$0' first."
                exit 1
            fi
            source "$ENV_FILE"
            PORT=${PORT:-64500}
            build_and_run
            show_status
            ;;
        --dev|-d)
            print_banner
            dev_mode
            ;;
        --stop)
            print_step "Stopping services..."
            # Stop both production and dev services
            docker compose -f docker-compose.yaml down 2>/dev/null || docker-compose -f docker-compose.yaml down 2>/dev/null || true
            docker compose -f docker-compose.dev.yaml down 2>/dev/null || docker-compose -f docker-compose.dev.yaml down 2>/dev/null || true
            print_success "Services stopped"
            ;;
        --restart)
            print_step "Restarting services..."
            docker compose restart 2>/dev/null || docker-compose restart
            print_success "Services restarted"
            ;;
        --logs|-l)
            docker compose logs -f 2>/dev/null || docker-compose logs -f
            ;;
        --status)
            docker compose ps 2>/dev/null || docker-compose ps
            ;;
        --help|-h)
            show_help
            ;;
        "")
            print_banner
            check_dependencies
            echo ""

            # Try to load existing config
            if ! load_existing_config; then
                configure
                write_env_file
                update_port
            else
                source "$ENV_FILE"
                PORT=${PORT:-64500}
            fi

            echo ""
            prompt_yes_no "Start the services now?" "y" START_NOW

            if [ "$START_NOW" = "true" ]; then
                build_and_run
                show_status
            else
                echo ""
                print_success "Configuration saved. Run '$0 --start' when ready."
            fi
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
