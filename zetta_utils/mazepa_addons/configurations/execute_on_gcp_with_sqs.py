from __future__ import annotations

import copy
from contextlib import AbstractContextManager, ExitStack
from typing import Dict, Iterable, Optional, Union

from zetta_utils import builder, log, mazepa
from zetta_utils.mazepa_addons import resource_allocation

logger = log.get_logger("zetta_utils")


def get_gcp_with_sqs_config(
    execution_id: str,
    worker_lease_sec: int,
    worker_image: str,
    worker_replicas: int,
    worker_resources: Dict[str, int | float | str],
    worker_labels: Optional[Dict[str, str]],
    ctx_managers: list[AbstractContextManager],
) -> tuple[mazepa.ExecutionQueue, list[AbstractContextManager]]:
    work_queue_name = f"zzz-{execution_id}-work"
    ctx_managers.append(resource_allocation.aws_sqs.sqs_queue_ctx_mngr(work_queue_name))
    outcome_queue_name = f"zzz-{execution_id}-outcome"
    ctx_managers.append(resource_allocation.aws_sqs.sqs_queue_ctx_mngr(outcome_queue_name))
    exec_queue_spec = {
        "@type": "mazepa.SQSExecutionQueue",
        "name": work_queue_name,
        "outcome_queue_name": outcome_queue_name,
        "pull_lease_sec": worker_lease_sec,
    }
    exec_queue = builder.build(exec_queue_spec)

    ctx_managers.append(
        resource_allocation.gcp_k8s.worker_k8s_deployment_ctx_mngr(
            execution_id=execution_id,
            image=worker_image,
            queue=exec_queue_spec,
            replicas=worker_replicas,
            labels=worker_labels,
            resources=worker_resources,
            share_envs=[
                "GRAFANA_CLOUD_ACCESS_KEY",
                "ZETTA_USER",
                "ZETTA_PROJECT",
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "WANDB_API_KEY",
            ],
        )
    )
    return exec_queue, ctx_managers


@builder.register("mazepa.execute_on_gcp_with_sqs")
def execute_on_gcp_with_sqs(  # pylint: disable=too-many-locals
    target: Union[mazepa.Flow, mazepa.ExecutionState],
    worker_lease_sec: int,
    worker_image: str,
    worker_replicas: int,
    worker_resources: Dict[str, int | float | str],
    worker_labels: Optional[Dict[str, str]] = None,
    max_task_retry: int = 1,
    max_batch_len: int = 10000,
    batch_gap_sleep_sec: float = 4.0,
    extra_ctx_managers: Iterable[AbstractContextManager] = (),
    local_test: bool = False,
    do_dryrun_estimation: bool = False,
):
    execution_id = mazepa.id_generation.get_unique_id(
        prefix="exec", slug_len=4, add_uuid=False, max_len=50
    )

    ctx_managers = copy.copy(list(extra_ctx_managers))
    if local_test:
        exec_queue: mazepa.ExecutionQueue = mazepa.LocalExecutionQueue()
    else:
        exec_queue, ctx_managers = get_gcp_with_sqs_config(
            execution_id=execution_id,
            worker_image=worker_image,
            worker_labels=worker_labels,
            worker_replicas=worker_replicas,
            worker_resources=worker_resources,
            worker_lease_sec=worker_lease_sec,
            ctx_managers=ctx_managers,
        )

    with ExitStack() as stack:
        for mngr in ctx_managers:
            stack.enter_context(mngr)

        mazepa.execute(
            target=target,
            exec_queue=exec_queue,
            max_batch_len=max_batch_len,
            batch_gap_sleep_sec=batch_gap_sleep_sec,
            max_task_retry=max_task_retry,
            do_dryrun_estimation=do_dryrun_estimation,
        )
