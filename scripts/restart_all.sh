#!/bin/bash

# Restart all services: main.py + api.py + streamlit_app.py

echo "🛑 Stopping all processes..."
pkill -9 -f "python3 main.py" 2>/dev/null || true
pkill -9 -f "streamlit\|uvicorn" 2>/dev/null || true
sleep 2

echo "✅ Stopped"
echo ""
echo "🧹 Clearing Python cache..."
find /home/wner/switch -name "*.pyc" -delete 2>/dev/null
find /home/wner/switch -type d -name "__pycache__" 2>/dev/null | while read d; do rm -rf "$d" 2>/dev/null; done
echo ""
mkdir -p /home/wner/switch/logs

echo "🚀 Starting collector (main.py)..."
cd /home/wner/switch && source venv/bin/activate && nohup python3 main.py > logs/main.log 2>&1 &
sleep 3

echo "🚀 Starting API (port 8000)..."
cd /home/wner/switch && source venv/bin/activate && nohup uvicorn api:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
sleep 3
echo "   Calling /reload-parsers..."
curl -s http://127.0.0.1:8000/reload-parsers 2>/dev/null | head -1 || echo "   (API starting, visit /reload-parsers later)"

echo "🚀 Starting Streamlit (port 8501)..."
cd /home/wner/switch && source venv/bin/activate && nohup streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 > logs/streamlit.log 2>&1 &
sleep 3

echo ""
echo "✅ All services restarted!"
echo ""
echo "📊 Status:"
ps aux | grep -E "python3 main.py|uvicorn|streamlit" | grep -v grep | awk '{print "  " $2, $11}' || echo "  No processes"
echo ""
echo "📝 Logs:"
echo "  Collector: /home/wner/switch/logs/main.log"
echo "  API:       /home/wner/switch/logs/api.log"
echo "  Web:       /home/wner/switch/logs/streamlit.log"
echo ""
echo "🌐 URLs:"
echo "  API:       http://localhost:8000 or http://monitor.switch.test:8000"
echo "  Streamlit: http://localhost:8501 or http://monitor.switch.test (via nginx)"
