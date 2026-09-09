from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import threading
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
try:  # Supports both ``backend.main`` and Vercel's backend-root runtime.
    from .analysis import analyze, VERSION
    from .documents import MAX_BYTES, MAX_CHARS, DocumentError, extract_bounded, validate_text
except ImportError:  # pragma: no cover - used only when backend/ is the project root
    from analysis import analyze, VERSION
    from documents import MAX_BYTES, MAX_CHARS, DocumentError, extract_bounded, validate_text

log = logging.getLogger('tenderai')
slots = threading.BoundedSemaphore(2)
ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title='TenderAI', version=VERSION, lifespan=lifespan)
origins = os.getenv('ALLOWED_ORIGINS', 'https://entelexiya.github.io,http://localhost:8000,http://127.0.0.1:8000').split(',')
app.add_middleware(CORSMiddleware, allow_origins=[s.strip() for s in origins if s.strip()], allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        # Bound multipart overhead too, including chunked uploads before parsing.
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > MAX_BYTES + 65536:
                response = JSONResponse({'detail': 'Файл больше 10 МБ.', 'code': 'file_size'}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(body)
            if not message.get('more_body', False):
                break
        pending = True

        async def replay():
            nonlocal pending
            if pending:
                pending = False
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    if request.url.path in ('/', '/legacy.html'):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' https://entelexiya-tenderai-api.hf.space; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


@app.exception_handler(DocumentError)
async def document_error(request, exc):
    return JSONResponse({'detail': str(exc), 'code': exc.code}, status_code=422)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Never echo user documents in validation logs/responses.
    return JSONResponse({'detail': 'Проверьте формат запроса и длину текста.', 'code': 'validation'}, status_code=422)


@app.get('/health')
@app.get('/api/health')
def health():
    return {'status': 'ready', 'schema_version': 2, 'analysis_version': VERSION, 'mode': 'rules'}


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    filename: str = Field(default='Вставленный текст', max_length=180)


def begin():
    if not slots.acquire(blocking=False):
        raise HTTPException(429, 'Сервер занят. Повторите запрос через несколько секунд.', headers={'Retry-After': '5'})


def review(pages, name, warnings):
    result = analyze(pages, name, warnings)
    result['mode'] = 'rules'
    return result


@app.post('/analyze')
@app.post('/api/analyze-text')
def analyze_text(req: TextRequest):
    begin()
    try:
        validate_text(req.text)
        return review([{'number': 1, 'text': req.text}], req.filename, [])
    finally:
        slots.release()


@app.post('/api/analyze-file')
def analyze_file(file: UploadFile):
    begin()
    try:
        data = file.file.read(MAX_BYTES + 1)
        name = (file.filename or 'document').replace('\\', '/').rsplit('/', 1)[-1][:180]
        pages, warnings = extract_bounded(data, name)
        return review(pages, name, warnings)
    finally:
        file.file.close()
        slots.release()


@app.get('/')
def index():
    return FileResponse(ROOT / 'index.html')


@app.get('/legacy.html')
def legacy_index():
    return FileResponse(ROOT / 'legacy.html')


@app.get('/{asset}')
def assets(asset: str):
    if asset not in {'styles.css', 'legacy.css', 'app.js', 'config.js', 'favicon.svg'}:
        raise HTTPException(404, 'Страница не найдена')
    return FileResponse(ROOT / asset)
