# Copyright 2018-2021
# Institute of Neuroscience and Medicine (INM-1), Forschungszentrum Jülich GmbH

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from . import query

from ..commons import logger
from ..locations import point, pointset
from ..core import space, region
from ..retrieval import requests
from ..features import profiles, fingerprints

import numpy as np
from typing import List


class WagstylProfileLoader:

    REPO = "https://github.com/kwagstyl/cortical_layers_tutorial"
    BRANCH = "main"
    PROFILES_FILE = "data/profiles_left.npy"
    THICKNESSES_FILE = "data/thicknesses_left.npy"
    MESH_FILE = "data/gray_left_327680.surf.gii"

    _profiles = None
    _vertices = None
    _boundary_depths = None

    def __init__(self):
        if self._profiles is None:
            self.__class__._load()

    @property
    def profile_labels(self):
        return np.arange(0, 1, 1 / self._profiles.shape[1])

    @classmethod
    def _load(cls):
        # read thicknesses, in mm, and normalize by their last columsn which is the total thickness
        mesh_left = requests.HttpRequest(f"{cls.REPO}/raw/{cls.BRANCH}/{cls.MESH_FILE}").data
        T = requests.HttpRequest(f"{cls.REPO}/raw/{cls.BRANCH}/{cls.THICKNESSES_FILE}").data.T
        total = T[:, :-1].sum(1)
        valid = np.where(total > 0)[0]
        boundary_depths = np.c_[np.zeros_like(valid), (T[valid, :-1] / total[valid, None]).cumsum(1)]
        boundary_depths[:, -1] = 1

        # read profiles with valid thickenss
        req = requests.HttpRequest(
            f"{cls.REPO}/raw/{cls.BRANCH}/{cls.PROFILES_FILE}",
            msg_if_not_cached="First request to BigBrain profiles. Downloading and preprocessing the data now. This may take a little."
        )

        cls._boundary_depths = boundary_depths
        cls._vertices = mesh_left.darrays[0].data[valid, :]
        cls._profiles = req.data[valid, :]
        logger.debug(f"{cls._profiles.shape[0]} BigBrain intensity profiles.")
        assert cls._vertices.shape[0] == cls._profiles.shape[0]

    def __len__(self):
        return self._vertices.shape[0]

    def match(self, regionobj: region.Region):
        assert isinstance(regionobj, region.Region)
        logger.debug(f"Matching locations of {len(self)} BigBrain profiles to {regionobj}")

        for spaceobj in regionobj.supported_spaces:
            if not spaceobj.is_surface:
                try:
                    mask = regionobj.build_mask(space=spaceobj, maptype="labelled")
                except RuntimeError:
                    continue
                logger.info(f"Assigning {len(self)} profile locations to {regionobj} in {spaceobj}...")
                pts = pointset.PointSet(self._vertices, space="bigbrain").warp(spaceobj)
                inside = [i for i, p in enumerate(pts) if p.contained_in(mask)]
                break
        else:
            raise RuntimeError(f"Could not filter big brain profiles by {regionobj}")

        return (
            self._profiles[inside, :],
            self._boundary_depths[inside, :],
            self._vertices[inside, :]
        )


class BigBrainProfileQuery(query.LiveQuery, args=[], FeatureType=profiles.BigBrainIntensityProfile):

    def __init__(self):
        query.LiveQuery.__init__(self)

    def query(self, regionobj: region.Region, **kwargs) -> List[profiles.BigBrainIntensityProfile]:
        assert isinstance(regionobj, region.Region)
        loader = WagstylProfileLoader()

        features = []
        for subregion in regionobj.leaves:
            matched_profiles, boundary_depths, coords = loader.match(subregion)
            bbspace = space.Space.get_instance('bigbrain')
            for i, profile in enumerate(matched_profiles):
                prof = profiles.BigBrainIntensityProfile(
                    regionname=subregion.name,
                    depths=loader.profile_labels,
                    values=profile,
                    boundaries=boundary_depths[i, :],
                    location=point.Point(coords[i, :], bbspace),
                )
                assert prof.matches(subregion)  # to create an assignment result
                features.append(prof)

        return features


class BigBrainIntensityFingerprintQuery(query.LiveQuery, args=[], FeatureType=fingerprints.BigBrainIntensityFingerprint):

    def __init__(self):
        query.LiveQuery.__init__(self)

    def query(self, regionobj: region.Region, **kwargs) -> List[fingerprints.BigBrainIntensityFingerprint]:
        assert isinstance(regionobj, region.Region)
        loader = WagstylProfileLoader()

        result = []
        for subregion in regionobj.leaves:
            matched_profiles, boundary_depths, coords = loader.match(subregion)

            # compute array of layer labels for all coefficients in profiles_left
            N = matched_profiles.shape[1]
            prange = np.arange(N)
            region_labels = 7 - np.array([
                [np.array([[(prange < T) * 1] for i, T in enumerate((b * N).astype('int'))]).squeeze().sum(0)]
                for b in boundary_depths
            ]).squeeze()

            fp = fingerprints.BigBrainIntensityFingerprint(
                regionname=subregion.name,
                means=[matched_profiles[region_labels == _].mean() for _ in range(1, 7)],
                stds=[matched_profiles[region_labels == _].std() for _ in range(1, 7)],
            )
            assert fp.matches(subregion)  # to create an assignment result
            result.append(fp)

        return result
