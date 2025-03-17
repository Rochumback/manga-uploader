from uuid import uuid4

import dotenv
from expiringdict import ExpiringDict
from fastapi import APIRouter, FastAPI, Request, Response, UploadFile, status
from fastapi.datastructures import Address

dotenv.load_dotenv()

from structs import ChapterMetadata, MangaMetadata
from uploadable import Manga, MangaChapter

app = FastAPI()


create = APIRouter(prefix="/create")

mangas_map = ExpiringDict(max_len=100, max_age_seconds=600)


@app.post("/upload/{uuid}", status_code=200)
async def upload(uuid: str, data: UploadFile, response: Response):
    upload = mangas_map.get(uuid)  # type: ignore
    if type(upload) is Manga:
        upload.set_image(data)
        upload.build_tree()

    if type(upload) is MangaChapter:
        try:
            upload.set_file(data)
            await upload.save_chapter()
        except Exception as exception:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return {"status": "error", "message": str(exception)}

    if type(upload) is None:
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return {"message": "uplaod not found"}


@create.post("/manga")
async def upload_manga(manga_info: MangaMetadata, request: Request, response: Response):
    temporary_id = str(uuid4())
    try:
        manga = Manga(manga_info)
    except ValueError as exception:
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return str(exception)

    mangas_map[temporary_id] = manga
    client: Address = request.client  # type: ignore
    return f"http://{client.host}:8000/upload/{temporary_id}"


@create.post("/chapter")
async def upload_manga_chapter(
    chapter_info: ChapterMetadata, request: Request, response: Response
):
    temporary_id = str(uuid4())
    try:
        manga = MangaChapter(chapter_info)
    except ValueError as exception:
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return str(exception)

    mangas_map[temporary_id] = manga
    client: Address = request.client  # type: ignore
    return f"http://{client.host}:8000/upload/{temporary_id}"


app.include_router(create)
