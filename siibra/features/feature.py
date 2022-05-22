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

from ctypes import ArgumentError
from ..commons import MapType, logger, Registry, QUIET
from ..core.concept import AtlasConcept
from ..core.atlas import Atlas
from ..core.space import Space, Location, Point, PointSet, BoundingBox
from ..core.region import Region
from ..core.parcellation import Parcellation

from typing import Tuple, Union
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

try:
    from importlib import resources
except ImportError:
    import importlib_resources as resources
import json
from enum import Enum


class MatchQualification(Enum):
    # Anatomical location of feature matches atlas concept exactly
    EXACT = 0
    # Anatomical location of feature matches atlas concept only approximately
    APPROXIMATE = 1
    # Anatomical location of the feature represents a part of the matched atlas concept
    CONTAINED = 2
    # Anatomical location of the feature inludes the matched atlas concept as a part
    CONTAINS = 3

    @classmethod
    def from_string(cls, name):
        for v in range(4):
            if cls(v).name == name.upper():
                return cls(v)
        return None

    def __str__(self):
        return self.name.lower()


class Match:
    """Description of how a feature has been mapped to an atlas concept."""

    def __init__(
        self,
        concept: AtlasConcept,
        qualification: MatchQualification = MatchQualification.EXACT,
        comment: str = None,
    ):
        """Construct a feature match description.

        Parameters
        ----------
        concept : AtlasConcept
            The atlas concept to which the feature had been mapped.
        qualification: MatchQualifiction
            Qualification of the match, see siibra.feature.MatchQualification
        comment: str
            Optional human-readable explanation comment about the way the match
            was computed
        """
        self.concept = concept
        self.qualification = qualification
        self._comments = []
        if comment is not None:
            self.add_comment(comment)

    @property
    def region(self):
        if isinstance(self.concept, Region):
            return self.concept
        else:
            return None

    @property
    def parcellation(self):
        if isinstance(self.concept, Region):
            return self.concept.parcellation
        elif isinstance(self.concept, Parcellation):
            return self.concept
        else:
            return None

    @property
    def location(self):
        if isinstance(self.concept, Location):
            return self.concept
        else:
            return None

    @property
    def comments(self):
        return ". ".join(self._comments)

    def __str__(self):
        return (
            f"Matched to {self.concept.__class__.__name__} "
            f"'{self.concept.name}' as '{self.qualification}'. "
            f"{self.comments}"
        )

    def add_comment(self, comment: str):
        self._comments.append(comment)


class Feature(ABC):
    """
    Abstract base class for all data features.
    """

    REGISTRY = Registry()

    def __init__(self):
        self._match = None

    def __init_subclass__(cls):
        """
        Registers all subclasses of Feature.
        """
        logger.debug(
            f"Registering feature type {cls.__name__} with modality {cls.modality()}"
        )
        cls.REGISTRY.add(cls.modality(), cls)
        return super().__init_subclass__()

    @property
    def matched(self):
        return self._match is not None

    @property
    def match_qualification(self):
        """If this feature was matched agains an atlas concept,
        return the qualification rating of the match.

        Return
        ------
        siibra.features.feature.MatchQualification, if feature was matche
        else None
        """
        return self._match.qualification if self.matched else None

    @property
    def match_description(self):
        return str(self._match) if self.matched else None

    @property
    def matched_region(self):
        return self._match.region if self.matched else None

    @property
    def matched_parcellation(self):
        return self._match.parcellation if self.matched else None

    @property
    def matched_location(self):
        return self._match.location if self.matched else None

    @abstractmethod
    def match(self, concept, **kwargs):
        """
        Matches this feature to the given atlas concept (or a subconcept of it),
        and remembers the matching result.

        Parameters:
        -----------
        concept : AtlasConcept

        Returns:
        -------
        True, if match was successful, otherwise False
        """
        raise RuntimeError(
            f"match() needs to be implemented by derived classes of {self.__class__.__name__}"
        )

    def __str__(self):
        return f"{self.__class__.__name__} feature"

    @classmethod
    def modality(cls):
        """Returns a string representing the modality of a feature."""
        return str(cls).split("'")[1].split(".")[-1]


