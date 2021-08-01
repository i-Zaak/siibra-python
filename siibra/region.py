# Copyright 2018-2020 Institute of Neuroscience and Medicine (INM-1), Forschungszentrum Jülich GmbH

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from . import logger,spaces
from .commons import OriginDataInfo, create_key, Glossary, MapType, ParcellationIndex,HasOriginDataInfo
from .space import Space
from .retrieval import GitlabLoader
from . import volumesrc
import numpy as np
import nibabel as nib
from memoization import cached
import re
import anytree
from typing import Union
import json

REMOVE_FROM_NAME=['hemisphere',' -',
    # region string used in receptor features sometimes contains both/Both keywords
    # when they are present, the regions cannot be parsed properly
    'both', 'Both']

def _clear_name(name):
    result = name
    for word in REMOVE_FROM_NAME:
        result = result.replace(word,'')
    return " ".join(w for w in result.split(' ') if len(w))

#RPROPS_REPO = "https://jugit.fz-juelich.de/t.dickscheid/brainscapes-datafeatures"
#RPROPS_BRANCH = "master"
#RPROPS_URL_SCHEME = f"{RPROPS_REPO}/-/raw/{RPROPS_BRANCH}/spatialprops/{{parckey}}-{{spacekey}}-spatialprops.json"

