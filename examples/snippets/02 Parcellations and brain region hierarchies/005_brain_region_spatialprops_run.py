"""
Spatial properties of brain regions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a reference space is specified, brain regions can expose a range of
spatial properties.
"""

import siibra
atlas = siibra.atlases.MULTILEVEL_HUMAN_ATLAS

# %%
# Compute the centroid and volume of a brain region. 
# Note that a brain region
# might in general consist of multiple separated components in the space.
# Also note that in `siibra`, spatial properties are always represented in
# millimeter units of the physical coordinate system of the reference space,
# not in voxel units.
v1_left = atlas.get_region("v1 left")
space = atlas.spaces.MNI152_2009C_NONL_ASYM
props = v1_left.spatial_props(space)
props

# %%
# The returned centroid is `siibra.Point` object. Such spatial primitives are 
# covered in more detail in :ref:`locations`. For now, we just acknowledge
# that this minimizes misinterpretation of the coordinates, since a siibra
# Point is explicitely linked to its space.
centroid = props['components'][0]['centroid']
print(centroid)
centroid.space.name

# %% 
# We can also generate a binary mask of the region in a given space, which
# gives us a Nifti1Image object as provided by the well established `nibabel
# <https://nipy.org/nibabel/>` library, and which we can directly visualize
# using e.g. plotting functions from `nilearn
# <https://nilearn.github.io/stable/index.html>`:
mask = v1_left.build_mask(space)
from nilearn import plotting
plotting.plot_roi(mask, title=f"Mask of {v1_left.name} in {space.name}")