class SpatialFeature(Feature):
    """
    Base class for coordinate-anchored data features.
    """

    def __init__(self, location: Location):
        """
        Initialize a new spatial feature.

        Parameters
        ----------
        location : Location type
            The location, see siibra.core.location
        """
        assert location is not None
        Feature.__init__(self)
        self.location = location

    @property
    def space(self):
        return self.location.space

    def match(
        self,
        concept,
        *,
        maptype: MapType = MapType.LABELLED,
        threshold_continuous: float = None,
        **kwargs,
    ):
        """
        Matches this feature to the given atlas concept (or a subconcept of it),
        and remembers the matching result.

        TODO this could use parameters for resolution

        Parameters:
        -----------
        concept : AtlasConcept
        maptype : MapType
        threshold_continuous : float

        Returns:
        -------
        True, if match was successful, otherwise False
        """

        self._match = None
        if self.location is None:
            return False

        if isinstance(concept, Parcellation):
            region = concept.regiontree
            logger.info(
                f"{self.__class__} matching against root node {region.name} of {concept.name}"
            )
        elif isinstance(concept, Region):
            region = concept
        else:
            logger.warning(
                f"{self.__class__} cannot match against {concept.__class__} concepts"
            )
            return False

        for tspace in [self.space] + region.supported_spaces:
            if tspace.is_surface:
                continue
            if region.mapped_in_space(tspace):
                if tspace == self.space:
                    return self._test_mask(
                        self.location,
                        region,
                        tspace,
                        maptype=maptype,
                        threshold_continuous=threshold_continuous,
                    )
                else:
                    logger.warning(
                        f"{self.__class__.__name__} cannot be tested for {region.name} "
                        f"in {self.space}, testing in {tspace} instead."
                    )
                    return self._test_mask(self.location.warp(tspace), region, tspace)
        else:
            logger.warning(f"Cannot test overlap of {self.location} with {region}")

        return self.matched

    def _test_mask(
        self,
        location: Location,
        region: Region,
        space: Space,
        *,
        maptype: MapType = MapType.LABELLED,
        threshold_continuous=None,
    ):
        mask = region.build_mask(
            space=space, maptype=maptype, threshold_continuous=threshold_continuous
        )
        intersection = location.intersection(mask)
        if intersection is None:
            return self.matched
        elif isinstance(location, Point):
            self._match = Match(
                region,
                MatchQualification.EXACT,
                f"Location {location} is inside mask of {region.name}",
            )
        elif isinstance(location, PointSet):
            npts = 1 if isinstance(intersection, Point) else len(intersection)
            if npts == len(location):
                self._match = Match(
                    region,
                    MatchQualification.EXACT,
                    f"All points of {location} inside mask of {region.name}",
                )
            else:
                self._match = Match(
                    region,
                    MatchQualification.APPROXIMATE,
                    f"{npts} of {len(location)} points "
                    f"were inside mask of {region.name}",
                )
        elif isinstance(location, BoundingBox):
            # the intersection of a bounding box with a mask will be a pointset of the
            # mask pixels in the bounding box.
            if location.volume <= intersection.boundingbox.volume:
                self._match = Match(
                    region,
                    MatchQualification.EXACT,
                    f"{str(location)} is fully located inside mask "
                    f"of region {region.name}. ",
                )
            else:
                self._match = Match(
                    region,
                    MatchQualification.APPROXIMATE,
                    f"{str(location)} overlaps with mask " f"of region {region.name}.",
                )
        else:
            self._match = Match(
                region,
                MatchQualification.APPROXIMATE,
                f"Location {location} intersected mask of {region.name}",
            )
        if self.location.space != location.space:
            self._match.add_comment(
                f"The {type(location)} has been warped from {self.location.space} "
                f"to {location.space} for performing the test."
            )
        return self.matched

    def __str__(self):
        return f"{self.__class__.__name__} at {str(self.location)}"


