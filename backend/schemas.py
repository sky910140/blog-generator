import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Step(BaseModel):
    step_index: int
    timestamp: int
    title: str
    description: str
    image_path: Optional[str] = None


class AIRawData(BaseModel):
    summary: Optional[str] = None
    steps: List[Step]


class ProjectCreateResponse(BaseModel):
    project_id: uuid.UUID
    status: str


class ProjectResponse(BaseModel):
    id: uuid.UUID
    title: str
    source_type: str
    local_video_path: str
    duration: Optional[int]
    status: str
    progress: int
    error_msg: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ContentResponse(BaseModel):
    project_id: uuid.UUID
    ai_raw_data: Optional[AIRawData]
    markdown_content: Optional[str]
    updated_at: datetime

    class Config:
        orm_mode = True


class ContentUpdateRequest(BaseModel):
    markdown: str
