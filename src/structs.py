from pydantic import BaseModel

class MangaMetadata(BaseModel):
    manga_name: str

class ChapterMetadata(BaseModel):
    manga_name: str
    chapter_number: float
