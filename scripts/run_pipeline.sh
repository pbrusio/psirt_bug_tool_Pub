#!/bin/bash
# Quick runner for PSIRT labeling pipeline with Gemini

# Activate venv if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    echo "🔄 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env with your GEMINI_API_KEY"
    exit 1
fi

# Run with provided arguments or defaults
if [ $# -eq 0 ]; then
    echo "🚀 Running PSIRT Labeling Pipeline (Gemini)"
    echo "   Mode: Full run (all PSIRTs)"
    echo ""
    python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv
else
    echo "🚀 Running PSIRT Labeling Pipeline (Gemini)"
    echo "   Arguments: $@"
    echo ""
    python psirt_labeling_pipeline.py gemini_enriched_PSIRTS_mrk1.csv "$@"
fi
