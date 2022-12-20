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

from .. import logger
from ..retrieval import requests
from ..core import space

import numpy as np
import nibabel as nib
from abc import ABC
from typing import List
from ..locations import boundingbox


class ColorVolumeNotSupported(NotImplementedError):
    pass


class Volume:
    """
    A volume is a specific mesh or 3D array,
    which can be accessible via multiple providers in different formats.
    """

    PREFERRED_FORMATS = ["nii", "zip/nii", "neuroglancer/precomputed", "gii-mesh", "neuroglancer/precompmesh", "gii-label"]
    SURFACE_FORMATS = ["gii-mesh", "neuroglancer/precompmesh", "gii-label"]

    def __init__(
        self,
        space_spec: dict,
        providers: List['VolumeProvider'],
        name: str = "",
        variant: str = None,
    ):
        self._name_cached = name  # see lazy implementation below
        self._space_spec = space_spec
        self.variant = variant
        self._providers = {}
        for provider in providers:
            srctype = provider.srctype
            assert srctype not in self._providers
            self._providers[srctype] = provider
        if len(self._providers) == 0:
            logger.debug(f"No provider for volume {self}")

    @property
    def name(self):
        """ allows derived classes to implemente a lazy name specification."""
        return self._name_cached

    @property
    def formats(self):
        return set(self._providers.keys())

    @property
    def is_surface(self):
        return all(f in self.SURFACE_FORMATS for f in self.formats)

    @property
    def fragments(self):
        return {f for p in self._providers.values() for f in p.fragments}

    @property
    def space(self):
        for key in ["@id", "name"]:
            if key in self._space_spec:
                return space.Space.get_instance(self._space_spec[key])
        return space.Space(None, "Unspecified space")

    def __str__(self):
        if self.space is None:
            return f"{self.__class__.__name__} {self.name}"
        else:
            return f"{self.__class__.__name__} {self.name} in {self.space.name}"

    def fetch(
        self,
        voi: boundingbox.BoundingBox = None,
        format: str = None,
        **kwargs
    ):
        """
        Fetch a volumetric or surface representation from one of the providers.

        Parameters
        ----------
        resolution_mm: float
            Desired voxel spacing in mm,
            currently only applicable for neuroglancer volumes.
        voi: BoundingBox
            Desired volume of interest, given as a bounding box,
            currently only applicable for neuroglancer volumes.
        format: str
            Requested format. Per default, several formats are tried,
            starting with volumetric formats. You may explicitly specify:
            - 'surface' or 'mesh' to fetch a surface format
            - 'volumetric' or 'voxel' to fetch a volumetric format
            - supported format types, see Volume.PREFERRED_FORMATS. This includes
              "nii", "zip/nii", "neuroglancer/precomputed", "gii-mesh", 
              "neuroglancer/precompmesh", "gii-label"
        """
        if voi and (voi.space != self.space):
            logger.info(f"Warping volume of interest from {voi.space.name} to {self.space.name}.")
            voi = voi.warp(self.space)

        if format is None:
            requested_formats = self.PREFERRED_FORMATS
        elif format in ['surface', 'mesh']:
            requested_formats = self.SURFACE_FORMATS
        elif format in ['voxels', 'volumetric']:
            requested_formats = set(self.PREFERRED_FORMATS) - set(self.SURFACE_FORMATS)
        elif format in self.PREFERRED_FORMATS:
            requested_formats = [format]
        else:
            raise ValueError(f"Invalid format requested: {format}")

        for fmt in requested_formats:
            if fmt in self.formats:
                try:
                    return self._providers[fmt].fetch(**kwargs)
                except requests.SiibraHttpRequestError as e:
                    logger.error(f"Cannot access {self._providers[fmt]}")
                    print(str(e))
                    continue
        return None


class Subvolume(Volume):
    """
    Wrapper class for exposing a z level of a 4D volume to be used like a 3D volume.
    """
    def __init__(self, parent_volume: Volume, z: int):
        Volume.__init__(
            self,
            space_spec=parent_volume._space_spec,
            providers=[
                SubvolumeProvider(p, z=z)
                for p in parent_volume._providers.values()
            ]
        )


class VolumeProvider(ABC):

    def __init_subclass__(cls, srctype: str) -> None:
        cls.srctype = srctype
        return super().__init_subclass__()

    @property
    def fragments(self):
        return []


class SubvolumeProvider(VolumeProvider, srctype="subvolume"):
    """
    This provider wraps around an existing volume provider,
    but is preconfigured to always fetch a fixed subvolume.
    The primary use is to provide a fixed z coordinate
    of a 4D volume provider as a 3D volume under the
    interface of a normal volume provider.
    """
    def __init__(self, parent_provider: VolumeProvider, z: int):
        VolumeProvider.__init__(self)
        self.provider = parent_provider
        self.srctype = parent_provider.srctype
        self.z = z

    def fetch(self, **kwargs):
        vol = self.provider.fetch(**kwargs)
        arr = np.asanyarray(vol.dataobj)
        assert len(arr.shape) == 4
        assert self.z in range(arr.shape[3])
        return nib.Nifti1Image(arr[:, :, :, self.z].squeeze(), vol.affine)

    def __getattr__(self, attr):
        return self.provider.__getattribute__(attr)
