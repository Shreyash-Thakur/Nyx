"""Workflow engine (ADR-0003): right-sized, declarative, durable.

A workflow is an ordered list of steps; each step invokes a registered action
(the only extensibility point) and may carry a restricted condition. Runs are
persisted as WorkflowInstance rows so they are inspectable and durable.
"""
import uuid
from decimal import Decimal

from app.core.workflow.engine import (
    ActionRegistry,
    WorkflowDefinition,
    WorkflowRunner,
    WorkflowStep,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.reconciliation import ReconciliationRecord
from app.models.workflow import WorkflowInstance


def test_runner_executes_steps_and_persists_instance(db):
    reg = ActionRegistry()

    @reg.register("append")
    def append(params, ctx, db):
        return {"trail": ctx.get("trail", []) + [params["mark"]]}

    definition = WorkflowDefinition(
        name="demo",
        steps=[
            WorkflowStep(id="s1", action="append", params={"mark": "a"}),
            WorkflowStep(id="s2", action="append", params={"mark": "b"}),
        ],
    )

    instance = WorkflowRunner(reg).run(db, definition)
    db.commit()

    assert instance.status == "completed"
    assert instance.context["trail"] == ["a", "b"]
    assert db.get(WorkflowInstance, instance.id) is not None


def test_step_skipped_when_condition_not_met(db):
    reg = ActionRegistry()
    ran = []
    reg.register("note")(lambda params, ctx, db: ran.append(params["mark"]) or {})

    definition = WorkflowDefinition(
        name="conditional",
        steps=[
            WorkflowStep(id="s1", action="note", params={"mark": "x"},
                         when={"field": "status", "equals": "extracted"}),
        ],
    )

    instance = WorkflowRunner(reg).run(db, definition, context={"status": "uploaded"})

    assert ran == []  # condition false -> action not invoked
    assert instance.status == "completed"


def test_failed_action_marks_instance_failed(db):
    reg = ActionRegistry()

    @reg.register("boom")
    def boom(params, ctx, db):
        raise RuntimeError("kaboom")

    definition = WorkflowDefinition(name="failing", steps=[WorkflowStep(id="s1", action="boom")])

    instance = WorkflowRunner(reg).run(db, definition)
    db.commit()

    assert instance.status == "failed"
    assert "kaboom" in (instance.error or "")


def test_retry_reruns_a_failed_instance(db):
    reg = ActionRegistry()
    calls = []

    @reg.register("flaky")
    def flaky(params, ctx, db):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient")
        return {"ok": True}

    definition = WorkflowDefinition(name="flaky_wf", steps=[WorkflowStep(id="s1", action="flaky")])
    runner = WorkflowRunner(reg)

    instance = runner.run(db, definition)
    db.commit()
    assert instance.status == "failed"

    runner.retry(db, instance, definition)
    db.commit()

    assert instance.status == "completed"
    assert instance.context["ok"] is True
    assert len(calls) == 2


def test_retry_rejects_non_failed_instance(db):
    reg = ActionRegistry()
    reg.register("noop")(lambda params, ctx, db: {})
    definition = WorkflowDefinition(name="noop_wf", steps=[WorkflowStep(id="s1", action="noop")])
    runner = WorkflowRunner(reg)

    instance = runner.run(db, definition)
    db.commit()
    assert instance.status == "completed"

    try:
        runner.retry(db, instance, definition)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_reconcile_action_runs_against_an_invoice(db, admin_user):
    from app.core.workflow.actions import action_registry, build_invoice_post_extraction

    inv = Invoice(
        id=uuid.uuid4(),
        original_filename="f.pdf",
        storage_path="x",
        content_type="application/pdf",
        status=InvoiceStatus.EXTRACTED,
        total_amount=Decimal("250.00"),
        uploaded_by=admin_user.id,
        tenant_id=admin_user.tenant_id,
    )
    db.add(inv)
    db.commit()

    definition = build_invoice_post_extraction()
    instance = WorkflowRunner(action_registry).run(
        db,
        definition,
        context={"invoice_id": str(inv.id), "status": inv.status.value},
        tenant_id=inv.tenant_id,
    )
    db.commit()

    assert instance.status == "completed"
    records = db.query(ReconciliationRecord).filter(ReconciliationRecord.invoice_id == inv.id).all()
    assert len(records) == 1
