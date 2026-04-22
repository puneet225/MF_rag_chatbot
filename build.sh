#!/usr/bin/env bash
# Render Build Script
# ===================

set -e # Exit on error

echo "🛠️ Starting build..."

# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers (Chromium)
echo "🌐 Installing Playwright Chromium..."
playwright install --with-deps chromium

echo "✅ Build complete!"