class RegionalFeature(Feature):
    """
    Base class for region-anchored data features (semantic anchoring to region
    names instead of coordinates).
    """

    # load region name aliases from data file
    _aliases = {}
    for species_name in ["human"]:
        # TODO temporary solution
        # when fully migrated to kg v3 query, change .kg_v1_id to .id
        species_id = Atlas.get_species_data("human").kg_v1_id
        with resources.open_text(
            "siibra.features", f"region_aliases_{species_name}.json"
        ) as f:
            _aliases[species_id] = {
                d["Region specification"]
                .lower()
                .strip(): {k: v for k, v in d.items() if k != "Region specification"}
                for d in json.load(f)
            }
        logger.debug(
            f"Loaded {len(_aliases[species_id])} region spec aliases for {species_name}"
        )

    def __init__(self, regionspec: Tuple[str, Region], species=[], **kwargs):
        """
        Parameters
        ----------
        regionspec : string or Region
            Specifier for the brain region, will be matched at test time
        """
        if not any(map(lambda c: isinstance(regionspec, c), [Region, str])):
            raise TypeError(
                f"invalid type {type(regionspec)} provided as region specification"
            )
        Feature.__init__(self)
        self.regionspec = regionspec
        if isinstance(species, list):
            self.species = species
        elif isinstance(species, dict):
            self.species = [species]
        else:
            raise ArgumentError(
                f"Type {type(species)} not expected for species, should be list or dict."
            )

    @property
    def species_ids(self):
        return [s.get("@id") for s in self.species]

    def match(self, concept, **kwargs):
        """
        Matches this feature to the given atlas concept (or a subconcept of it),
        and remembers the matching result.

        Parameters:
        -----------
        concept : AtlasConcept

        Returns:
        -------
        True, if match was successful, otherwise False
        """
        self._match = None

        # Verify that a possible species specification of the feature matches the
        # given concept at all.
        try:
            if isinstance(concept, Region):
                atlases = concept.parcellation.atlases
            if isinstance(concept, Parcellation):
                atlases = concept.atlases
            if isinstance(concept, Atlas):
                atlases = {concept}
            if atlases:
                # if self.species_ids is defined, and the concept is explicitly not in
                # return False
                if all(
                    atlas.species.kg_v1_id not in self.species_ids for atlas in atlases
                ):
                    return self.matched
        # for backwards compatibility. If any attr is not found, pass
        except AttributeError:
            pass

        # Feature's region is specified as a Region object
        # -> we can apply simple tests for any query object.
        if isinstance(self.regionspec, Region):
            return self._match_region(self.regionspec, concept)

        assert isinstance(self.regionspec, str)
        spec = self.regionspec.lower().strip()

        # Feature's region is specified by string. Check alias table first.
        for species_id in set(self.species_ids) & set(self._aliases.keys()):
            if spec in self._aliases[species_id]:
                repl = self._aliases[species_id][spec]
                with QUIET:
                    if repl["Matched parcellation"] is not None:
                        # a matched parcellation is stored in the alias table, this will be preferred.
                        parc = Parcellation.REGISTRY[repl["Matched parcellation"]]
                        spec = repl["Matched region"]
                        msg_alias = (
                            f"Original region specification was '{self.regionspec}'."
                        )
                    else:
                        # no matched parcellation, then we use the original one given in the table.
                        assert repl["Origin parcellation"] is not None
                        parc = Parcellation.REGISTRY[repl["Origin parcellation"]]
                        msg_alias = (
                            f"Parcellation '{parc}' was used to decode '{spec}'."
                        )
                    for r in [parc.decode_region(s) for s in spec.split(",")]:
                        if self._match_region(r, concept):
                            break
                if self._match is not None:
                    self._match.add_comment(msg_alias)
                    if repl["Qualification"] is not None:
                        self._match.qualification = MatchQualification.from_string(
                            repl["Qualification"]
                        )
                return self.matched

        # Feature's region is specified by string, search query is a Parcellation
        if isinstance(concept, Parcellation):
            logger.debug(
                f"{self.__class__} matching against root node {concept.regiontree.name} of {concept.name}"
            )
            for w in concept.key.split("_"):
                spec = spec.replace(w.lower(), "")
            for region in concept.regiontree.find(spec):
                self._match = Match(
                    region,
                    MatchQualification.CONTAINED,
                    f"Feature was linked to {region.name}, which belongs to parcellation {concept.name}.",
                )
                return True

        # Feature's region is specified by string, search query is a Region
        elif isinstance(concept, Region):
            for w in concept.parcellation.key.split("_"):
                if not w.isnumeric() and len(w) > 2:
                    spec = spec.replace(w.lower(), "")
            for region in concept.find(spec):
                if region == concept:
                    self._match = Match(region, MatchQualification.EXACT)
                else:
                    self._match = Match(
                        concept,
                        MatchQualification.CONTAINED,
                        f"Feature was linked to child region '{region.name}'",
                    )
                return True

        # Feature's region is specified by string, search query is an Atlas
        elif isinstance(concept, Atlas):
            logger.debug(
                "Matching regional features against a complete atlas. "
                "This is not efficient and the query may take a while."
            )
            for w in concept.key.split("_"):
                spec = spec.replace(w.lower(), "")
            for p in concept.parcellations:
                for region in p.regiontree.find(spec):
                    self._match = Match(
                        concept,
                        MatchQualification.CONTAINED,
                        f"Region {region.name} belongs to atlas parcellation {p.name}",
                    )
                    return True
        else:
            logger.warning(
                f"{self.__class__} cannot match against {concept.__class__} concepts"
            )

        return self.matched

    def _match_region(self, region: Region, concept: AtlasConcept):
        """
        Match a decoded region object representing the anatomical location
        of this feature to a given atlas concept.

        This is only a convenience function used by match(), and not
        meant for direct evaluation.
        """
        self._match = None
        if isinstance(concept, Parcellation):
            if region in concept:
                self._match = Match(
                    concept,
                    MatchQualification.CONTAINED,
                    f"Feature belongs to {region.name}, which is part of "
                    f"parcellation {concept.name}.",
                )
        elif isinstance(concept, Region):
            if region == concept:
                self._match = Match(concept, MatchQualification.EXACT)
            elif region.has_parent(concept):
                self._match = Match(
                    concept,
                    MatchQualification.CONTAINED,
                    f"Feature was linked to child region '{region.name}'",
                )
            elif concept.has_parent(region):
                self._match = Match(
                    concept,
                    MatchQualification.CONTAINS,
                    f"Feature was linked to parent region '{region.name}'",
                )
        elif isinstance(concept, Atlas):
            if any(region in p for p in concept.parcellations):
                self._match = Match(
                    concept,
                    MatchQualification.CONTAINED,
                    f"Feature belongs to {region.name}, which is part of "
                    f"a parcellation supported by atlas {concept.name}.",
                )
        return self.matched

    def __str__(self):
        return f"{self.__class__.__name__} for {self.regionspec}"


