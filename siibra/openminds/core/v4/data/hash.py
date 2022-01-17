# generated by datamodel-codegen:
#   filename:  https://raw.githubusercontent.com/HumanBrainProject/openMINDS/3fa86f956b407b2debf47c2e1b6314e37579c707/v3/core/v4/data/hash.schema.json

from pydantic import Field
from siibra.openminds.base import SiibraBaseModel


class Model(SiibraBaseModel):
    id: str = Field(..., alias='@id', description='Metadata node identifier.')
    type: str = Field(..., alias='@type')
    algorithm: str = Field(
        ...,
        alias='https://openminds.ebrains.eu/vocab/algorithm',
        description='Procedure for solving a mathematical problem in a finite number of steps. Can involve repetition of an operation.',
        title='algorithm',
    )
    digest: str = Field(
        ...,
        alias='https://openminds.ebrains.eu/vocab/digest',
        description='Summation or condensation of a body of information.',
        title='digest',
    )
