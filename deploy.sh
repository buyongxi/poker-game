#!/bin/bash

# Poker Game 一键部署脚本
# 前端: localhost:5173
# 后端: localhost:8000

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 日志文件
LOG_DIR="$PROJECT_ROOT/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# PID 文件
PID_DIR="$PROJECT_ROOT/.pids"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    Poker Game 部署脚本${NC}"
echo -e "${BLUE}========================================${NC}"

# 创建必要的目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}错误: 未找到命令 '$1'，请先安装${NC}"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查依赖...${NC}"
    check_command "python3"
    check_command "pip3"
    check_command "node"
    check_command "npm"
    echo -e "${GREEN}依赖检查通过${NC}"
}

# 安装后端依赖
install_backend() {
    echo -e "${YELLOW}安装后端依赖...${NC}"
    cd "$BACKEND_DIR"

    # 创建虚拟环境（如果不存在）
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}创建 Python 虚拟环境...${NC}"
        python3 -m venv venv
    fi

    # 激活虚拟环境并安装依赖
    source venv/bin/activate
    pip3 install -r requirements.txt
    deactivate

    echo -e "${GREEN}后端依赖安装完成${NC}"
}

# 安装前端依赖
install_frontend() {
    echo -e "${YELLOW}安装前端依赖...${NC}"
    cd "$FRONTEND_DIR"

    if [ ! -d "node_modules" ]; then
        npm install
    else
        echo -e "${GREEN}前端依赖已存在，跳过安装${NC}"
    fi

    echo -e "${GREEN}前端依赖安装完成${NC}"
}

# 启动后端服务
start_backend() {
    echo -e "${YELLOW}启动后端服务...${NC}"
    cd "$BACKEND_DIR"

    # 检查是否已运行
    if [ -f "$BACKEND_PID" ]; then
        pid=$(cat "$BACKEND_PID")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}后端服务已在运行 (PID: $pid)${NC}"
            return
        fi
    fi

    # 激活虚拟环境并启动
    source venv/bin/activate
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
    deactivate

    # 等待服务启动
    sleep 2

    # 检查是否启动成功
    pid=$(cat "$BACKEND_PID")
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}后端服务已启动 (PID: $pid)${NC}"
        echo -e "${GREEN}后端地址: http://localhost:8000${NC}"
    else
        echo -e "${RED}后端服务启动失败，请查看日志: $BACKEND_LOG${NC}"
        exit 1
    fi
}

# 启动前端服务
start_frontend() {
    echo -e "${YELLOW}启动前端服务...${NC}"
    cd "$FRONTEND_DIR"

    # 检查是否已运行
    if [ -f "$FRONTEND_PID" ]; then
        pid=$(cat "$FRONTEND_PID")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}前端服务已在运行 (PID: $pid)${NC}"
            return
        fi
    fi

    # 启动开发服务器
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID"

    # 等待服务启动
    sleep 3

    # 检查是否启动成功
    pid=$(cat "$FRONTEND_PID")
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}前端服务已启动 (PID: $pid)${NC}"
        echo -e "${GREEN}前端地址: http://localhost:5173${NC}"
    else
        echo -e "${RED}前端服务启动失败，请查看日志: $FRONTEND_LOG${NC}"
        exit 1
    fi
}

# 停止服务
stop_services() {
    echo -e "${YELLOW}停止服务...${NC}"

    # 停止后端
    if [ -f "$BACKEND_PID" ]; then
        pid=$(cat "$BACKEND_PID")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            echo -e "${GREEN}后端服务已停止${NC}"
        fi
        rm -f "$BACKEND_PID"
    fi

    # 停止前端
    if [ -f "$FRONTEND_PID" ]; then
        pid=$(cat "$FRONTEND_PID")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            echo -e "${GREEN}前端服务已停止${NC}"
        fi
        rm -f "$FRONTEND_PID"
    fi
}

# 查看状态
show_status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}    服务状态${NC}"
    echo -e "${BLUE}========================================${NC}"

    # 后端状态
    if [ -f "$BACKEND_PID" ]; then
        pid=$(cat "$BACKEND_PID")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}后端服务: 运行中 (PID: $pid)${NC}"
        else
            echo -e "${RED}后端服务: 已停止${NC}"
        fi
    else
        echo -e "${RED}后端服务: 未启动${NC}"
    fi

    # 前端状态
    if [ -f "$FRONTEND_PID" ]; then
        pid=$(cat "$FRONTEND_PID")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}前端服务: 运行中 (PID: $pid)${NC}"
        else
            echo -e "${RED}前端服务: 已停止${NC}"
        fi
    else
        echo -e "${RED}前端服务: 未启动${NC}"
    fi

    echo -e "${BLUE}========================================${NC}"
}

# 显示帮助
show_help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start     安装依赖并启动服务 (默认)"
    echo "  stop      停止所有服务"
    echo "  restart   重启所有服务"
    echo "  status    查看服务状态"
    echo "  logs      查看日志"
    echo "  help      显示帮助信息"
    echo ""
    echo "访问地址:"
    echo "  前端: http://localhost:5173"
    echo "  后端: http://localhost:8000"
}

# 查看日志
show_logs() {
    echo -e "${YELLOW}后端日志 (最后 50 行):${NC}"
    if [ -f "$BACKEND_LOG" ]; then
        tail -50 "$BACKEND_LOG"
    else
        echo "暂无日志"
    fi

    echo ""
    echo -e "${YELLOW}前端日志 (最后 50 行):${NC}"
    if [ -f "$FRONTEND_LOG" ]; then
        tail -50 "$FRONTEND_LOG"
    else
        echo "暂无日志"
    fi
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            check_dependencies
            install_backend
            install_frontend
            start_backend
            start_frontend
            echo ""
            show_status
            echo ""
            echo -e "${GREEN}部署完成！${NC}"
            echo -e "${GREEN}前端地址: http://localhost:5173${NC}"
            echo -e "${GREEN}后端地址: http://localhost:8000${NC}"
            echo -e "${YELLOW}提示: 通过内网穿透将 localhost:5173 映射到外部即可访问${NC}"
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            sleep 1
            check_dependencies
            start_backend
            start_frontend
            show_status
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}未知命令: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
