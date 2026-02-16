#!/bin/bash
# Production deployment script for Bub with systemd-run
# Usage: ./deploy-production.sh <command> [component]
#
# Commands:
#   start <component>   - Start a component (bus|agent|tape)
#   stop <component>    - Stop a component
#   logs <component>    - View logs of a component
#   status <component>  - Check status of a component
#   list               - List all running bub components
#
# Examples:
#   ./deploy-production.sh start bus
#   ./deploy-production.sh start agent
#   ./deploy-production.sh start tape
#   ./deploy-production.sh logs agent
#   ./deploy-production.sh stop bus

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${PROJECT_ROOT}/run"

# Ensure run directory exists
mkdir -p "${RUN_DIR}"

# Component definitions
# Format: name|command|working_dir|description
COMPONENTS=(
    "bus|bub bus serve|${PROJECT_ROOT}|WebSocket message bus server (pure router)"
    "agent|bub agent|${PROJECT_ROOT}|Agent worker"
    "tape|bub tape serve|${PROJECT_ROOT}|Tape store service"
    "telegram-bridge|bub bus telegram|${PROJECT_ROOT}|Telegram bridge (connects to bus as client)"
)

# Helper: get unit name for a component
get_unit_name() {
    local component="$1"
    local unit_file="${RUN_DIR}/${component}.unit_name"
    if [ -f "${unit_file}" ]; then
        cat "${unit_file}"
    else
        echo ""
    fi
}

# Helper: save unit name for a component
save_unit_name() {
    local component="$1"
    local unit_name="$2"
    echo "${unit_name}" > "${RUN_DIR}/${component}.unit_name"
}

# Helper: remove unit name for a component
remove_unit_name() {
    local component="$1"
    local unit_file="${RUN_DIR}/${component}.unit_name"
    if [ -f "${unit_file}" ]; then
        rm "${unit_file}"
    fi
}

# Helper: check if component exists
component_exists() {
    local target="$1"
    for comp_def in "${COMPONENTS[@]}"; do
        IFS='|' read -r name cmd dir desc <<< "${comp_def}"
        if [ "${name}" = "${target}" ]; then
            return 0
        fi
    done
    return 1
}

# Helper: get component info
get_component_info() {
    local target="$1"
    for comp_def in "${COMPONENTS[@]}"; do
        IFS='|' read -r name cmd dir desc <<< "${comp_def}"
        if [ "${name}" = "${target}" ]; then
            echo "${comp_def}"
            return 0
        fi
    done
    return 1
}

# Start a component using systemd-run
start_component() {
    local component="$1"
    
    if ! component_exists "${component}"; then
        echo "❌ Unknown component: ${component}"
        echo "Available components: bus, agent, tape, telegram-bridge"
        exit 1
    fi
    
    local comp_def
    comp_def=$(get_component_info "${component}")
    IFS='|' read -r name cmd dir desc <<< "${comp_def}"
    
    # Check if already running
    local existing_unit
    existing_unit=$(get_unit_name "${component}")
    if [ -n "${existing_unit}" ]; then
        if systemctl --user is-active --quiet "${existing_unit}" 2>/dev/null; then
            echo "⚠️  ${component} is already running (unit: ${existing_unit})"
            echo "   Use: $0 logs ${component}  - to view logs"
            echo "   Use: $0 stop ${component}  - to stop"
            return 1
        fi
        # Clean up stale unit name file
        remove_unit_name "${component}"
    fi
    
    echo "🚀 Starting ${component}..."
    echo "   Description: ${desc}"
    echo "   Command: ${cmd}"
    echo "   Working directory: ${dir}"
    
    # Generate unique unit name
    local unit_name="bub-${component}-$(date +%s)"
    
    # Start with systemd-run
    # --user: run as user service
    # --unit: specific unit name
    # --collect: auto-cleanup when process exits
    # --property=WorkingDirectory: set working directory
    # --property=Environment: pass through relevant env vars
    # --property=Restart=always: auto-restart on failure
    # --property=RestartSec=5: wait 5 seconds before restarting
    # --no-block: don't wait for completion (hands-off)
    systemd-run \
        --user \
        --unit="${unit_name}" \
        --collect \
        --property=WorkingDirectory="${dir}" \
        --property=Environment="HOME=${HOME}" \
        --property=Environment="USER=${USER}" \
        --property=Environment="PATH=${PATH}" \
        --property=Environment="PYTHONUNBUFFERED=1" \
        --property=Environment="BUB_LOG_LEVEL=${BUB_LOG_LEVEL:-INFO}" \
        --property=Restart=always \
        --property=RestartSec=5 \
        --property=StartLimitIntervalSec=60 \
        --property=StartLimitBurst=3 \
        --no-block \
        -- uv run --env-file "${PROJECT_ROOT}/.env" ${cmd}
    
    # Save unit name
    save_unit_name "${component}" "${unit_name}"
    
    echo "✅ ${component} started"
    echo "   Unit: ${unit_name}"
    echo ""
    echo "   View logs: $0 logs ${component}"
    echo "   Check status: $0 status ${component}"
    echo "   Stop: $0 stop ${component}"
}

