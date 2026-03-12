#!/bin/bash
#
# 使用 tmux 启动所有服务（一个窗口，多个面板）
#

cd "$(dirname "$0")/.."

SESSION="github-agent"

# 如果 session 已存在，先删除
tmux kill-session -t $SESSION 2>/dev/null

echo "创建 tmux session: $SESSION"
tmux new-session -d -s $SESSION

# 窗口 1: KB Service (左侧面板)
tmux rename-window -t $SESSION:0 'services'
tmux send-keys -t $SESSION:0 'cd "$(dirname "$0")/.." && source venv/bin/activate && echo "=== KB Service ===" && python3 -m knowledge_base.kb_service --host 0.0.0.0 --port 8000' C-m

# 分割窗口，右侧启动主服务
tmux split-window -h -t $SESSION:0
tmux send-keys -t $SESSION:0.right 'cd "$(dirname "$0")/.." && source venv/bin/activate && sleep 3 && echo "=== Main Service ===" && python3 main.py --port 8080' C-m

# 分割下方面板显示日志
tmux split-window -v -t $SESSION:0.left
tmux send-keys -t $SESSION:0 'cd "$(dirname "$0")/.." && echo "=== 日志监控 ===" && tail -f /tmp/kb_service.log' C-m

# 调整布局
tmux select-layout -t $SESSION:0 tiled

# 附加到 session
echo "启动完成，正在进入 tmux..."
echo "提示: 按 Ctrl+B 然后按 D 可以分离会话"
echo "      运行 'tmux attach -t github-agent' 重新进入"
sleep 1
tmux attach -t $SESSION