class ParcellationFeature(Feature):
    """
    Base class for data features which apply to the atlas as a whole
    instead of a particular location or region. A typical example is a
    connectivity matrix, which applies to all regions in the atlas.
    """

    def __init__(self, parcellationspec):
        """
        Parameters
        ----------
        parcellationspec : str or Parcellation object
            Identifies the underlying parcellation
        """
        Feature.__init__(self)
        self.spec = parcellationspec
        self.parcellations = Parcellation.REGISTRY.find(parcellationspec)

    def match(self, concept, **kwargs):
        """
        Matches this feature to the given atlas concept (or a subconcept of it),
        and remembers the matching result.

        Parameters:
        -----------
        concept : AtlasConcept

        Returns:
        -------
        True, if match was successful, otherwise False
        """
        self._match = None
        if isinstance(concept, Parcellation):
            if concept in self.parcellations:
                self._match = concept
        elif isinstance(concept, Region):
            if concept.parcellation in self.parcellations:
                self._match = concept
        elif isinstance(concept, Atlas):
            logger.debug(
                "Matching a parcellation feature against a complete atlas. "
                "This will return features matching any supported parcellation, "
                "including different parcellation versions."
            )
            for p in concept.parcellations:
                if p in self.parcellations:
                    self._match = p
                    return True
        else:
            logger.warning(
                f"{self.__class__} cannot match against {concept.__class__} concepts"
            )

        return self.matched

    def __str__(self):
        return f"{self.__class__.__name__} for {self.spec}"


