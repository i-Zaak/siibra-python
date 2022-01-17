# generated by datamodel-codegen:
#   filename:  https://raw.githubusercontent.com/HumanBrainProject/openMINDS/3fa86f956b407b2debf47c2e1b6314e37579c707/v3/core/v4/miscellaneous/ORCID.schema.json

from pydantic import Field, constr
from siibra.openminds.base import SiibraBaseModel


class Model(SiibraBaseModel):
    id: str = Field(..., alias='@id', description='Metadata node identifier.')
    type: str = Field(..., alias='@type')
    identifier: constr(
        regex=r'^https://orcid.org/[0-9]{4}-[0-9]{4}-[0-9]{4}-([0-9]{3}[A-Z]|[0-9]{4})$'
    ) = Field(
        ...,
        alias='https://openminds.ebrains.eu/vocab/identifier',
        description='Term or code used to identify something or someone.',
        title='identifier',
    )
