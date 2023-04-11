# pylint: disable=global-statement,redefined-outer-name,unused-argument
from __future__ import annotations

import functools
from contextlib import AbstractContextManager
from typing import Any

import pytest

from zetta_utils.mazepa import (
    Dependency,
    InMemoryExecutionState,
    LocalExecutionQueue,
    TaskStatus,
    concurrent_flow,
    execute,
    flow_schema,
    taskable_operation,
)
from zetta_utils.mazepa.remote_execution_queues import SQSExecutionQueue

TASK_COUNT = 0


@pytest.fixture
def reset_task_count():
    global TASK_COUNT
    TASK_COUNT = 0


@taskable_operation
def dummy_task(argument: str) -> Any:
    global TASK_COUNT
    TASK_COUNT += 1
    return f"return-for-{argument}"


@flow_schema
def dummy_flow(argument: str):
    task1 = dummy_task.make_task(argument=f"{argument}-x1")
    yield task1
    yield Dependency(task1)
    assert task1.status == TaskStatus.SUCCEEDED
    assert task1.outcome is not None
    assert task1.outcome.return_value == f"return-for-{argument}-x1"
    task2 = dummy_task.make_task(argument=f"{argument}-x2")
    yield task2


@flow_schema
def dummy_flow_without_outcome(argument: str):
    task1 = dummy_task.make_task(argument=f"{argument}-x1")
    yield task1
    yield Dependency(task1)
    task2 = dummy_task.make_task(argument=f"{argument}-x2")
    yield task2


@flow_schema
def dummy_flow2():
    task1 = dummy_task.make_task(argument="x1")
    yield task1
    yield Dependency(task1)
    task2 = dummy_task.make_task(argument="x2")
    yield task2


@flow_schema
def empty_flow():
    yield []


def test_local_execution_defaults(reset_task_count):
    execute(
        concurrent_flow(
            [
                dummy_flow("f1"),
                dummy_flow("f2"),
                dummy_flow("f3"),
            ]
        ),
        batch_gap_sleep_sec=0,
        max_batch_len=2,
        do_dryrun_estimation=False,
    )
    assert TASK_COUNT == 6


def test_local_execution_one_flow(reset_task_count):
    execute(
        dummy_flow("f1"),
        batch_gap_sleep_sec=0,
        max_batch_len=1,
        do_dryrun_estimation=False,
    )
    assert TASK_COUNT == 2


def test_local_execution_one_callable(reset_task_count) -> None:
    execute(
        functools.partial(dummy_task, argument="x0"),
        batch_gap_sleep_sec=0,
        max_batch_len=1,
        do_dryrun_estimation=False,
    )
    assert TASK_COUNT == 1


def test_local_execution_one_task(reset_task_count) -> None:
    execute(
        dummy_task.make_task(argument="x0"),
        batch_gap_sleep_sec=0,
        do_dryrun_estimation=False,
        max_batch_len=1,
    )
    assert TASK_COUNT == 1


def test_local_execution_with_dryrun(reset_task_count):
    execute(dummy_flow2(), max_batch_len=1, do_dryrun_estimation=True, show_progress=False)
    assert TASK_COUNT == 2


def make_mock_ctx_mngr(mocker) -> AbstractContextManager[Any]:
    mngr_m = mocker.NonCallableMock(spec=AbstractContextManager)
    mngr_m.__enter__ = mocker.MagicMock()
    mngr_m.__exit__ = mocker.MagicMock()
    return mngr_m


def test_local_execution_state(reset_task_count):
    execute(
        InMemoryExecutionState(
            [
                dummy_flow("f1"),
                dummy_flow("f2"),
                dummy_flow("f3"),
            ]
        ),
        execution_id="yo",
        batch_gap_sleep_sec=0,
        max_batch_len=2,
        do_dryrun_estimation=False,
    )
    assert TASK_COUNT == 6


def test_local_execution_state_queue(reset_task_count):
    execute(
        InMemoryExecutionState(
            [
                dummy_flow("f1"),
                dummy_flow("f2"),
                dummy_flow("f3"),
            ]
        ),
        exec_queue=LocalExecutionQueue(debug=True),
        batch_gap_sleep_sec=0,
        do_dryrun_estimation=False,
        max_batch_len=2,
    )
    assert TASK_COUNT == 6


def test_local_no_sleep(mocker):
    sleep_m = mocker.patch("time.sleep")
    execute(
        empty_flow(),
        batch_gap_sleep_sec=10,
        max_batch_len=2,
        do_dryrun_estimation=False,
    )
    sleep_m.assert_not_called()


def test_non_local_sleep(mocker):
    sleep_m = mocker.patch("time.sleep")
    queue_m = mocker.MagicMock(spec=SQSExecutionQueue)
    execute(
        empty_flow(),
        batch_gap_sleep_sec=10,
        max_batch_len=2,
        do_dryrun_estimation=False,
        exec_queue=queue_m,
    )
    sleep_m.assert_called_once()


def test_local_execution_backup_write(reset_task_count, mocker):
    record_execution_checkpoint_m = mocker.patch(
        "zetta_utils.mazepa.execution.record_execution_checkpoint"
    )

    execute(
        concurrent_flow(
            [
                dummy_flow("f1"),
                dummy_flow("f2"),
                dummy_flow("f3"),
            ]
        ),
        batch_gap_sleep_sec=0,
        max_batch_len=2,
        do_dryrun_estimation=False,
        checkpoint_interval_sec=0.0,
    )
    record_execution_checkpoint_m.assert_called()


def test_local_execution_backup_read(reset_task_count):
    execute(
        concurrent_flow(
            [
                dummy_flow_without_outcome("f1"),
                dummy_flow_without_outcome("f2"),
                dummy_flow_without_outcome("f3"),
            ]
        ),
        batch_gap_sleep_sec=0,
        max_batch_len=2,
        do_dryrun_estimation=False,
        checkpoint="tests/assets/reference/task_checkpoint.zstd",
    )