class CorticalProfile(RegionalFeature):
    """
    Represents a 1-dimensional profile of measurements along cortical depth,
    measured at relative depths between 0 representing the pial surface,
    and 1 corresponding to the gray/white matter boundary.

    Mandatory attributes are the list of depth coordinates and the list of
    corresponding measurement values, which have to be of equal length,
    as well as a unit and description of the measurements.

    Optionally, the depth coordinates of layer boundaries can be specified.

    Most attributes are modelled as properties, so dervide classes are able
    to implement lazy loading instead of direct initialiation.

    """

    LAYERS = {0: "0", 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "WM"}
    BOUNDARIES = list(
        zip(list(LAYERS.keys())[:-1], list(LAYERS.keys())[1:])
    )

    def __init__(
        self,
        species: dict,
        regionname: str,
        description: str,
        depths: Union[list, np.ndarray] = None,
        values: Union[list, np.ndarray] = None,
        unit: str = None,
        boundary_positions: dict = None,
    ):
        """Initialize profile.

        Args:
            species (dict):
                Species specification; dictionary with keys 'name', 'id'
            regionname (str):
                Textual description of the brain region
            description (str):
                Human-readable of the modality of the measurements.
            depths (list, optional):
                List of cortical depthh positions corresponding to each
                measurement, all in the range [0..1].
                Defaults to None.
            values (list, optional):
                List of the actual measurements at each depth position.
                Length must correspond to 'depths'.
                Defaults to None.
            unit (str, optional):
                Textual identifier for the unit of measurements.
                Defaults to None.
            boundary_positions (dict, optional):
                Dictionary of depths at which layer boundaries were identified.
                Keys are tuples of layer numbers, e.g. (1,2), values are cortical
                depth positions in the range [0..1].
                Defaults to None.
        """
        RegionalFeature.__init__(self, regionspec=regionname, species=species)

        # cached properties will be revealed as property functions,
        # so derived classes may choose to override for lazy loading.
        self._description = description
        self._unit = unit
        self._depths_cached = depths
        self._values_cached = values
        self._boundary_positions = boundary_positions

    def _assert_consistency(self):
        # check plausibility of the profile
        assert isinstance(self._depths, (list, np.ndarray))
        assert isinstance(self._values, (list, np.ndarray))
        assert len(self._values) == len(self._depths)
        assert all(0 <= d <= 1 for d in self._depths)
        assert all(0 <= d <= 1 for d in self.boundary_positions.values())
        assert all(
            layerpair in self.BOUNDARIES
            for layerpair in self.boundary_positions.keys()
        )

    @property
    def description(self):
        return self._description

    @property
    def unit(self):
        """Optionally overridden in derive classes to enable lazy loading."""
        if self._unit is None:
            raise NotImplementedError(f"'unit' not set for {self.__class__.__name__}.")
        return self._unit

    @property
    def boundary_positions(self):
        if self._boundary_positions is None:
            return {}
        else:
            return self._boundary_positions

    def assign_layer(self, depth: float):
        """ Compute the cortical layer for a given depth from the
        layer boundary positions. If no positions are available
        for this profile, return None. """
        assert 0 <= depth <= 1
        if len(self.boundary_positions) == 0:
            return None
        else:
            return max([
                l2 for (l1, l2), d in self.boundary_positions.items()
                if d < depth
            ])

    @property
    def boundaries_mapped(self):
        return all(
            (b in self.boundary_positions)
            for b in self.BOUNDARIES
        )

    @property
    def _layers(self):
        """ List of layers assigned to each measurments,
        if layer boundaries are available for this features.
        """
        if self.boundaries_mapped:
            return [self.assign_layer(d) for d in self._depths]
        else:
            return None

    @property
    def data(self):
        """Return a pandas Series representing the profile."""
        self._assert_consistency()
        return pd.Series(
            self._values, index=self._depths, name=f"{self.modality()} ({self.unit})"
        )

    def plot(self, ax=None):
        """Plot the profile. If given, the axes `ax` will be used."""
        axs = self.data.plot(
            grid=True,
            ylim=(0, max(self._values)),
            ylabel=self.unit,
            xlabel="Cortical depth",
            ax=ax,
        )

        if self.boundaries_mapped:
            bvals = list(self.boundary_positions.values())
            for i, (d1, d2) in enumerate(list(zip(bvals[:-1], bvals[1:]))):
                axs.text(d1 + (d2 - d1) / 2., 10, self.LAYERS[i + 1], weight='normal', ha='center')
                if i % 2 == 0:
                    axs.axvspan(d1, d2, color="black", alpha=0.1)

        return axs

    @property
    def _depths(self):
        """Returns a list of the relative cortical depths of the measured values in the range [0..1].
        To be implemented in derived class."""
        if self._depths_cached is None:
            raise NotImplementedError(
                f"'_depths' not available for {self.__class__.__name__}."
            )
        return self._depths_cached

    @property
    def _values(self):
        """Returns a list of the measured values per depth.
        To be implemented in derived class."""
        if self._values_cached is None:
            raise NotImplementedError(
                f"'_values' not available for {self.__class__.__name__}."
            )
        return self._values_cached
