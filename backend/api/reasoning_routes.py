"""
Reasoning Layer API Routes

Provides AI-powered explanation, remediation, natural language query,
and executive summary endpoints. These endpoints leverage the fine-tuned
Foundation-Sec-8B model to provide contextual understanding that batch
labeling cannot deliver.

Endpoints:
- POST /api/v1/reasoning/explain - Explain why labels apply to a PSIRT
- POST /api/v1/reasoning/remediate - Generate remediation guidance
- POST /api/v1/reasoning/ask - Natural language queries
- GET  /api/v1/reasoning/summary - Executive posture summary
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from backend.core.reasoning_engine import get_reasoning_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reasoning", tags=["reasoning"])


# =============================================================================
# Request/Response Models
# =============================================================================

# Explain Models
class ExplainRequest(BaseModel):
    """Request to explain vulnerability assessment"""
    psirt_id: Optional[str] = Field(None, description="Advisory ID (e.g., 'cisco-sa-iosxe-ssh-dos')")
    psirt_summary: Optional[str] = Field(None, description="PSIRT summary text (if no psirt_id)")
    labels: Optional[List[str]] = Field(None, description="Labels to explain (fetched if not provided)")
    platform: str = Field(..., description="Platform (IOS-XE, IOS-XR, ASA, FTD, NX-OS)")
    device_id: Optional[int] = Field(None, description="Device ID for context (from inventory)")
    device_features: Optional[List[str]] = Field(None, description="Device features if no device_id")
    question_type: str = Field(
        default="why",
        description="Type of explanation: 'why' (why labels apply), 'impact' (business impact), 'technical' (deep dive)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "psirt_id": "cisco-sa-20231018-iosxe-webui",
                "platform": "IOS-XE",
                "device_id": 1,
                "question_type": "why"
            }
        }


class ExplainResponse(BaseModel):
    """Explanation response"""
    request_id: str
    psirt_id: Optional[str]
    platform: str
    labels_explained: List[str]
    explanation: str
    device_context: Optional[str] = None
    affected: Optional[bool] = None
    confidence: float
    reasoning_time_ms: float
    timestamp: datetime


# Remediate Models
class RemediateRequest(BaseModel):
    """Request for remediation guidance"""
    psirt_id: str = Field(..., description="Advisory ID")
    platform: str = Field(..., description="Platform")
    device_id: Optional[int] = Field(None, description="Device ID for specific guidance")
    device_version: Optional[str] = Field(None, description="Device software version")
    device_features: Optional[List[str]] = Field(None, description="Configured features")
    include_commands: bool = Field(default=True, description="Include CLI commands")
    include_upgrade_path: bool = Field(default=True, description="Include upgrade info")

    class Config:
        json_schema_extra = {
            "example": {
                "psirt_id": "cisco-sa-20231018-iosxe-webui",
                "platform": "IOS-XE",
                "device_version": "17.9.4"
            }
        }


class RemediationOption(BaseModel):
    """Single remediation option"""
    action: str  # "disable_feature", "apply_acl", "upgrade", "workaround"
    title: str
    description: str
    commands: Optional[List[str]] = None
    impact: str
    effectiveness: str  # "full", "partial", "temporary"


class RemediateResponse(BaseModel):
    """Remediation guidance response"""
    request_id: str
    psirt_id: str
    platform: str
    device_context: Optional[str]
    severity: str
    options: List[RemediationOption]
    recommended_option: int
    upgrade_path: Optional[Dict[str, Any]] = None
    confidence: float
    reasoning_time_ms: float
    timestamp: datetime


# Ask Models
class AskRequest(BaseModel):
    """Natural language query"""
    question: str = Field(..., description="Question in natural language", max_length=1000)
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context hints")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Which devices are affected by critical SSH vulnerabilities?"
            }
        }


class AskResponse(BaseModel):
    """Natural language response"""
    request_id: str
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    suggested_actions: Optional[List[str]] = None
    follow_up_questions: Optional[List[str]] = None
    confidence: float
    reasoning_time_ms: float
    timestamp: datetime


# Summary Models
class CriticalAction(BaseModel):
    """Critical action item"""
    priority: int
    action: str
    affected_devices: Optional[int] = None
    advisory: Optional[str] = None


class ImpactMetrics(BaseModel):
    """Metrics for a specific vulnerability type"""
    total: int
    critical_high: int
    by_platform: Dict[str, int]
    affecting_inventory: Optional[int] = Field(
        default=None,
        description="Count matching inventory platforms (PSIRTs only)"
    )
    inventory_critical_high: Optional[int] = Field(
        default=None,
        description="Critical/High count matching inventory (PSIRTs only)"
    )


class SummaryResponse(BaseModel):
    """Vulnerability posture summary"""
    request_id: str
    period: str
    total_advisories: int
    total_bugs_in_db: Optional[int] = Field(
        default=None,
        description="Reference count of all bugs in the database"
    )
    inventory_devices_scanned: Optional[int] = Field(
        default=None,
        description="Devices with a stored scan result"
    )
    inventory_critical_high: Optional[int] = Field(
        default=None,
        description="Critical/high count from latest scans"
    )
    inventory_medium_low: Optional[int] = Field(
        default=None,
        description="Medium/low count from latest scans"
    )
    inventory_platforms: Optional[List[str]] = Field(
        default=None,
        description="Platforms present in inventory"
    )
    affecting_environment: int
    summary_text: str
    risk_assessment: str  # "critical", "elevated", "moderate", "low"
    critical_actions: List[CriticalAction]
    trends: Optional[Dict[str, Any]] = None
    bugs: Optional[ImpactMetrics] = None
    psirts: Optional[ImpactMetrics] = None
    timestamp: datetime


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/explain", response_model=ExplainResponse)
async def explain_vulnerability(request: ExplainRequest):
    """
    Explain why labels apply to a PSIRT, optionally for a specific device.

    **Use Cases:**
    - "Why is this PSIRT tagged with SEC_CoPP?"
    - "Is my device affected by this vulnerability?"
    - "What's the technical impact of this advisory?"

    The fine-tuned model uses taxonomy definitions and anti-definitions
    to provide accurate, Cisco-specific explanations.

    **Question Types:**
    - `why`: Explain why each label applies (default)
    - `impact`: Business and operational impact analysis
    - `technical`: Deep technical analysis with attack vectors
    """
    start_time = datetime.now()
    request_id = f"expl-{uuid.uuid4().hex[:8]}"

    try:
        engine = get_reasoning_engine()
        result = await engine.explain(
            psirt_id=request.psirt_id,
            psirt_summary=request.psirt_summary,
            labels=request.labels,
            platform=request.platform,
            device_id=request.device_id,
            device_features=request.device_features,
            question_type=request.question_type
        )

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        return ExplainResponse(
            request_id=request_id,
            psirt_id=request.psirt_id,
            platform=request.platform,
            labels_explained=result['labels'],
            explanation=result['explanation'],
            device_context=result.get('device_context'),
            affected=result.get('affected'),
            confidence=result['confidence'],
            reasoning_time_ms=elapsed_ms,
            timestamp=datetime.now()
        )

    except ValueError as e:
        logger.warning(f"Explain validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Explain failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remediate", response_model=RemediateResponse)
async def get_remediation(request: RemediateRequest):
    """
    Generate remediation guidance for a vulnerability.

    **Provides:**
    - Multiple remediation options (disable feature, ACL, upgrade, workaround)
    - Platform-specific CLI commands
    - Impact assessment for each option
    - Effectiveness rating (full/partial/temporary)
    - Upgrade path recommendations

    **Options are prioritized** from most effective to least disruptive.
    """
    start_time = datetime.now()
    request_id = f"rem-{uuid.uuid4().hex[:8]}"

    try:
        engine = get_reasoning_engine()
        result = await engine.remediate(
            psirt_id=request.psirt_id,
            platform=request.platform,
            device_id=request.device_id,
            device_version=request.device_version,
            device_features=request.device_features,
            include_commands=request.include_commands,
            include_upgrade_path=request.include_upgrade_path
        )

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        return RemediateResponse(
            request_id=request_id,
            psirt_id=request.psirt_id,
            platform=request.platform,
            device_context=result.get('device_context'),
            severity=result.get('severity', 'unknown'),
            options=[RemediationOption(**opt) for opt in result['options']],
            recommended_option=result.get('recommended_option', 0),
            upgrade_path=result.get('upgrade_path'),
            confidence=result['confidence'],
            reasoning_time_ms=elapsed_ms,
            timestamp=datetime.now()
        )

    except ValueError as e:
        logger.warning(f"Remediate validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Remediation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Answer natural language questions about vulnerabilities.

    Parses the question to understand intent, queries relevant
    data sources, and synthesizes a natural language response.

    **Example Questions:**
    - "Which devices are affected by critical vulnerabilities?"
    - "What's the remediation for the WebUI bug?"
    - "Show me vulnerabilities affecting OSPF"
    - "How many critical bugs affect IOS-XE?"
    - "What does SEC_CoPP mean?"

    **Supported Intents:**
    - List devices/vulnerabilities
    - Explain vulnerabilities or labels
    - Get remediation guidance
    - Count statistics
    - Generate summaries
    """
    start_time = datetime.now()
    request_id = f"ask-{uuid.uuid4().hex[:8]}"

    try:
        engine = get_reasoning_engine()
        result = await engine.ask(
            question=request.question,
            context=request.context
        )

        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        return AskResponse(
            request_id=request_id,
            question=request.question,
            answer=result['answer'],
            sources=result.get('sources', []),
            suggested_actions=result.get('suggested_actions'),
            follow_up_questions=result.get('follow_up_questions'),
            confidence=result['confidence'],
            reasoning_time_ms=elapsed_ms,
            timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"Ask failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    period: str = Query(
        default="week",
        description="Time period: 'week', 'month', or 'YYYY-MM-DD:YYYY-MM-DD'"
    ),
    scope: str = Query(
        default="all",
        description="Scope: 'all', 'critical', or 'device:{id}'"
    ),
    format: str = Query(
        default="brief",
        description="Format: 'brief', 'detailed', or 'executive'"
    )
):
    """
    Generate executive summary of vulnerability posture.

    **Periods:**
    - `week`: Past 7 days
    - `month`: Past 30 days
    - Custom: `YYYY-MM-DD:YYYY-MM-DD`

    **Scopes:**
    - `all`: Full environment
    - `critical`: Only critical/high severity
    - `device:{id}`: Specific device

    **Formats:**
    - `brief`: Quick overview with key metrics
    - `detailed`: Full breakdown with statistics
    - `executive`: Management-friendly summary with recommendations
    """
    start_time = datetime.now()
    request_id = f"sum-{uuid.uuid4().hex[:8]}"

    try:
        engine = get_reasoning_engine()
        result = await engine.summary(
            period=period,
            scope=scope,
            format=format
        )

        return SummaryResponse(
            request_id=request_id,
            period=result['period'],
            total_advisories=result['total_advisories'],
            total_bugs_in_db=result.get('total_bugs_in_db'),
            inventory_devices_scanned=result.get('inventory_devices_scanned'),
            inventory_critical_high=result.get('inventory_critical_high'),
            inventory_medium_low=result.get('inventory_medium_low'),
            inventory_platforms=result.get('inventory_platforms'),
            affecting_environment=result['affecting_environment'],
            summary_text=result['summary_text'],
            risk_assessment=result['risk_assessment'],
            critical_actions=[CriticalAction(**a) for a in result['critical_actions']],
            trends=result.get('trends'),
            bugs=ImpactMetrics(**result['bugs']) if result.get('bugs') else None,
            psirts=ImpactMetrics(**result['psirts']) if result.get('psirts') else None,
            timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"Summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def reasoning_health():
    """Check reasoning layer health"""
    try:
        engine = get_reasoning_engine()
        # Test taxonomy loading
        has_taxonomies = len(engine._taxonomies) > 0

        # Test MLX availability (lazy check)
        mlx_status = "not_tested"
        try:
            labeler = engine._get_labeler()
            mlx_status = "available" if engine._mlx_available else "unavailable"
        except Exception:
            mlx_status = "unavailable"

        return {
            "status": "healthy" if has_taxonomies else "degraded",
            "taxonomies_loaded": len(engine._taxonomies),
            "mlx_status": mlx_status,
            "endpoints": ["/explain", "/remediate", "/ask", "/summary"]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
