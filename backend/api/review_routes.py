"""
Review Queue API Routes

Endpoints for human review of Bronze-tier predictions from self-training.
Enables the feedback loop for Explainable AI.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import json
import os
import sqlite3
from pathlib import Path

router = APIRouter(prefix="/api/v1/review", tags=["Review Queue"])

# Path to bronze log file
PROJECT_ROOT = Path(__file__).parent.parent.parent
BRONZE_LOG_PATH = PROJECT_ROOT / "output" / "self_train_bronze.jsonl"
DB_PATH = PROJECT_ROOT / "vulnerability_db.sqlite"


# Pydantic Models

class BronzeItem(BaseModel):
    """A bronze-tier prediction awaiting review"""
    id: int
    bug_id: str
    platform: str
    summary: str
    predicted_labels: List[str]
    reasoning: Optional[str] = None
    confidence: float
    similarity_scores: List[float] = Field(default_factory=list)
    timestamp: str
    status: str = "pending"  # pending, approved, rejected


class ReviewQueueResponse(BaseModel):
    """Response for review queue listing"""
    items: List[BronzeItem]
    total: int
    offset: int
    limit: int
    pending_count: int
    approved_count: int
    rejected_count: int


class ApproveRequest(BaseModel):
    """Request to approve a bronze item with optional label edits"""
    labels: List[str] = Field(..., description="Confirmed labels (can be edited from predicted)")
    reasoning: Optional[str] = Field(None, description="Optional reasoning to store")


class ReviewStats(BaseModel):
    """Statistics about the review queue"""
    total_bronze: int
    pending: int
    approved: int
    rejected: int
    platforms: dict


# In-memory status tracking (persists to JSON file)
REVIEW_STATUS_FILE = PROJECT_ROOT / "output" / "review_status.json"


def load_review_status() -> dict:
    """Load review status from file"""
    if REVIEW_STATUS_FILE.exists():
        with open(REVIEW_STATUS_FILE) as f:
            return json.load(f)
    return {}


def save_review_status(status: dict):
    """Save review status to file"""
    os.makedirs(REVIEW_STATUS_FILE.parent, exist_ok=True)
    with open(REVIEW_STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)


def load_bronze_items() -> List[dict]:
    """Load all bronze items from JSONL log"""
    items = []
    if not BRONZE_LOG_PATH.exists():
        return items

    with open(BRONZE_LOG_PATH) as f:
        for i, line in enumerate(f):
            if line.strip():
                item = json.loads(line)
                item['id'] = i  # Use line number as ID
                items.append(item)

    return items


@router.get("/queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    max_confidence: Optional[float] = Query(None, ge=0, le=1)
):
    """
    Get bronze items for review with filtering and pagination.

    Bronze items are predictions with confidence between 0.50-0.70
    that need human review before being promoted to the training set.
    """
    # Load all bronze items
    all_items = load_bronze_items()
    review_status = load_review_status()

    # Enrich with status
    for item in all_items:
        item['status'] = review_status.get(str(item['id']), {}).get('status', 'pending')

    # Apply filters
    filtered = all_items

    if platform:
        filtered = [i for i in filtered if i.get('platform') == platform]

    if status_filter:
        filtered = [i for i in filtered if i['status'] == status_filter]

    if min_confidence is not None:
        filtered = [i for i in filtered if i.get('confidence', 0) >= min_confidence]

    if max_confidence is not None:
        filtered = [i for i in filtered if i.get('confidence', 0) <= max_confidence]

    # Calculate counts
    pending_count = sum(1 for i in all_items if i['status'] == 'pending')
    approved_count = sum(1 for i in all_items if i['status'] == 'approved')
    rejected_count = sum(1 for i in all_items if i['status'] == 'rejected')

    # Paginate
    paginated = filtered[offset:offset + limit]

    # Convert to response model
    response_items = []
    for item in paginated:
        response_items.append(BronzeItem(
            id=item['id'],
            bug_id=item['bug_id'],
            platform=item['platform'],
            summary=item.get('summary', ''),
            predicted_labels=item.get('predicted_labels', []),
            reasoning=item.get('reasoning'),
            confidence=item.get('confidence', 0.0),
            similarity_scores=item.get('similarity_scores', []),
            timestamp=item.get('timestamp', ''),
            status=item['status']
        ))

    return ReviewQueueResponse(
        items=response_items,
        total=len(filtered),
        offset=offset,
        limit=limit,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count
    )


@router.get("/queue/{item_id}", response_model=BronzeItem)
async def get_review_item(item_id: int):
    """Get a single bronze item by ID"""
    all_items = load_bronze_items()
    review_status = load_review_status()

    for item in all_items:
        if item['id'] == item_id:
            item['status'] = review_status.get(str(item_id), {}).get('status', 'pending')
            return BronzeItem(
                id=item['id'],
                bug_id=item['bug_id'],
                platform=item['platform'],
                summary=item.get('summary', ''),
                predicted_labels=item.get('predicted_labels', []),
                reasoning=item.get('reasoning'),
                confidence=item.get('confidence', 0.0),
                similarity_scores=item.get('similarity_scores', []),
                timestamp=item.get('timestamp', ''),
                status=item['status']
            )

    raise HTTPException(status_code=404, detail=f"Item {item_id} not found")


@router.post("/queue/{item_id}/approve")
async def approve_item(item_id: int, request: ApproveRequest):
    """
    Approve a bronze item and promote it to the database.

    This updates the vulnerability record with:
    - labels_source = 'human_review'
    - The confirmed labels
    - Optional reasoning
    """
    all_items = load_bronze_items()
    review_status = load_review_status()

    # Find the item
    item = None
    for i in all_items:
        if i['id'] == item_id:
            item = i
            break

    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    bug_id = item['bug_id']

    # Update database
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE vulnerabilities
            SET labels = ?, labels_source = ?, reasoning = ?
            WHERE bug_id = ?
        """, (
            json.dumps(request.labels),
            'human_review',
            request.reasoning or item.get('reasoning', ''),
            bug_id
        ))

        conn.commit()
        updated = cursor.rowcount
        conn.close()

        if updated == 0:
            raise HTTPException(status_code=404, detail=f"Bug {bug_id} not found in database")

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Update status tracking
    review_status[str(item_id)] = {
        'status': 'approved',
        'labels': request.labels,
        'reasoning': request.reasoning,
        'reviewed_at': datetime.utcnow().isoformat(),
        'bug_id': bug_id
    }
    save_review_status(review_status)

    return {
        "message": "Item approved and database updated",
        "bug_id": bug_id,
        "labels": request.labels,
        "labels_source": "human_review"
    }


