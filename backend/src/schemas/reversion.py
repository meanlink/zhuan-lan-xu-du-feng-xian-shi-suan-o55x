from pydantic import BaseModel, Field
class ReversionInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source_dataset_ids: list[int] = Field(min_length=1, max_length=50)
    target_spec_id: int
