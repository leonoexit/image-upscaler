#!/bin/bash
# Setup script for Image Upscaler
set -e

echo "🔧 Setting up Image Upscaler..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
source venv/bin/activate
echo "⬆️  Upgrading pip..."
pip install --upgrade pip setuptools wheel -q

echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# Fix basicsr compatibility with newer torchvision
DEGRADATIONS_FILE=$(find venv -path "*/basicsr/data/degradations.py" -type f 2>/dev/null)
if [ -n "$DEGRADATIONS_FILE" ]; then
    if grep -q "from torchvision.transforms.functional_tensor" "$DEGRADATIONS_FILE"; then
        echo "🔧 Patching basicsr/torchvision compatibility..."
        sed -i '' 's/from torchvision.transforms.functional_tensor import rgb_to_grayscale/from torchvision.transforms.functional import rgb_to_grayscale/' "$DEGRADATIONS_FILE"
    fi
fi

echo ""
echo "✅ Setup complete!"
echo "🚀 Run: source venv/bin/activate && python app.py"
echo "🌐 Then open: http://localhost:8000"