@router.post("/queue/{item_id}/reject")
async def reject_item(item_id: int, reason: Optional[str] = None):
    """
    Reject a bronze item (mark as reviewed but not promoted).

    Rejected items stay in the queue for reference but won't
    be promoted to the training set.
    """
    all_items = load_bronze_items()
    review_status = load_review_status()

    # Verify item exists
    item = None
    for i in all_items:
        if i['id'] == item_id:
            item = i
            break

    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

    # Update status
    review_status[str(item_id)] = {
        'status': 'rejected',
        'reason': reason,
        'reviewed_at': datetime.utcnow().isoformat(),
        'bug_id': item['bug_id']
    }
    save_review_status(review_status)

    return {
        "message": "Item rejected",
        "bug_id": item['bug_id'],
        "reason": reason
    }


@router.get("/stats", response_model=ReviewStats)
async def get_review_stats():
    """Get statistics about the review queue"""
    all_items = load_bronze_items()
    review_status = load_review_status()

    # Enrich with status
    for item in all_items:
        item['status'] = review_status.get(str(item['id']), {}).get('status', 'pending')

    # Calculate stats
    pending = sum(1 for i in all_items if i['status'] == 'pending')
    approved = sum(1 for i in all_items if i['status'] == 'approved')
    rejected = sum(1 for i in all_items if i['status'] == 'rejected')

    # Platform breakdown
    platforms = {}
    for item in all_items:
        platform = item.get('platform', 'Unknown')
        if platform not in platforms:
            platforms[platform] = {'total': 0, 'pending': 0}
        platforms[platform]['total'] += 1
        if item['status'] == 'pending':
            platforms[platform]['pending'] += 1

    return ReviewStats(
        total_bronze=len(all_items),
        pending=pending,
        approved=approved,
        rejected=rejected,
        platforms=platforms
    )


@router.post("/batch/approve")
async def batch_approve(item_ids: List[int]):
    """
    Approve multiple items at once using their predicted labels.

    Useful for quickly processing items with high confidence
    where the predicted labels look correct.
    """
    all_items = load_bronze_items()
    review_status = load_review_status()

    results = {"approved": [], "failed": []}

    for item_id in item_ids:
        item = None
        for i in all_items:
            if i['id'] == item_id:
                item = i
                break

        if not item:
            results['failed'].append({"id": item_id, "reason": "not found"})
            continue

        bug_id = item['bug_id']
        labels = item.get('predicted_labels', [])
        reasoning = item.get('reasoning', '')

        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=30)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE vulnerabilities
                SET labels = ?, labels_source = ?, reasoning = ?
                WHERE bug_id = ?
            """, (
                json.dumps(labels),
                'human_review',
                reasoning,
                bug_id
            ))

            conn.commit()
            conn.close()

            # Update status
            review_status[str(item_id)] = {
                'status': 'approved',
                'labels': labels,
                'reasoning': reasoning,
                'reviewed_at': datetime.utcnow().isoformat(),
                'bug_id': bug_id
            }

            results['approved'].append({"id": item_id, "bug_id": bug_id})

        except Exception as e:
            results['failed'].append({"id": item_id, "reason": str(e)})

    save_review_status(review_status)

    return {
        "message": f"Processed {len(item_ids)} items",
        "approved_count": len(results['approved']),
        "failed_count": len(results['failed']),
        "results": results
    }
