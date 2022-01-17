# generated by datamodel-codegen:
#   filename:  https://raw.githubusercontent.com/HumanBrainProject/openMINDS/3fa86f956b407b2debf47c2e1b6314e37579c707/v3/core/v4/research/stimulation.schema.json

from typing import Any, Dict, Optional

from pydantic import Field
from siibra.openminds.base import SiibraBaseModel


class Model(SiibraBaseModel):
    id: str = Field(..., alias='@id', description='Metadata node identifier.')
    type: str = Field(..., alias='@type')
    description: Optional[str] = Field(
        None,
        alias='https://openminds.ebrains.eu/vocab/description',
        description='Longer statement or account giving the characteristics of someone or something.',
        title='description',
    )
    lookup_label: Optional[str] = Field(
        None,
        alias='https://openminds.ebrains.eu/vocab/lookupLabel',
        title='lookupLabel',
    )
    stimulation_approach: Dict[str, Any] = Field(
        ...,
        alias='https://openminds.ebrains.eu/vocab/stimulationApproach',
        title='stimulationApproach',
    )
    stimulus_type: Dict[str, Any] = Field(
        ...,
        alias='https://openminds.ebrains.eu/vocab/stimulusType',
        title='stimulusType',
    )
