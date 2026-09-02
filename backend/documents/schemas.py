"""Document request/response Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    name: str
    fileType: str
    fileSize: int
    chunkCount: int
    status: str
    embeddingStatus: str
    createdAt: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]


class DocumentDetailResponse(BaseModel):
    id: str
    name: str
    fileType: str
    fileSize: int
    chunkCount: int
    status: str
    embeddingStatus: str
    createdAt: str
    chunks: list["ChunkOut"]


class ChunkOut(BaseModel):
    id: str
    chunkIndex: int
    content: str
    page: int | None


DocumentDetailResponse.model_rebuild()
