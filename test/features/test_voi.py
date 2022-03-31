import pytest
import numpy as np
from siibra.features.voi import VolumeOfInterestQuery, VolumeOfInterest


query = VolumeOfInterestQuery()

@pytest.mark.parametrize('feature', query.features)
def test_voi_features(feature: VolumeOfInterest):
    feature.to_model()

def test_pli_volume_transform():
    feat = [f for f in query.features if "3D-PLI" in f.name]
    assert len(feat) == 1, f"expecting 1 PLI data" #may need to fix in future
    feat = feat[0]
    assert all(
        (np.array(vol.detail.get('neuroglancer/precomputed').get('transform')) == vol.transform_nm).all()
        for vol in feat.volumes
    ), f"expecting transform in neuroglance/precomputed be adopted as transform_nm, but was not."
