"""Workflow engine — right-sized, owned, replaceable (ADR-0003).

A workflow is an ordered list of steps. Each step invokes a registered *action*
with params and an optional *condition*; the action registry is the only
extensibility point, and conditions are a restricted data structure (no
function calls / no eval) so the surface stays small and auditable.

Runs are recorded as ``WorkflowInstance`` rows (durable, inspectable). Parking,
retries and async resumption are deliberately out of scope for this first
increment; a YAML loader is a later layer over the same dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.tenancy import DEFAULT_TENANT_ID

logger = get_logger(__name__)

# An action receives (params, context, db) and returns a dict merged into the
# workflow context (or None).
Action = Callable[[dict, dict, Session], dict | None]


@dataclass
class WorkflowStep:
    id: str
    action: str
    params: dict = field(default_factory=dict)
    when: dict | None = None


@dataclass
class WorkflowDefinition:
    name: str
    steps: list[WorkflowStep]


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}

    def register(self, name: str):
        def deco(fn: Action) -> Action:
            self._actions[name] = fn
            return fn

        return deco

    def get(self, name: str) -> Action:
        if name not in self._actions:
            raise KeyError(f"Unknown workflow action: {name!r}")
        return self._actions[name]


def condition_met(when: dict | None, context: dict) -> bool:
    """Evaluate a restricted condition against the context.

    Supported, mutually-exclusive operators on a single ``field``:
    ``equals``, ``not_equals``, ``in``. No condition means always-run.
    """
    if not when:
        return True
    actual = context.get(when["field"])
    if "equals" in when:
        return actual == when["equals"]
    if "not_equals" in when:
        return actual != when["not_equals"]
    if "in" in when:
        return actual in when["in"]
    return True


class WorkflowRunner:
    def __init__(self, registry: ActionRegistry) -> None:
        self.registry = registry

    def run(
        self,
        db: Session,
        definition: WorkflowDefinition,
        *,
        context: dict | None = None,
        tenant_id=DEFAULT_TENANT_ID,
        actor_id=None,
    ):
        from app.models.workflow import WorkflowInstance

        ctx: dict = dict(context or {})
        instance = WorkflowInstance(
            tenant_id=tenant_id,
            workflow_name=definition.name,
            status="running",
            # Distinct copy: the working ``ctx`` must not alias the ORM-tracked
            # value, or in-place updates would hide the final change from
            # SQLAlchemy's plain-JSON dirty detection.
            context=dict(ctx),
            actor_id=actor_id,
        )
        db.add(instance)
        db.flush()

        self._execute(db, instance, definition, ctx)
        return instance

    def retry(self, db: Session, instance, definition: WorkflowDefinition):
        """Re-run a failed instance's steps against its own persisted context.

        The engine has no per-step resume cursor (deliberately deferred, see
        module docstring), so this replays every step from the top rather
        than continuing mid-step. That is safe exactly because every
        registered action is expected to be idempotent -- the same contract
        the engine already relies on for the primary run.
        """
        if instance.status != "failed":
            raise ValueError(f"Cannot retry a workflow instance in status {instance.status!r}")

        ctx: dict = dict(instance.context or {})
        instance.status = "running"
        instance.error = None
        self._execute(db, instance, definition, ctx)
        return instance

    def _execute(self, db: Session, instance, definition: WorkflowDefinition, ctx: dict) -> None:
        try:
            for step in definition.steps:
                if not condition_met(step.when, ctx):
                    logger.info("workflow_step_skipped", workflow=definition.name, step=step.id)
                    continue
                instance.current_step = step.id
                action = self.registry.get(step.action)
                result = action(step.params or {}, ctx, db) or {}
                ctx.update(result)
            instance.status = "completed"
        except Exception as exc:
            instance.status = "failed"
            instance.error = str(exc)
            logger.error(
                "workflow_failed",
                workflow=definition.name,
                step=instance.current_step,
                error=str(exc),
            )

        # Reassign so SQLAlchemy detects the JSON mutation.
        instance.context = dict(ctx)
        db.flush()
