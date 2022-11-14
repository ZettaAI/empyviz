"""Type conversion functions."""
from __future__ import annotations

import numpy as np
import numpy.typing as npt
import torch
from typeguard import typechecked

import zetta_utils as zu
from zetta_utils.tensor_typing import Tensor, TensorTypeVar


@typechecked
def to_np(data: Tensor) -> npt.NDArray:
    """Convert the given tensor to :class:`numpy.ndarray`.

    :param data: Input tensor_ops.
    :return: Input tensor in :class:`np.ndarray` format.

    """
    if isinstance(data, torch.Tensor):
        result = data.cpu().detach().numpy()
    else:
        assert isinstance(data, np.ndarray)
        result = data

    return result


@typechecked
def to_torch(data: Tensor, device: torch.types.Device = "cpu") -> torch.Tensor:
    """Convert the given tensor to :class:`torch.Tensor`.

    :param data: Input tensor_ops.
    :param device: Device name on which the torch tensor will reside.
    :return: Input tensor in :class:`torch.Tensor` format.

    """
    if isinstance(data, torch.Tensor):
        result = data
    else:
        assert isinstance(data, np.ndarray)
        result = torch.from_numpy(data).to(device)

    return result


@typechecked
def astype(data: Tensor, reference: TensorTypeVar) -> TensorTypeVar:
    """Convert the given tensor to :class:`np.ndarray` or :class:`torch.Tensor`
    depending on the type of reference tensor_ops.

    :param data: Input tensor_ops.
    :param reference: Reference type tensor_ops.
    :return: Input tensor converted to the reference type.

    """
    if isinstance(reference, torch.Tensor):
        result = zu.tensor_ops.convert.to_torch(data)  # type: TensorTypeVar
    elif isinstance(reference, np.ndarray):
        result = zu.tensor_ops.convert.to_np(data)
    return result
