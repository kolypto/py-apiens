from typing import Optional

import pydantic as pd
from packaging import version


from apiens.tools.pydantic.derive import derive_model, merge_models

# Pydantic Version
PD_VERSION = version.parse(pd.VERSION)

# Pydantic < 1.7.3 report "required-optional" default values as None.
# Newer versions report it as Ellipsis
REQOPT_DEFAULT = None if PD_VERSION < version.parse('1.7.3') else ...


def test_derive_model():
    # Create a model
    class Animal(pd.BaseModel):
        id: int
        name: str
        age: int

    assert set(Animal.__fields__) == {'id', 'name', 'age'}

    # Derive a model
    SecretAnimal = derive_model(Animal, 'SecretAnimal', exclude=('name', 'age'))
    # Check fields
    assert set(SecretAnimal.__fields__) == {'id'}  # only one field left
    id = SecretAnimal.__fields__['id']
    assert id.type_ == int
    assert id.required == True
    # Check inheritance
    assert issubclass(SecretAnimal, Animal)
    # Check json() behavior
    assert SecretAnimal(id=1).dict() == {'id': 1}


    # === Test: required/optional/required-optional fields
    class Animal(pd.BaseModel):
        r: int  # required
        o: Optional[int]  # optional
        ro: Optional[int] = ...  # required-optional

    # Check the initial values
    r, o, ro = Animal.__fields__.values()
    assert r.required == True
    assert o.required == False
    assert ro.required == True

    # Derive a model
    SecretAnimal = derive_model(Animal, 'SecretAnimal', include=('r', 'o', 'ro'))

    # All required/optional fields must stay the same
    r, o, ro = SecretAnimal.__fields__.values()
    assert r.required == True
    assert o.required == False
    if PD_VERSION != version.parse('1.5'):  # TODO: FIXME: fails with pydantic 1.5
        assert ro.required == True
    #
    #
    # # === Test: derive_model() + SALoadedBase
    # Base = declarative_base()
    #
    # class AnimalModel(Base):
    #     __tablename__ = 'animals'
    #     id = sa.Column(sa.Integer, primary_key=True)
    #     name = sa.Column(sa.String)
    #     age = sa.Column(sa.Integer)
    #
    # class AnimalSchema(SALoadedModel):
    #     id: int
    #     name: Optional[str] = None
    #     age: Optional[int] = None
    #
    # AgelessAnimalSchema = sa2.pydantic.derive_model(AnimalSchema, 'AgelessAnimal', exclude=('age',))
    #
    # # Prepare a partially loaded animal
    # # Only one field is loaded: `id`
    # animal = sa_set_committed_state(AnimalModel(), id=1)
    # # Parent schema: SALoadedModel works
    # assert AnimalSchema.from_orm(animal).dict(exclude_unset=True) == {'id': 1}
    # # Subclass schema: SALoadedModel is inherited!
    # assert AgelessAnimalSchema.from_orm(animal).dict(exclude_unset=True) == {'id': 1}


def test_merge_models():
    class A(pd.BaseModel):
        a: Optional[int]
        b: list[int]

    class B(pd.BaseModel):
        c: str
        d: list[str]

    AB = merge_models('AB', A, B)

    assert set(AB.__fields__) == {'a', 'b', 'c', 'd'}
    AB(a=None, b=[1,2,3], c='1', d=[5,6,7])
