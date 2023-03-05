from __future__ import annotations

from collections.abc import Sequence as AbcSequence
from copy import deepcopy
from os import path
from typing import Any, Callable, Generic, Literal, Sequence, TypeVar, Union

import attrs
from torch import Tensor
from typing_extensions import ParamSpec

from zetta_utils import builder, log, mazepa
from zetta_utils.geometry import BBox3D, Vec3D
from zetta_utils.layer.volumetric import VolumetricBasedLayerProtocol, VolumetricIndex
from zetta_utils.typing import ensure_seq_of_seq

from ..operation_protocols import VolumetricOpProtocol
from .volumetric_apply_flow import VolumetricApplyFlowSchema
from .volumetric_callable_operation import VolumetricCallableOperation

logger = log.get_logger("zetta_utils")

IndexT = TypeVar("IndexT")
P = ParamSpec("P")
R_co = TypeVar("R_co", covariant=True)
T = TypeVar("T")


@mazepa.taskable_operation_cls
@attrs.mutable
class DelegatedSubchunkedOperation(Generic[P]):
    """
    An operation that delegates to a FlowSchema.
    """

    flow_schema: VolumetricApplyFlowSchema[P, None]

    def get_input_resolution(self, dst_resolution: Vec3D) -> Vec3D:  # pylint: disable=no-self-use
        return dst_resolution

    def __call__(
        self,
        idx: VolumetricIndex,
        dst: VolumetricBasedLayerProtocol,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        mazepa.Executor(do_dryrun_estimation=False, show_progress=False)(
            self.flow_schema(idx, dst, *args, **kwargs)
        )


@builder.register("build_subchunkable_apply_flow")
def build_subchunkable_apply_flow(  # pylint: disable=keyword-arg-before-vararg, too-many-locals, too-many-branches
    dst: VolumetricBasedLayerProtocol,
    dst_resolution: Sequence[float],
    processing_chunk_sizes: Sequence[Sequence[int]],
    processing_crop_pads: Sequence[int] | Sequence[Sequence[int]] = (0, 0, 0),
    processing_blend_pads: Sequence[int] | Sequence[Sequence[int]] = (0, 0, 0),
    processing_blend_modes: Union[
        Literal["linear", "quadratic"], Sequence[Literal["linear", "quadratic"]]
    ] = "linear",
    roi_crop_pad: Sequence[int] = (0, 0, 0),
    level_intermediaries_dirs: Sequence[str | None] | None = None,
    start_coord: Sequence[int] | None = None,
    end_coord: Sequence[int] | None = None,
    coord_resolution: Sequence | None = None,
    bbox: BBox3D | None = None,
    fn: Callable[P, Tensor] | None = None,
    op: VolumetricOpProtocol[P, None, Any] | None = None,
    max_reduction_chunk_sizes: Sequence[int] | Sequence[Sequence[int]] | None = None,
    allow_cache_up_to_level: int = 0,
    *args: P.args,
    **kwargs: P.kwargs,
) -> mazepa.Flow:
    """
    Performs basic argument error checking, expands singletons to lists, converts to Vec3D,
    and delegates too the business logic function `_build_subchankable_apply_flow`
    """
    if bbox is None:
        if start_coord is None or end_coord is None or coord_resolution is None:
            raise ValueError(
                "`bbox` was not supplied, so `start_coord`, end_coord`, and"
                " `coord_resolution` has to be specified."
            )
        bbox_ = BBox3D.from_coords(
            start_coord=start_coord, end_coord=end_coord, resolution=coord_resolution
        )
    else:
        if start_coord is not None or end_coord is not None or coord_resolution is not None:
            raise ValueError(
                "`bbox` was supplied, so `start_coord`, end_coord`, and"
                " `coord_resolution` cannot be specified."
            )
        bbox_ = bbox

    if fn is not None and op is not None:
        raise ValueError("Cannot take both `fn` and `op`; please choose one or the other.")
    if fn is None and op is None:
        raise ValueError("Need exactly one of `fn` and `op`; received neither.")

    if op is not None:
        assert fn is None
        op_ = op
    else:
        assert fn is not None
        op_ = VolumetricCallableOperation[P](fn)

    num_levels = len(processing_chunk_sizes)

    # Explicit checking here for prettier user eror
    seq_of_seq_arguments = {
        "max_reduction_chunk_sizes": max_reduction_chunk_sizes,
        "processing_crop_pads": processing_crop_pads,
        "processing_blend_pads": processing_blend_pads,
        "processing_blend_modes": processing_blend_modes,
    }
    for k, v in seq_of_seq_arguments.items():
        if (
            not isinstance(v, str)
            and isinstance(v, AbcSequence)
            and len(v) > 0
            and isinstance(v[0], AbcSequence)
        ):
            if not len(v) == num_levels:
                raise ValueError(
                    f"If provided as a nested sequence, length of `{k}` must be equal to "
                    f"the number of subchunking levels, which is {num_levels} (infered from "
                    f"`processing_chunk_sizes`). Got `len({k}) == {len(v)}`"
                )

    if level_intermediaries_dirs is not None and len(level_intermediaries_dirs) != num_levels:
        raise ValueError(
            f"`len(level_intermediaries_dirs)` != {num_levels}, where {num_levels} is the "
            "number of subchunking levels infered from `processing_chunk_sizes`"
        )

    if max_reduction_chunk_sizes is None:
        max_reduction_chunk_sizes_ = processing_chunk_sizes
    else:
        max_reduction_chunk_sizes_ = ensure_seq_of_seq(max_reduction_chunk_sizes, num_levels)

    if level_intermediaries_dirs is not None:
        level_intermediaries_dirs_ = level_intermediaries_dirs
    else:
        level_intermediaries_dirs_ = [None for _ in range(num_levels)]

    processing_blend_pads_ = ensure_seq_of_seq(processing_blend_pads, num_levels)
    processing_crop_pads_ = ensure_seq_of_seq(processing_crop_pads, num_levels)
    processing_blend_modes_ = ensure_seq_of_seq(processing_blend_modes, num_levels)

    assert len(args) == 0
    return _build_subchunkable_apply_flow(
        dst=dst,
        dst_resolution=Vec3D(*dst_resolution),
        level_intermediaries_dirs=level_intermediaries_dirs_,
        processing_chunk_sizes=[Vec3D(*v) for v in processing_chunk_sizes],
        processing_crop_pads=[Vec3D(*v) for v in processing_crop_pads_],
        processing_blend_pads=[Vec3D(*v) for v in processing_blend_pads_],
        processing_blend_modes=processing_blend_modes_,  # type: ignore # Literal gets lost
        roi_crop_pad=Vec3D(*roi_crop_pad),
        allow_cache_up_to_level=allow_cache_up_to_level,
        max_reduction_chunk_sizes=[Vec3D(*v) for v in max_reduction_chunk_sizes_],
        op=op_,
        bbox=bbox_,
        **kwargs,
    )


def _path_join_if_not_none(base: str | None, suffix: str) -> str | None:
    if base is None:
        return None
    else:
        return path.join(base, suffix)  # f"chunks_level_{level}"


def _build_subchunkable_apply_flow(  # pylint: disable=keyword-arg-before-vararg, line-too-long, too-many-locals, too-many-branches, too-many-statements
    dst: VolumetricBasedLayerProtocol,
    dst_resolution: Vec3D,
    level_intermediaries_dirs: Sequence[str | None],
    processing_chunk_sizes: Sequence[Vec3D[int]],
    processing_crop_pads: Sequence[Vec3D[int]],
    processing_blend_pads: Sequence[Vec3D[int]],
    processing_blend_modes: Sequence[Literal["linear", "quadratic"]],
    roi_crop_pad: Vec3D[int],
    max_reduction_chunk_sizes: Sequence[Vec3D[int]],
    allow_cache_up_to_level: int,
    bbox: BBox3D,
    op: VolumetricOpProtocol[P, None, Any],
    *args: P.args,
    **kwargs: P.kwargs,
) -> mazepa.Flow:
    idx = VolumetricIndex(resolution=dst_resolution, bbox=bbox)
    level0_op = op.with_added_crop_pad(processing_crop_pads[-1])

    num_levels = len(processing_chunk_sizes)

    """
    Check that the sizes are correct. Note that the the order has to be reversed for indexing.
    At level l (where processing_chunk_sizes[num_levels] = idx.stop-idx.start):
    processing_chunk_sizes[l+1] + 2*processing_crop_pads[l+1] + 2*processing_blend_pads[l+1] % processing_chunk_sizes[l] == 0
    processing_blend_pads[l] * 2 <= processing_chunk_sizes[l]
    """
    logger.info("Checking the arguments given.")
    for level in range(num_levels - 1, -1, -1):
        i = num_levels - level - 1
        if i == 0:
            processing_chunk_size_higher = idx.shape
            processing_blend_pad_higher = Vec3D[int](0, 0, 0)
            processing_crop_pad_higher = roi_crop_pad
        else:
            processing_chunk_size_higher = processing_chunk_sizes[i - 1]
            processing_blend_pad_higher = processing_blend_pads[i - 1]
            processing_crop_pad_higher = processing_crop_pads[i - 1]
        processing_chunk_size = processing_chunk_sizes[i]
        processing_blend_pad = processing_blend_pads[i]

        processing_region = (
            processing_chunk_size_higher
            + 2 * processing_crop_pad_higher
            + 2 * processing_blend_pad_higher
        )

        if processing_region % processing_chunk_size != Vec3D[int](0, 0, 0):
            n_region_chunks = processing_region / processing_chunk_size
            n_region_chunks_rounded = Vec3D[int](*(max(1, round(e)) for e in n_region_chunks))
            if processing_region % n_region_chunks_rounded == Vec3D(0, 0, 0):
                rec_processing_chunk_size = (processing_region / n_region_chunks_rounded).int()
                rec_str = f"Recommendation for `processing_chunk_size[level]`: {rec_processing_chunk_size}"
            else:
                rec_str = (
                    "Unable to recommend processing_chunk_size[level]: try using a more divisible"
                    " `processing_crop_pad[level+1]` and/or `processing_blend_pad[level+1]`."
                )
            error_str = (
                "At each level (where the 0-th level is the smallest), the"
                " `processing_chunk_size[level+1]` + 2*`processing_crop_pad[level+1]` + 2*`processing_blend_pad[level+1]` must be"
                f" evenly divisible by the `processing_chunk_size[level]`.\n\nAt level {level}, received:\n"
                f"`processing_chunk_size[level+1]`:\t\t\t\t{processing_chunk_size_higher}\n"
                f"`processing_crop_pad[level+1]` (`roi_crop_pad` for the top level):\t{processing_crop_pad_higher}\n"
                f"`processing_blend_pad[level+1]`:\t\t\t\t{processing_blend_pad_higher}\n"
                f"Size of the region to be processed for the level: {processing_region}\n"
                f"Which must be (but is not) divisible by: `processing_chunk_size[level]`: {processing_chunk_size}\n\n"
            )
            raise ValueError(error_str + rec_str)
        if not processing_blend_pad * 2 <= processing_chunk_size:
            raise ValueError(
                "At each level (where the 0-th level is the smallest), the `processing_blend_pad[level]` must"
                f" be at most half of the `processing_chunk_size[level]`. At level {level}, received:\n"
                f"`processing_blend_pad[level]`: {processing_blend_pad}\n"
                f"`processing_chunk_size[level]`: {processing_chunk_size}"
            )

    """
    Append roi_crop pads into one list
    """
    roi_crop_pads = [roi_crop_pad] + list(processing_crop_pads[:-1])
    """
    Check for no checkerboarding
    """
    for i in range(0, num_levels - 1):
        if roi_crop_pads[i] == Vec3D[int](0, 0, 0) and processing_blend_pads[i] == Vec3D[int](
            0, 0, 0
        ):
            logger.info(
                f"Level {num_levels - i - 1}: Chunks will not be checkerboarded since `processing_crop_pad[level+1]`"
                f" (`roi_crop_pad` for the top level) and `processing_blend_pad[level]` are both {Vec3D[int](0, 0, 0)}."
            )
    if processing_blend_pads[num_levels - 1] == Vec3D[int](0, 0, 0):
        logger.info(
            f"Level 0: Chunks will not be checkerboarded since `processing_blend_pad[level]` is {Vec3D[int](0, 0, 0)}."
        )
    if roi_crop_pads[0] == Vec3D[int](0, 0, 0) and processing_blend_pads[0] == Vec3D[int](0, 0, 0):
        logger.info(
            "Since checkerboarding is skipped at the top level, the roi is required to be chunk-aligned."
        )
        dst = attrs.evolve(
            deepcopy(dst), backend=dst.backend.with_changes(enforce_chunk_aligned_writes=True)
        )
    else:
        dst = attrs.evolve(
            deepcopy(dst), backend=dst.backend.with_changes(enforce_chunk_aligned_writes=False)
        )

    """
    Basic building blocks where the work gets done, at the very bottom
    """
    flow_schema: VolumetricApplyFlowSchema = VolumetricApplyFlowSchema(
        op=level0_op,
        processing_chunk_size=processing_chunk_sizes[-1],
        max_reduction_chunk_size=max_reduction_chunk_sizes[-1],
        dst_resolution=dst_resolution,
        roi_crop_pad=roi_crop_pads[-1],
        processing_blend_pad=processing_blend_pads[-1],
        processing_blend_mode=processing_blend_modes[-1],
        intermediaries_dir=_path_join_if_not_none(level_intermediaries_dirs[-1], "chunks_level_0"),
        allow_cache=(allow_cache_up_to_level >= 1),
        clear_cache_on_return=(allow_cache_up_to_level == 1),
    )

    """
    Iteratively build the hierarchy of schemas
    """
    for level in range(1, num_levels):
        flow_schema = VolumetricApplyFlowSchema(
            op=DelegatedSubchunkedOperation(  # type:ignore #readability over typing here
                flow_schema,
            ),
            processing_chunk_size=processing_chunk_sizes[-level - 1],
            max_reduction_chunk_size=max_reduction_chunk_sizes[-level - 1],
            dst_resolution=dst_resolution,
            roi_crop_pad=roi_crop_pads[-level - 1],
            processing_blend_pad=processing_blend_pads[-level - 1],
            processing_blend_mode=processing_blend_modes[-level - 1],
            intermediaries_dir=_path_join_if_not_none(
                level_intermediaries_dirs[-level - 1], f"chunks_level_{level}"
            ),
            allow_cache=(allow_cache_up_to_level >= level + 1),
            clear_cache_on_return=(allow_cache_up_to_level == level + 1),
        )

    return flow_schema(idx, dst, *args, **kwargs)
