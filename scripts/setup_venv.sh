#!/bin/bash
# Setup virtual environment for PSIRT Labeling Pipeline

echo "🔧 Setting up PSIRT Labeling Pipeline environment..."
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✅ Virtual environment created"
echo ""
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip -q

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run the pipeline:"
echo "  python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv"
echo ""
echo "To test with 5 PSIRTs:"
echo "  python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv --limit 5"
echo "=========================================="
