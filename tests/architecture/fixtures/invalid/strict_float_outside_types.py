from pydantic import Field, StrictFloat

LocalRatio = Field(gt=0.0, le=1.0, default=StrictFloat)
