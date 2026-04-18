from pydantic import BaseModel


class LevelPayload(BaseModel):
    level_id: int | None = None


class CommentPayload(BaseModel):
    comment: str | None = None


class AnonymousNamePayload(BaseModel):
    anonymous_name: str | None = None
