"""Workflow instance inspection and failure recovery (ADR-0003).

The engine has no auto-retry: a permanently-failed instance stays failed
until an operator resumes it. This is the admin-facing side of that story --
list what's stuck, retry it once the underlying cause is fixed.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.exceptions import bad_request, not_found
from app.core.rbac import Permission
from app.core.workflow.actions import WORKFLOW_DEFINITIONS, action_registry
from app.core.workflow.engine import WorkflowRunner
from app.dependencies import CurrentUser, DBSession, require
from app.models.workflow import WorkflowInstance

router = APIRouter(prefix="/workflows", tags=["Workflows"])


class WorkflowInstanceResponse(BaseModel):
    id: uuid.UUID
    workflow_name: str
    status: str
    current_step: str | None
    context: dict | None
    error: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/instances",
    response_model=list[WorkflowInstanceResponse],
    dependencies=[Depends(require(Permission.WORKFLOW_MANAGE))],
)
def list_instances(
    current_user: CurrentUser,
    db: DBSession,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Most recent workflow instances for the caller's tenant."""
    stmt = select(WorkflowInstance).where(WorkflowInstance.tenant_id == current_user.tenant_id)
    if status:
        stmt = stmt.where(WorkflowInstance.status == status)
    stmt = stmt.order_by(WorkflowInstance.created_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.post(
    "/instances/{instance_id}/retry",
    response_model=WorkflowInstanceResponse,
    dependencies=[Depends(require(Permission.WORKFLOW_MANAGE))],
)
def retry_instance(instance_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    """Re-run a failed workflow instance against its own persisted context."""
    instance = db.scalar(
        select(WorkflowInstance).where(
            WorkflowInstance.id == instance_id,
            WorkflowInstance.tenant_id == current_user.tenant_id,
        )
    )
    if instance is None:
        raise not_found("WorkflowInstance", str(instance_id))

    build_definition = WORKFLOW_DEFINITIONS.get(instance.workflow_name)
    if build_definition is None:
        raise bad_request(f"Unknown workflow definition: {instance.workflow_name}")

    try:
        WorkflowRunner(action_registry).retry(db, instance, build_definition())
    except ValueError as exc:
        raise bad_request(str(exc))

    db.commit()
    return instance
