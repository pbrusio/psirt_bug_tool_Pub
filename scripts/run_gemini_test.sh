#!/bin/bash
# Quick test script for Gemini-based PSIRT labeling

echo "🚀 PSIRT Labeling Pipeline - Gemini Test"
echo "=========================================="
echo ""

# Check if API key is set
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "❌ Error: GOOGLE_API_KEY environment variable not set"
    echo ""
    echo "Please set your Gemini API key:"
    echo "  export GOOGLE_API_KEY='your-key-here'"
    echo ""
    echo "Get your key at: https://aistudio.google.com/app/apikey"
    exit 1
fi

# Check if google-generativeai is installed
if ! python3 -c "import google.generativeai" 2>/dev/null; then
    echo "📦 Installing google-generativeai..."
    pip install -q google-generativeai
fi

echo "✅ API key found"
echo "✅ Dependencies installed"
echo ""

# Run test with 5 PSIRTs
echo "🔄 Processing 5 PSIRTs as test..."
echo ""

python3 psirt_labeling_pipeline.py \
    gemini_enriched_PSIRTS_mrk1.csv \
    --provider gemini \
    --limit 5 \
    --output-dir output_test

echo ""
echo "=========================================="
echo "✅ Test complete!"
echo ""
echo "📁 Results in: output_test/"
echo ""
echo "To validate outputs:"
echo "  python3 validate_output.py output_test/"
echo ""
echo "To run full pipeline:"
echo "  python3 psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv"
