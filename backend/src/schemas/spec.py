from pydantic import BaseModel, Field
class SpecInput(BaseModel):
    family: str = Field(min_length=2, max_length=80)
    fields: list[dict] = Field(min_length=1, max_length=20)
    window_days: int = Field(default=14, ge=1, le=60)
    note: str = Field(default='', max_length=500)
