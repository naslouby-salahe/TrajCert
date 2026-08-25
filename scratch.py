from typing import Annotated, Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema


class NDArrayFloat64Annotation:
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.any_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: x.tolist(),
                info_arg=False,
                return_schema=core_schema.list_schema(core_schema.float_schema()),
            ),
        )

    @classmethod
    def validate(cls, v: Any) -> NDArray[np.float64]:
        if isinstance(v, np.ndarray):
            return v.astype(np.float64)
        return np.array(v, dtype=np.float64)


Vector = Annotated[NDArray[np.float64], NDArrayFloat64Annotation]


class TestModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    arr: Vector


m = TestModel(arr=[1.0, 2.0, 3.0])
print(type(m.arr))
print(m.model_dump())
