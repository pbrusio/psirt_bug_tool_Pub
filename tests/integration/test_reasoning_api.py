"""
Integration tests for Reasoning API endpoints

Tests route registration and basic API behavior without requiring model loading.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestReasoningRouteRegistration:
    """Test that reasoning routes are properly registered"""

    def test_router_import(self):
        """Test that reasoning router can be imported"""
        from backend.api.reasoning_routes import router
        assert router is not None
        assert router.prefix == "/api/v1/reasoning"

    def test_router_has_endpoints(self):
        """Test that all expected endpoints are registered"""
        from backend.api.reasoning_routes import router
        routes = [r.path for r in router.routes]

        # Routes include full path with prefix
        assert "/api/v1/reasoning/explain" in routes
        assert "/api/v1/reasoning/remediate" in routes
        assert "/api/v1/reasoning/ask" in routes
        assert "/api/v1/reasoning/summary" in routes
        assert "/api/v1/reasoning/health" in routes


class TestPydanticModels:
    """Test Pydantic request/response models"""

    def test_explain_request_model(self):
        """Test ExplainRequest model validation"""
        from backend.api.reasoning_routes import ExplainRequest

        # Valid request with summary
        req = ExplainRequest(
            psirt_summary="Test vulnerability",
            platform="IOS-XE"
        )
        assert req.psirt_summary == "Test vulnerability"
        assert req.platform == "IOS-XE"

        # Valid request with psirt_id
        req2 = ExplainRequest(
            psirt_id="cisco-sa-test",
            platform="IOS-XE"
        )
        assert req2.psirt_id == "cisco-sa-test"

    def test_explain_request_requires_platform(self):
        """Test that ExplainRequest requires platform"""
        from backend.api.reasoning_routes import ExplainRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExplainRequest(psirt_summary="Test")  # Missing platform

    def test_remediate_request_model(self):
        """Test RemediateRequest model validation"""
        from backend.api.reasoning_routes import RemediateRequest

        req = RemediateRequest(
            psirt_id="cisco-sa-test",
            platform="IOS-XE"
        )
        assert req.psirt_id == "cisco-sa-test"

    def test_ask_request_model(self):
        """Test AskRequest model validation"""
        from backend.api.reasoning_routes import AskRequest

        req = AskRequest(question="How many vulnerabilities?")
        assert req.question == "How many vulnerabilities?"

    def test_ask_request_validates_length(self):
        """Test that AskRequest accepts reasonable length questions"""
        from backend.api.reasoning_routes import AskRequest

        # Should accept normal questions
        req = AskRequest(question="How many vulnerabilities are there in my network?")
        assert len(req.question) > 0

    def test_response_models_can_be_created(self):
        """Test that response models work correctly"""
        from backend.api.reasoning_routes import ExplainResponse, AskResponse

        # Test ExplainResponse - include timestamp field
        explain = ExplainResponse(
            request_id="test-123",
            psirt_id="cisco-sa-test",
            platform="IOS-XE",
            labels_explained=["MGMT_SSH_HTTP"],
            explanation="Test explanation",
            confidence=0.85,
            reasoning_time_ms=1234.5,
            timestamp=datetime.now().isoformat()
        )
        assert explain.request_id == "test-123"

        # Test AskResponse - include timestamp and sources fields
        ask = AskResponse(
            request_id="ask-123",
            question="Test question",
            answer="Test answer",
            sources=[],
            confidence=0.75,
            reasoning_time_ms=500.0,
            timestamp=datetime.now().isoformat()
        )
        assert ask.answer == "Test answer"


class TestRateLimitConfiguration:
    """Test that rate limits are configured in app.py"""

    def test_rate_limits_defined(self):
        """Test that rate limits are defined for reasoning endpoints"""
        # Check the source code for rate limit configuration
        app_path = Path(__file__).parent.parent.parent / "backend" / "app.py"
        content = app_path.read_text()

        assert "/api/v1/reasoning/explain" in content
        assert "/api/v1/reasoning/remediate" in content
        assert "/api/v1/reasoning/ask" in content
        assert "/api/v1/reasoning/summary" in content


class TestHealthEndpoint:
    """Test health endpoint behavior"""

    @pytest.mark.asyncio
    async def test_health_endpoint_structure(self):
        """Test health endpoint returns proper structure"""
        from backend.api.reasoning_routes import reasoning_health

        # Call the endpoint function directly
        result = await reasoning_health()

        assert "status" in result
        assert "endpoints" in result
        assert len(result["endpoints"]) == 4


class TestReasoningEngineIntegration:
    """Test ReasoningEngine integration (with mocking)"""

    def test_engine_can_be_instantiated(self):
        """Test that ReasoningEngine can be created with mocked analyzer"""
        with patch('backend.core.reasoning_engine.get_analyzer') as mock_get:
            mock_get.return_value = MagicMock()

            from backend.core.reasoning_engine import ReasoningEngine
            engine = ReasoningEngine()

            # Verify it loaded taxonomies
            assert len(engine._taxonomies) > 0

    @pytest.mark.asyncio
    async def test_explain_method_exists_and_callable(self):
        """Test that explain method works with mocked inference"""
        with patch('backend.core.reasoning_engine.get_analyzer') as mock_get:
            mock_get.return_value = MagicMock()

            from backend.core.reasoning_engine import ReasoningEngine
            engine = ReasoningEngine()

            # Mock the inference to avoid needing real model
            with patch.object(engine, '_run_inference') as mock_inf:
                mock_inf.return_value = {
                    'response': 'Mocked explanation',
                    'confidence': 0.85
                }

                result = await engine.explain(
                    psirt_summary="Test vulnerability in SSH",
                    labels=['MGMT_SSH_HTTP'],
                    platform='IOS-XE'
                )

                assert 'explanation' in result
                assert 'confidence' in result
