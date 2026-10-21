from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str = ""
    excerpt: str = ""


class Finding(BaseModel):
    summary: str
    sources: list[Source] = Field(default_factory=list)
