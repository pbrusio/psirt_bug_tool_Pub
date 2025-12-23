"""
Unit tests for ReasoningEngine

Tests the core reasoning logic without requiring the full MLX model.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.reasoning_engine import (
    ReasoningEngine,
    classify_intent,
    extract_entities,
    QueryIntent,
    get_reasoning_engine
)


class TestIntentClassification:
    """Test intent classification logic"""

    def test_list_devices_intent(self):
        """Test device listing queries are classified correctly"""
        questions = [
            "List all devices in my inventory",
            "Show inventory",
            "Show me my inventory list",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.LIST_DEVICES, f"Failed for: {q}"

    def test_device_vulnerabilities_intent(self):
        """Test device-vulnerability queries (devices + vulns mentioned)"""
        questions = [
            "Which devices are affected by this vulnerability?",
            "What routers are vulnerable?",
            "Bugs affecting my switches",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.DEVICE_VULNERABILITIES, f"Failed for: {q}"

    def test_list_vulnerabilities_intent(self):
        """Test vulnerability listing queries"""
        questions = [
            "Which vulnerabilities affect my network?",
            "Show me critical bugs",
            "List all PSIRTs for IOS-XE",
            "What CVEs are there?",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.LIST_VULNERABILITIES, f"Failed for: {q}"

    def test_explain_vulnerability_intent(self):
        """Test explanation queries for vulnerabilities"""
        questions = [
            "Explain cisco-sa-20231018-iosxe-webui",
            "Explain this CVE to me",
            "Why is this advisory important?",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.EXPLAIN_VULNERABILITY, f"Failed for: {q}"

    def test_explain_label_intent(self):
        """Test label explanation queries"""
        questions = [
            "What does SEC_CoPP mean?",
            "What is MGMT_SSH_HTTP?",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.EXPLAIN_LABEL, f"Failed for: {q}"

    def test_remediation_intent(self):
        """Test remediation queries"""
        questions = [
            "How do I fix this vulnerability?",
            "How can I mitigate the SSH vulnerability?",
            "Is there a workaround?",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.REMEDIATION, f"Failed for: {q}"

    def test_count_intent(self):
        """Test count queries"""
        questions = [
            "How many vulnerabilities are there?",
            "What's the total number of advisories?",
            "How many bugs do we have?",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.COUNT, f"Failed for: {q}"

    def test_summary_intent(self):
        """Test summary queries"""
        questions = [
            "Give me a summary of my security posture",
            "Weekly vulnerability report",
            "Summarize my risk status",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.SUMMARY, f"Failed for: {q}"

    def test_unknown_intent(self):
        """Test unknown/ambiguous queries"""
        questions = [
            "Hello",
            "What time is it?",
            "Tell me about clouds",
        ]
        for q in questions:
            intent, confidence, _ = classify_intent(q)
            assert intent == QueryIntent.UNKNOWN, f"Failed for: {q}"
            assert confidence < 0.7  # Low confidence for unknown


class TestEntityExtraction:
    """Test entity extraction from questions"""

    def test_extract_platform(self):
        """Test platform extraction"""
        entities = extract_entities("Which IOS-XE devices are affected?", QueryIntent.LIST_DEVICES)
        assert 'platforms' in entities
        assert 'IOS-XE' in entities['platforms']

    def test_extract_multiple_platforms(self):
        """Test extracting multiple platforms"""
        entities = extract_entities("Compare IOS-XE and IOS-XR vulnerabilities", QueryIntent.LIST_VULNERABILITIES)
        assert 'platforms' in entities
        assert 'IOS-XE' in entities['platforms']
        assert 'IOS-XR' in entities['platforms']

    def test_extract_severity(self):
        """Test severity extraction"""
        entities = extract_entities("Show me critical vulnerabilities", QueryIntent.LIST_VULNERABILITIES)
        assert entities.get('severity') == 'critical'

    def test_extract_timeframe(self):
        """Test timeframe extraction"""
        entities = extract_entities("What happened last week?", QueryIntent.SUMMARY)
        assert entities.get('timeframe') == 'week'

    def test_extract_advisory_id(self):
        """Test advisory ID extraction"""
        entities = extract_entities("Explain cisco-sa-20231018-iosxe-webui", QueryIntent.EXPLAIN_VULNERABILITY)
        assert entities.get('advisory_id') == 'cisco-sa-20231018-iosxe-webui'

    def test_extract_labels(self):
        """Test label extraction"""
        entities = extract_entities("What does SEC_CoPP mean?", QueryIntent.EXPLAIN_LABEL)
        assert 'labels' in entities
        assert 'SEC_CoPP' in entities['labels']

    def test_extract_version(self):
        """Test version extraction"""
        entities = extract_entities("Devices running 17.9.4", QueryIntent.LIST_DEVICES)
        assert entities.get('version') == '17.9.4'


class TestReasoningEngine:
    """Test ReasoningEngine class methods"""

    @pytest.fixture
    def engine(self):
        """Create a ReasoningEngine instance with mocked model"""
        with patch('backend.core.reasoning_engine.get_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            engine = ReasoningEngine()
            yield engine

    def test_load_taxonomies(self, engine):
        """Test taxonomy loading"""
        assert len(engine._taxonomies) > 0
        assert 'IOS-XE' in engine._taxonomies

    def test_format_device_context(self, engine):
        """Test device context formatting"""
        device = {
            'hostname': 'switch-01',
            'version': '17.9.4',
            'platform': 'IOS-XE',
            'hardware_model': 'Cat9300',
            'features': ['MGMT_SSH_HTTP', 'SEC_CoPP']
        }
        context = engine._format_device_context(device)
        assert 'switch-01' in context
        assert '17.9.4' in context
        assert 'Cat9300' in context


class TestReasoningEngineSingleton:
    """Test singleton behavior"""

    def test_singleton_returns_same_instance(self):
        """Test that get_reasoning_engine returns the same instance"""
        with patch('backend.core.reasoning_engine.get_analyzer') as mock_get:
            mock_get.return_value = MagicMock()

            # Reset singleton for test
            import backend.core.reasoning_engine as re_module
            re_module._reasoning_engine_instance = None

            engine1 = get_reasoning_engine()
            engine2 = get_reasoning_engine()
            assert engine1 is engine2


class TestAsyncMethods:
    """Test async methods of ReasoningEngine"""

    @pytest.fixture
    def mock_engine(self):
        """Create engine with fully mocked dependencies"""
        with patch('backend.core.reasoning_engine.get_analyzer') as mock_get:
            mock_analyzer = MagicMock()
            mock_labeler = MagicMock()
            mock_analyzer.pipeline.labeler = mock_labeler
            mock_get.return_value = mock_analyzer

            engine = ReasoningEngine()
            yield engine

    @pytest.mark.asyncio
    async def test_explain_with_summary(self, mock_engine):
        """Test explain with provided summary"""
        with patch.object(mock_engine, '_run_inference') as mock_inf:
            mock_inf.return_value = {
                'response': 'This is an explanation',
                'confidence': 0.85
            }

            result = await mock_engine.explain(
                psirt_summary="SSH vulnerability",
                labels=['MGMT_SSH_HTTP'],
                platform='IOS-XE'
            )

            assert 'explanation' in result
            assert 'confidence' in result

    @pytest.mark.asyncio
    async def test_explain_requires_summary_or_id(self, mock_engine):
        """Test that explain requires either summary or psirt_id"""
        with pytest.raises(ValueError):
            await mock_engine.explain(
                platform='IOS-XE'
                # No psirt_summary or psirt_id
            )

    @pytest.mark.asyncio
    async def test_ask_routing(self, mock_engine):
        """Test that ask routes to correct handler"""
        with patch.object(mock_engine, '_handle_count_query') as mock_count:
            mock_count.return_value = {'answer': 'Total: 100', 'sources': []}

            result = await mock_engine.ask("How many vulnerabilities are there?")

            mock_count.assert_called_once()
