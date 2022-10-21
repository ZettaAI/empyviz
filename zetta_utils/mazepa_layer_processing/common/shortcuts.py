from typing import TypeVar, Any, Callable
from typing_extensions import ParamSpec
from zetta_utils import mazepa
from zetta_utils import builder
from zetta_utils.layer import LayerIndex, IndexChunker, Layer

from . import ChunkedApplyFlow, SimpleCallableTaskFactory

IndexT = TypeVar("IndexT", bound=LayerIndex)
P = ParamSpec("P")


@builder.register("build_chunked_apply_flow")
def build_chunked_apply_flow(
    task_factory: mazepa.TaskFactory[P, Any],
    chunker: IndexChunker[IndexT],
    *args: P.args,
    **kwargs: P.kwargs,
) -> mazepa.Flow[P]:
    flow_type = ChunkedApplyFlow[IndexT, P, None](
        chunker=chunker,
        task_factory=task_factory,
    )
    flow = flow_type(*args, **kwargs)  # TODO: typing problems here.
    return flow


@builder.register("build_chunked_apply_callable_flow_type")
def build_chunked_apply_callable_flow_type(
    fn: Callable[P, Any], chunker: IndexChunker[IndexT]
) -> ChunkedApplyFlow[IndexT, P, None]:
    factory = SimpleCallableTaskFactory[P](fn=fn)
    return ChunkedApplyFlow[IndexT, P, None](
        chunker=chunker,
        task_factory=factory,  # type: ignore # depends on callable that's supplied at runtime
    )


def _write_callable(src_data):
    return src_data


@builder.register("build_chunked_write_flow")
def build_chunked_write_flow_type(
    chunker: IndexChunker[IndexT],
) -> ChunkedApplyFlow:
    return build_chunked_apply_callable_flow_type(
        fn=_write_callable,
        chunker=chunker,
    )


@builder.register("chunked_write")
def chunked_write(
    chunker: IndexChunker[IndexT],
    idx: IndexT,
    dst: Layer[Any, IndexT],
    src: Layer[Any, IndexT],
) -> mazepa.Flow:
    result = build_chunked_write_flow_type(chunker=chunker)(idx=idx, dst=dst, src=src)
    return result


"""
from zetta_utils.layer.volumetric import VolumetricIndex
@builder.register("chunked_write")
def warp(
    chunker: IndexChunker[IndexT],
    idx: VolumetricIndex,
    dst: Layer[Any, VolumetricIndex],
    src: Layer[Any, VolumetricIndex],
    field: Layer[Any, VolumetricIndex],
) -> mazepa.Flow:
    factory
    result = build_chunked_write_flow_type(chunker=chunker)(idx=idx, dst=dst, src=src)
    return result
"""
