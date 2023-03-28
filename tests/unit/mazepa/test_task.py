from __future__ import annotations

import time

import attrs

from zetta_utils.mazepa import (
    Task,
    TaskableOperation,
    TaskStatus,
    TransientErrorCondition,
    taskable_operation,
    taskable_operation_cls,
)


def test_make_taskable_operation_cls() -> None:
    @taskable_operation_cls(operation_name="OpDummyClass1")
    @attrs.mutable
    class DummyTaskCls:
        def __call__(self) -> str:
            return "result"

    @taskable_operation_cls
    @attrs.mutable
    class DummyTaskCls2:
        def __call__(self) -> str:
            return "result"

    obj: TaskableOperation[[], str] = DummyTaskCls()
    obj = DummyTaskCls()
    obj2 = DummyTaskCls2()

    assert isinstance(obj, TaskableOperation)
    assert isinstance(obj2, TaskableOperation)
    task = obj.make_task()
    task2 = obj2.make_task()
    assert isinstance(task, Task)
    assert isinstance(task2, Task)
    outcome = obj()
    assert outcome == "result"
    assert task.operation_name == "OpDummyClass1"


def test_make_taskable_operation() -> None:
    @taskable_operation(operation_name="OpDummy")
    def dummy_task_fn():
        pass

    assert isinstance(dummy_task_fn, TaskableOperation)
    task = dummy_task_fn.make_task()
    assert isinstance(task, Task)
    assert task.operation_name == "OpDummy"


def test_task_runtime_limit() -> None:
    @taskable_operation(runtime_limit_sec=0.1)
    def dummy_task_fn():
        time.sleep(0.3)

    assert isinstance(dummy_task_fn, TaskableOperation)
    task = dummy_task_fn.make_task()
    assert isinstance(task, Task)
    outcome = task(debug=False)
    assert isinstance(outcome.exception, TimeoutError)


def test_transient_error_condition() -> None:
    @taskable_operation(
        transient_error_conditions=(TransientErrorCondition(ValueError, "No More"),)
    )
    def dummy_task_fn(transient: bool):
        if transient:
            raise ValueError("No More")
        raise ValueError("Yes More")

    transient_task = dummy_task_fn.make_task(transient=True)
    transient_task()
    assert transient_task.status == TaskStatus.TRANSIENT_ERROR
    nontransient_task = dummy_task_fn.make_task(transient=False)
    nontransient_task()
    assert nontransient_task.status == TaskStatus.FAILED
