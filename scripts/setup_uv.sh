#!/bin/bash

# Pincer x402 Demo - Solana Priority Setup Script
# This script uses uv for faster installation

set -e

echo "🚀 Setting up Pincer x402 Demo (Solana Priority)"
echo "================================================"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo "✅ uv installed"
else
    echo "✅ uv found"
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
uv venv
source .venv/bin/activate || . .venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing dependencies with uv (this is fast!)..."
uv pip install -r requirements.txt

# Copy environment template
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "✅ Created .env - please edit it with your Solana wallet keys"
else
    echo ""
    echo "⚠️  .env already exists, skipping..."
fi

# Initialize database
echo ""
echo "🗄️  Initializing database..."
uv run python scripts/init_ledger.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Solana wallet keys (get them from a wallet like Phantom):"
echo "   SVM_PRIVATE_KEY=your_base58_private_key"
echo "   TREASURY_SVM_PRIVATE_KEY=your_treasury_key"
echo ""
echo "2. Need test SOL? Get some from the faucet:"
echo "   https://faucet.solana.com/ (Select 'Devnet')"
echo ""
echo "3. Start the entire ecosystem (Facilitator, Resource, Merchant):"
echo "   uv run scripts/run_all.py"
echo ""
echo "4. In a NEW terminal, run the AI Agent demo:"
echo "   make demo"
echo ""

