#!/bin/bash

# Pincer x402 Demo - 一鍵啟動腳本（使用 uv）
# 在 4 個終端分別運行這個腳本

echo "🚀 Pincer x402 Demo 啟動器"
echo "=========================="
echo ""
echo "請選擇要啟動的服務："
echo ""
echo "1) Resource Server (Port 4021)"
echo "2) Pincer (Port 4022)"
echo "3) Merchant/Shake Shack (Port 4023)"
echo "4) Agent Demo"
echo ""
read -p "輸入選項 (1-4): " choice

case $choice in
  1)
    echo "🍽️  啟動 Resource Server..."
    uv run python src/resource/server.py
    ;;
  2)
    echo "⚡ 啟動 Pincer..."
    uv run python src/pincer/server.py
    ;;
  3)
    echo "🍔 啟動 Shake Shack..."
    uv run python src/merchant/server.py
    ;;
  4)
    echo "🤖 運行 Agent Demo..."
    uv run python src/agent/demo.py
    ;;
  *)
    echo "❌ 無效選項"
    exit 1
    ;;
esac
