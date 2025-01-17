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

"""
Parcellation-based functional data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`siibra` provides access to parcellation-averaged functional data such as
blood-oxygen-level-dependent (BOLD) signals.
"""

# %%
import siibra
# sphinx_gallery_thumbnail_number = 1

# %%
# We start by selecting an atlas parcellation.
jubrain = siibra.parcellations.get("julich 2.9")

# %%
# The matrices are queried as expected, using `siibra.features.get`,
# passing the parcellation as a concept.
# Here, we query for structural connectivity matrices.
features = siibra.features.get(jubrain, siibra.features.functional.RegionalBOLD)
print(f"Found {len(features)} parcellation-based BOLD signals for {jubrain}.")

# %%
# We fetch the first result, which is a specific `RegionalBOLD` object.
bold = features[0]
print(f"RegionalBOLD features reflects {bold.modality} of {bold.cohort} cohort.")
print(bold.name)
print("\n" + bold.description)

# Subjects are encoded via anonymized ids:
print(bold.subjects)


# %%
# The parcellation-based functional data are provided as pandas DataFrames
# with region objects as columns and indices as time step.
subject = bold.subjects[0]
table = bold.get_table(subject)
print(f"Timestep: {bold.timestep}")
table[jubrain.get_region("hOc3v left")]

# %%
# We can visualize the signal strength per region by time via a carpet plot.
# In fact, `plot_carpet` method can take a list of regions to display the
# data for selected regions only.
selected_regions = [
    'SF (Amygdala) left', 'SF (Amygdala) right', 'Area Ph2 (PhG) left',
    'Area Ph2 (PhG) right', 'Area Fo4 (OFC) left', 'Area Fo4 (OFC) right',
    'Area 7A (SPL) left', 'Area 7A (SPL) right', 'CA1 (Hippocampus) left',
    'CA1 (Hippocampus) right', 'CA1 (Hippocampus) left', 'CA1 (Hippocampus) right'
]
bold.plot_carpet(subject=bold.subjects[0], regions=selected_regions)
# %%
# Alternatively, we can visualize the mean signal strength per region:
bold.plot(subject=bold.subjects[0], regions=selected_regions)