# Stop a component
stop_component() {
    local component="$1"
    shift
    local extra_args=("$@")
    
    if ! component_exists "${component}"; then
        echo "❌ Unknown component: ${component}"
        exit 1
    fi
    
    local unit_name
    unit_name=$(get_unit_name "${component}")
    
    if [ -z "${unit_name}" ]; then
        echo "⚠️  No unit name found for ${component}"
        echo "   It may not have been started with this script"
        return 1
    fi
    
    echo "🛑 Stopping ${component}..."
    echo "   Unit: ${unit_name}"
    
    if systemctl --user is-active --quiet "${unit_name}" 2>/dev/null; then
        systemctl --user stop "${unit_name}" "${extra_args[@]}"
        echo "✅ ${component} stopped"
    else
        echo "⚠️  ${component} was not running"
    fi
    
    remove_unit_name "${component}"
}

# View logs of a component
logs_component() {
    local component="$1"
    shift
    local extra_args=("$@")
    
    if ! component_exists "${component}"; then
        echo "❌ Unknown component: ${component}"
        exit 1
    fi
    
    local unit_name
    unit_name=$(get_unit_name "${component}")
    
    if [ -z "${unit_name}" ]; then
        echo "⚠️  No unit name found for ${component}"
        echo "   It may not have been started with this script"
        return 1
    fi
    
    echo "📋 Logs for ${component} (${unit_name}):"
    if [ ${#extra_args[@]} -eq 0 ]; then
        echo "   (Press Ctrl+C to exit logs)"
        echo ""
        journalctl --user -u "${unit_name}" -f
    else
        journalctl --user -u "${unit_name}" "${extra_args[@]}"
    fi
}

# Check status of a component
status_component() {
    local component="$1"
    shift
    local extra_args=("$@")
    
    if ! component_exists "${component}"; then
        echo "❌ Unknown component: ${component}"
        exit 1
    fi
    
    local unit_name
    unit_name=$(get_unit_name "${component}")
    
    if [ -z "${unit_name}" ]; then
        echo "⚠️  ${component}: not started (no unit name file)"
        return 1
    fi
    
    echo "📊 Status of ${component}:"
    echo "   Unit: ${unit_name}"
    echo ""
    
    systemctl --user status "${unit_name}" "${extra_args[@]}"
}

# List all running bub components
list_components() {
    echo "📋 Bub Components:"
    echo ""
    
    local found=0
    for comp_def in "${COMPONENTS[@]}"; do
        IFS='|' read -r name cmd dir desc <<< "${comp_def}"
        local unit_name
        unit_name=$(get_unit_name "${name}")
        
        if [ -n "${unit_name}" ]; then
            if systemctl --user is-active --quiet "${unit_name}" 2>/dev/null; then
                echo "✅ ${name}: running"
                echo "   Unit: ${unit_name}"
                echo "   ${desc}"
                found=1
            else
                echo "⚠️  ${name}: stopped (stale unit file)"
                remove_unit_name "${name}"
            fi
            echo ""
        fi
    done
    
    if [ ${found} -eq 0 ]; then
        echo "   No components are currently running"
        echo ""
        echo "   Start components with:"
        echo "     $0 start bus"
        echo "     $0 start agent"
        echo "     $0 start tape"
        echo "     $0 start telegram-bridge"
    fi
}

# Show help
show_help() {
    echo "Bub Production Deployment Script"
    echo ""
    echo "Usage: $0 <command> [component]"
    echo ""
    echo "Commands:"
    echo "  start <component>   Start a component (bus|agent|tape)"
    echo "  stop <component>    Stop a component"
    echo "  logs <component>    View logs of a component"
    echo "  status <component>  Check status of a component"
    echo "  list               List all running bub components"
    echo ""
    echo "Components:"
    echo "  bus              - WebSocket message bus server (pure router)"
    echo "  agent            - Agent worker"
    echo "  tape             - Tape store service"
    echo "  telegram-bridge  - Telegram bridge (connects to bus as client)"
    echo ""
    echo "Examples:"
    echo "  $0 start bus              # Start the bus server"
    echo "  $0 start agent            # Start the agent"
    echo "  $0 start tape             # Start the tape service"
    echo "  $0 start telegram-bridge  # Start the Telegram bridge"
    echo "  $0 logs agent             # View agent logs"
    echo "  $0 stop bus               # Stop the bus server"
    echo "  $0 status tape            # Check tape service status"
    echo "  $0 list                   # List all running components"
}

# Main command dispatcher
main() {
    local command="${1:-}"
    local component="${2:-}"
    
    case "${command}" in
        start)
            if [ -z "${component}" ]; then
                echo "❌ Missing component name"
                echo "Usage: $0 start <component>"
                echo "Components: bus, agent, tape, telegram-bridge"
                exit 1
            fi
            start_component "${component}"
            ;;
        stop)
            if [ -z "${component}" ]; then
                echo "❌ Missing component name"
                echo "Usage: $0 stop <component>"
                exit 1
            fi
            shift 2
            stop_component "${component}" "$@"
            ;;
        logs)
            if [ -z "${component}" ]; then
                echo "❌ Missing component name"
                echo "Usage: $0 logs <component>"
                exit 1
            fi
            shift 2
            logs_component "${component}" "$@"
            ;;
        status)
            if [ -z "${component}" ]; then
                echo "❌ Missing component name"
                echo "Usage: $0 status <component>"
                exit 1
            fi
            shift 2
            status_component "${component}" "$@"
            ;;
        list)
            list_components
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "❌ Unknown command: ${command}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
