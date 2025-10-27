#!/usr/bin/env bash
#
# CT Application Runner
#
# Description:
#   Runs the CT (Cover Traffic) application with configurable environment settings.
#   Supports local development and remote deployment environments (staging, prod).
#
# Usage:
#   ./run.sh [OPTIONS]
#
# Options:
#   -e, --env=ENV              Environment to run (local, staging, prod) [default: local]
#   -d, --deployment=DEPLOY    Deployment color (blue, green, auto) [default: auto]
#   -l, --log-folder=PATH      Directory for log files [default: .logs]
#   -n, --no-log-file          Run without logging to file (stdout only)
#   -h, --help                 Show this help message
#
# Environment Variables (required in .env file for non-local environments):
#   HOST_FORMAT      - URL format string for remote hosts
#   PROD_TOKEN       - API token for production environment
#   STAGING_TOKEN    - API token for staging environment
#
# Examples:
#   ./run.sh                                    # Run locally with default settings
#   ./run.sh --env=staging                      # Run against staging environment
#   ./run.sh --env=prod --deployment=blue       # Run against production blue deployment
#   ./run.sh -n                                 # Run locally without log file
#

set -euo pipefail

# Load environment variables from .env file if it exists
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1090,SC1091
    source <(grep -v '^#' .env)
    set +a
fi

# Default values
env="local"
deployment="auto"
log_folder=".logs"
no_log_file=""

# Function for checking health
healthyz() { curl -s -o /dev/null -w "%{http_code}" "$1/healthyz"; }

# Function for checking deployment
check_deployment() {
    local host_format="$1"
    local env_name="$2"
    local blue_url green_url blue_status green_status

    blue_url=$(printf '%s' "$host_format" | sed "s/%s/blue/; s/%s/1/; s/%s/$env_name/")
    green_url=$(printf '%s' "$host_format" | sed "s/%s/green/; s/%s/1/; s/%s/$env_name/")

    blue_status=$(healthyz "$blue_url")
    if [[ "$blue_status" -eq 200 ]]; then
        echo "blue"
        exit 1
    fi

    green_status=$(healthyz "$green_url")
    if [[ "$green_status" -eq 200 ]]; then
        echo "green"
        exit 1
    fi
}


get_local_node_address() {
    port=$((3000 + $1 * 3))
    echo "http://localhost:$port"
}

# Function to display help
show_help() {
    cat << EOF
CT Application Runner

Usage: $0 [OPTIONS]

Options:
  -e, --env=ENV              Environment to run (local, staging, prod) [default: local]
  -d, --deployment=DEPLOY    Deployment color (blue, green, auto) [default: auto]
  -l, --log-folder=PATH      Directory for log files [default: .logs]
  -n, --no-log-file          Run without logging to file (stdout only)
  -h, --help                 Show this help message

Environment Variables (required in .env file for non-local environments):
  HOST_FORMAT      - URL format string for remote hosts
  PROD_TOKEN       - API token for production environment
  STAGING_TOKEN    - API token for staging environment

Examples:
  $0                                    # Run locally with default settings
  $0 --env=staging                      # Run against staging environment
  $0 --env=prod --deployment=blue       # Run against production blue deployment
  $0 -n                                 # Run locally without log file

EOF
    exit 0
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            env="$2"
            shift 2
            ;;
        --env=*)
            env="${1#*=}"
            shift
            ;;
        -d|--deployment)
            deployment="$2"
            shift 2
            ;;
        --deployment=*)
            deployment="${1#*=}"
            shift
            ;;
        -l|--log-folder)
            log_folder="$2"
            shift 2
            ;;
        --log-folder=*)
            log_folder="${1#*=}"
            shift
            ;;
        -n|--no-log-file)
            no_log_file="1"
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            echo "Run '$0 --help' for usage information." >&2
            exit 1
            ;;
    esac
done

# Validate environment value
if [[ ! "$env" =~ ^(local|staging|prod)$ ]]; then
    echo "Error: Invalid environment '$env'. Must be one of: local, staging, prod" >&2
    exit 1
fi

# Validate deployment value
if [[ ! "$deployment" =~ ^(auto|blue|green)$ ]]; then
    echo "Error: Invalid deployment '$deployment'. Must be one of: auto, blue, green" >&2
    exit 1
fi

if [[ "$env" == "local" ]]; then
    HOPRD_API_HOST=$(get_local_node_address 1)
    export HOPRD_API_HOST
    export HOPRD_API_TOKEN="e2e-API-token^^"

else
    # Validate required environment variables for remote environments
    if [[ -z "${HOST_FORMAT:-}" ]]; then
        echo "Error: HOST_FORMAT environment variable is required for non-local environments" >&2
        echo "Please check your .env file." >&2
        exit 1
    fi

    # Check deployment if it's set to auto
    if [[ "$deployment" == "auto" ]]; then
        deployment=$(check_deployment "$HOST_FORMAT" "$env")
    fi

    # Node parameters
    HOPRD_API_HOST=$(printf '%s\n' "$HOST_FORMAT" | sed "s/%s/$deployment/; s/%s/1/; s/%s/$env/")
    export HOPRD_API_HOST

    if [[ "$env" == "prod" ]]; then
        if [[ -z "${PROD_TOKEN:-}" ]]; then
            echo "Error: PROD_TOKEN environment variable is required for production environment" >&2
            echo "Please check your .env file." >&2
            exit 1
        fi
        export HOPRD_API_TOKEN="$PROD_TOKEN"
    elif [[ "$env" == "staging" ]]; then
        if [[ -z "${STAGING_TOKEN:-}" ]]; then
            echo "Error: STAGING_TOKEN environment variable is required for staging environment" >&2
            echo "Please check your .env file." >&2
            exit 1
        fi
        export HOPRD_API_TOKEN="$STAGING_TOKEN"
    fi
fi

# Run the application
if [[ -n "$no_log_file" ]]; then
    echo "Starting CT in $env mode (no log file)"
    uv run -m core --configfile "./.configs/core_${env}_config.yaml"
else
    # Create log folder
    mkdir -p "$log_folder"
    time=$(date '+%Y%m%d_%H%M%S')
    echo "Starting CT in $env mode, storing logs in $log_folder"
    uv run -m core --configfile "./.configs/core_${env}_config.yaml" 2>&1 | tee "$log_folder/core_$time.log"
fi