class Region(anytree.NodeMixin, HasOriginDataInfo):
    """
    Representation of a region with name and more optional attributes
    """

    LOADER = GitlabLoader(server='https://jugit.fz-juelich.de',project=3009,reftag='master')

    def __init__(self, name, parcellation, index:ParcellationIndex, attrs={}, parent=None, children=None, volume_src={}):
        """
        Constructs a new region object.

        Parameters
        ----------
        name : str
            Human-readable name of the rgion
        parcellation : Parcellation
            the parcellation object that this region belongs to
        parcellaton : int
            the integer label index used to mark the region in a labelled brain volume
        index : ParcellationIndex
            the integer label index used to specify one of muliple available maps, if any (otherwise None)
        attrs : dict
            A dictionary of arbitrary additional information
        parent : Region
            Parent of this region, if any
        volume_src : Dict of VolumeSrc
            VolumeSrc objects indexed by (Space,MapType), representing available image datasets for this region map.
        """
        HasOriginDataInfo.__init__(self)
        self.name = _clear_name(name)
        self.key = create_key(name)
        self.parcellation = parcellation
        self.index = index
        self.attrs = attrs
        self.parent = parent
        self.volume_src = volume_src
        child_has_mapindex = False
        if children:
            self.children = children
            for c in self.children:
                c.parent = self
                c.parcellation = self.parcellation
                if c.index.map is not None:
                    child_has_mapindex=True

        if (self.index.map is None) and (not child_has_mapindex):
            self.index.map=0

    @staticmethod
    def copy(other):
        """
        copy contructor must detach the parent in to avoid problems with
        the Anytree implementation.
        """
        # create an isolated object, detached from the other's tree
        region = Region(other.name, other.parcellation, other.index, other.attrs)
        region.origin_datainfos=other.origin_datainfos

        # Build the new subtree recursively
        region.children = tuple(Region.copy(c) for c in other.children)
        for c in region.children:
            c.parent = region

        return region

    @property
    def labels(self):
        return {r.index.label for r in self if r.index.label is not None}

    @property
    def names(self):
        return Glossary([r.key for r in self])

    def __eq__(self,other):
        return self.__hash__() == other.__hash__()

    def __hash__(self):
        """
        Identify each region by its parcellation and region key.
        """
        return hash(self.parcellation.key+self.key)

    def has_parent(self,parent):
        return parent in [a for a in self.ancestors]

    def __getattr__(self,name):
        if name in self.attrs.keys():
            return self.attrs[name]
        else:
            raise AttributeError("No such attribute: {}".format(name))

    def includes(self, region):
        """
        Determine wether this regiontree includes the given region.
        """
        return region==self or region in self.descendants

    @cached
    def find(self,regionspec,select_uppermost=False):
        """
        Find regions that match the given region specification in the subtree
        headed by this region. 

        Parameters
        ----------
        regionspec : any of 
            - a string with a possibly inexact name, which is matched both
              against the name and the identifier key, 
            - an integer, which is interpreted as a labelindex,
            - a full ParcellationIndex
            - a region object
        select_uppermost : Boolean
            If true, only the uppermost matches in the region hierarchy are
            returned (otherwise all siblings as well if they match the name)

        Yield
        -----
        list of matching regions
        """
        if isinstance(regionspec,str) and regionspec in self.names:
            # key is given, this gives us an exact region
            return [anytree.search.find_by_attr(self,regionspec,name="key")]
        result = list(set(anytree.search.findall(self,
                lambda node: node.matches(regionspec))))
        if len(result)>1 and select_uppermost:
            all_results = result
            mindepth = min([r.depth for r in result])
            result = [r for r in all_results if r.depth==mindepth]
            if len(result)<len(all_results):
                logger.debug("Returning only {} parent nodes of in total {} matching regions for spec '{}'.".format(
                    len(result), len(all_results), regionspec))

        if isinstance(result,Region):
            return [result]
        elif result is None:
            return []
        else:
            return list(result)

    @cached
    def matches(self,regionspec):
        """ 
        Checks wether this region matches the given region specification. 

        Parameters
        ---------

        regionspec : any of 
            - a string with a possibly inexact name, which is matched both
              against the name and the identifier key, 
            - an integer, which is interpreted as a labelindex,
            - a full ParcellationIndex
            - a region object

        Yield
        -----
        True or False
        """
        splitstr = lambda s : [w for w in re.split('[^a-zA-Z0-9.\-]', s) 
                if len(w)>0]
        if isinstance(regionspec,Region):
            return self==regionspec
        elif isinstance(regionspec,int):
            # argument is int - a labelindex is expected
            return self.index.label==regionspec
        elif isinstance(regionspec,ParcellationIndex):
            return self.index==regionspec          
        elif isinstance(regionspec,str):
            # string is given, perform some lazy string matching
            q = regionspec.lower().strip()
            if q==self.key.lower().strip():
                return True
            elif q==self.name.lower().strip():
                return True
            else:
                words = splitstr(self.name.lower())
                return all([w.lower() in words 
                            for w in splitstr(_clear_name(regionspec))]) 
        else:
            raise TypeError(f"Cannot interpret region specification of type '{type(regionspec)}'")

    @cached
    def build_mask(self,space : Space, resolution_mm=None ):
        """
        Returns a binary mask where nonzero values denote
        voxels corresponding to the region.

        NOTE: This is sensitive to the `continuous_map_threshold` attribute of
        the parent parcellation. If set, thresholded continuous maps will be
        preferred over labelled masks when a continuous regional map is available.

        Parameters
        ----------
        space : Space
            The desired template space.
        resolution_mm : float or None (Default: None)
            Request the template at a particular physical resolution in mm. If None,
            the native resolution is used.
            Currently, this only works for the BigBrain volume.
        """
        if not self.parcellation.supports_space(space):
            logger.error('Region "{}" does not provide a map for space "{}"'.format(
                str(self), str(space) ))

        mask = affine = None 

        if self.parcellation.continuous_map_threshold is not None:

            T = self.parcellation.continuous_map_threshold 
            if self.has_regional_map(space,MapType.CONTINUOUS):
                logger.info(f"Computing mask for {self.name} by thresholding the continuous regional map at {T}.")
                pmap = self.volume_src[space,MapType.CONTINUOUS].fetch(resolution_mm=resolution_mm)
            else:
                logger.info(f"Extracting mask for {self.name} from continuous map volume of {self.parcellation.name}.")
                pmap = self.parcellation.get_map(space,maptype=MapType.CONTINUOUS).extract_regionmap(self,resolution_mm=resolution_mm)
            if pmap is not None:
                mask = (np.asanyarray(pmap.dataobj)>T).astype('uint8')
                affine = pmap.affine

        elif self.has_regional_map(space,MapType.LABELLED):
            logger.info(f"Extracting mask for {self.name} from regional labelmap.")
            labelimg = self.volume_src[space,MapType.LABELLED].fetch(resolution_mm=resolution_mm)
            mask = labelimg.dataobj
            affine = labelimg.affine
        
        else:
            logger.info(f"Extracting mask for {self.name} from parcellation volume of {self.parcellation.name}.")
            labelmap = self.parcellation.get_map(space,maptype=MapType.LABELLED).fetchall(resolution_mm=resolution_mm)
            for mapindex,img in enumerate(labelmap):
                if mask is None:
                    mask = np.zeros(img.dataobj.shape,dtype='uint8')
                    affine = img.affine                
                for r in self: # consider all children
                    if (r.index.map is None) or (r.index.map==mapindex):
                        mask[img.get_fdata()==r.index.label]=1

        if mask is None:
            raise RuntimeError(f"Could not compute mask for {self.region.name} in {space.name}.")
        else:
            return nib.Nifti1Image(dataobj=mask,affine=affine)

    def defined_in_space(self,space):
        """
        Verifies wether this region is defined by a labelled map in the given space.
        TODO handle the case of continuous maps
        """
        try:
            M = self.parcellation.get_map(space,maptype='labelled')
            M.decode_region(self)
            return True
        except (ValueError,IndexError):
            return False

    def has_regional_map(self,space,maptype : MapType):
        """
        Tests wether a specific map is available for this region.

        Parameters
        ----------
        space : Space 
            Template space 
        maptype : MapType
            Type of map (e.g. continuous, labelled - see commons.MapType)
        """
        return (space,maptype) in self.volume_src

    @cached
    def get_regional_map(self,space:Space,maptype:Union[str,MapType]):
        """
        Retrieves and returns a specific map of this region, if available
        (otherwise None). This is typically a probability or otherwise
        continuous map, as opposed to the standard label mask from the discrete
        parcellation.

        Parameters
        ----------
        space : Space, or str
            Specifier for the template space 
        maptype : MapType
            Type of map (e.g. continuous, labelled - see commons.MapType)
        """
        if isinstance(maptype,str):
            maptype = MapType[maptype.upper()]
        try:
            spaceobj = spaces[space]
        except IndexError:
            logger.error(f"Cannot resolve space specification '{space}'.")
            return None
        if not self.has_regional_map(spaceobj,maptype):
            logger.warning(f"{self.parcellation.name} has no regional map for {self} in {spaceobj.name}.")
            return None
        return self.volume_src[spaceobj,maptype]

    def __getitem__(self, labelindex):
        """
        Given an integer label index, return the corresponding region.
        If multiple matches are found, return the unique parent if possible,
        otherwise create an artificial parent node.
        Otherwise, return None

        Parameters
        ----------

        regionlabel: int
            label index of the desired region.

        Return
        ------
        Region object
        """
        if not isinstance(labelindex,int):
            raise TypeError("Index access into the regiontree expects label indices of integer type")

        # first test this head node
        if self.index.label==labelindex:
            return self 

        # Consider children, and return the one with smallest depth
        matches = list(filter(lambda x: x is not None,
            [c[labelindex] for c in self.children] ))
        if matches:
            parentmatches = [m for m in matches if m.parent not in matches]
            if len(parentmatches)==1:
                return parentmatches[0]
            else:
                # create an articicial parent region from the multiple matches
                custom_parent = Region._build_grouptree(
                        parentmatches,self.parcellation)
                assert(custom_parent.index.label==labelindex)
                logger.warn("Label index {} resolves to multiple regions. A customized region subtree is returned: {}".format(
                    labelindex, custom_parent.name))
                return custom_parent
        return None

    @staticmethod
    def _build_grouptree(regions,parcellation):
        """
        Creates an artificial subtree from a list of regions by adding a group
        parent and adding the regions as deep copies recursively.
        """
        # determine appropriate labelindex
        indices = []
        for tree in regions:
            indices.extend([r.index for r in tree])
        unique = set(indices)
        index = next(iter(unique)) if len(unique)==1 else ParcellationIndex(None,None)

        group = Region(
                "Group: "+",".join([r.name for r in regions]),
                parcellation, index, 
                children=[Region.copy(r) for r in regions])
        return group


    def __str__(self):
        return f"{self.parcellation.name}: {self.name}"

    def __repr__(self):
        return  "\n".join("%s%s" % (pre, node.name)
                for pre, _, node in anytree.RenderTree(self))

    @cached
    def spatialprops(self,space,force=False):
        """
        Returns spatial region properties for connected components of this region found by analyzing the parcellation volume in the given space.

        Parameters
        ----------
        space : Space
            the space in which the computation shall be performed
        force : Boolean (Default: False)
            spatialprops will only be computed for leave regions (without
            children), except this is set to True.
        
        Return
        ------
        List of RegionProps objects, one per connected component found in the corresponding labelled parcellation map.
        """
        filename = f"{self.parcellation.key}-{space.key}-spatialprops.json"
        logger.debug(f'Trying to load spatial region props from {filename}')
        try:
            data = self.LOADER.get_file(filename,folder="spatialprops")
            D = json.loads(data)
        except Exception as e:
            raise RuntimeError(f"Cannot load and parse spatial property data for {self.parcellation.name} in {space.name}")
        return [c for p in D['spatialprops'] for c in p['components'] if p['region']['name']==self.name]

    def print_tree(self):
        """
        Returns the hierarchy of all descendants of this region as a tree.
        """
        print(self.__repr__())

    def __iter__(self):
        """
        Returns an iterator that goes through all regions in this subtree
        (including this parent region)
        """
        return anytree.PreOrderIter(self)

    @staticmethod
    def from_json(jsonstr,parcellation):
        """
        Provides an object hook for the json library to construct a Region
        object from a json definition.
        """

        # first construct any child objects
        # This is important due to the bottom-up way the tree gets
        # constructed # in the Region constructor.
        children = []
        if "children" in jsonstr:
            if jsonstr["children"] is not None:
                for regiondef in jsonstr["children"]:
                    children.append(Region.from_json(regiondef,parcellation))

        # Then setup the parent object
        assert('name' in jsonstr)
        name = jsonstr['name'] 
        pindex = ParcellationIndex(
            label = jsonstr['labelIndex'] if 'labelIndex' in jsonstr else None,
            map = jsonstr['mapIndex'] if 'mapIndex' in jsonstr else None)

        # Parse the volume sources in this region definition, if any
        # TODO the json structure should be simplified, the usage type clarified. 
        # @see https://github.com/FZJ-INM1-BDA/siibra-python/issues/42 
        volume_src = {}
        key2maptype = {
                'pmap' : MapType.CONTINUOUS,
                'collect' : MapType.LABELLED
                }
        if 'volumeSrc' in jsonstr:
            for space_id,space_vsources in jsonstr['volumeSrc'].items():
                space = spaces[space_id]
                vsrc_definitions = [{**vsrc,**{'key':key}}
                        for key,vsources in space_vsources.items()
                        for vsrc in vsources ]
                if len(vsrc_definitions)>1:
                    raise NotImplementedError(f"Multiple volume sources defined for region {name} and space {space_id}. This is not yet supported by siibra.")
                if len(vsrc_definitions)==0 or vsrc_definitions[0] is None:
                    raise ValueError(f"No valid volume source found!")
                vsrc = volumesrc.from_json(vsrc_definitions[0])
                key = vsrc_definitions[0]['key']
                if key not in key2maptype:
                    raise NotImplementedError(f"'volumeSrc' field has unknown key '{key}', cannot determine MapType")
                volume_src[space,key2maptype[key]] = vsrc

        r = Region( name, parcellation, pindex, 
                attrs=jsonstr, children=children, 
                volume_src=volume_src )

        if 'originDatasets' in jsonstr:
            origin_datainfos=[OriginDataInfo.from_json(ds) for ds in jsonstr.get('originDatasets', [])]
            r.origin_datainfos=[f for f in origin_datainfos if f is not None]

        # inherit labelindex from children, if they agree
        if pindex.label is None and r.children: 
            L = [c.index.label for c in r.children]
            if (len(L)>0) and (L.count(L[0])==len(L)):
                r.index.label = L[0]

        return r


if __name__ == '__main__':

    definition = {
            'name': 'Interposed Nucleus (Cerebellum) - left hemisphere',
            'rgb': [170, 29, 10],
            'labelIndex': 251,
            'ngId': 'jubrain mni152 v18 left',
            'children': [],
            'position': [-9205882, -57128342, -32224599],
            'originDatasets': [ {
                    'kgId': '658a7f71-1b94-4f4a-8f15-726043bbb52a', 
                    'kgSchema': 'minds/core/dataset/v1.0.0', 
                    'filename': 'Interposed Nucleus (Cerebellum) [v6.2, ICBM 2009c Asymmetric, left hemisphere]'
                    }]
            }

