import pytorch_lightning as pl
from zetta_utils import training


def test_default_trainer():
    result = training.lightning.trainers.build_default_trainer(
        experiment_name="unit_test",
        experiment_version="x0",
    )
    assert isinstance(result, pl.Trainer)
