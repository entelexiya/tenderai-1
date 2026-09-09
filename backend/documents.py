"""Bounded extraction. An unreadable page is never treated as a clean review."""
from io import BytesIO
import multiprocessing as mp
import re
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 100
MAX_CHARS = 300_000
MIN_LETTERS = 30


class DocumentError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def validate_text(text):
    if len(text) > MAX_CHARS:
        raise DocumentError('text_limit', 'Документ превышает лимит 300 000 символов. Разделите его на части.')
    letters = sum(c.isalpha() for c in text)
    if letters < MIN_LETTERS or '\x00' in text or text.count('\ufffd') > max(3, len(text) // 100):
        raise DocumentError('unreadable_text', 'Недостаточно читаемого текста. Нужен текстовый PDF или TXT в UTF-8.')
    return text


def extract_document(data, name):
    if not data or len(data) > MAX_BYTES:
        raise DocumentError('file_size', 'Файл должен быть непустым и не больше 10 МБ.')
    if name.lower().endswith('.txt'):
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise DocumentError('encoding', 'Сохраните TXT в кодировке UTF-8.') from None
        validate_text(text)
        return [{'number': 1, 'text': text}], []
    if not name.lower().endswith('.pdf') or not data.startswith(b'%PDF-'):
        raise DocumentError('file_type', 'Поддерживаются только PDF и TXT в UTF-8.')
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError('encrypted_pdf', 'PDF защищён паролем. Загрузите незашифрованную копию.')
        if len(reader.pages) > MAX_PAGES:
            raise DocumentError('page_limit', 'В PDF больше 100 страниц. Разделите его на части.')
        pages, unreadable, total = [], [], 0
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            total += len(text)
            if total > MAX_CHARS:
                raise DocumentError('text_limit', 'Документ превышает лимит 300 000 символов.')
            if sum(c.isalpha() for c in text) < MIN_LETTERS:
                unreadable.append(i)
            pages.append({'number': i, 'text': text})
        validate_text('\n'.join(p['text'] for p in pages))
        # Mixed image/text pages cannot be declared fully checked either.
        warnings = []
        if unreadable:
            warnings.append('Недостаточно текста на страницах: ' + ', '.join(map(str, unreadable)) + '. Возможно, это сканы. Итоговая оценка не выставлена; требуется OCR или текстовая копия.')
        return pages, warnings
    except DocumentError:
        raise
    except Exception:
        raise DocumentError('invalid_pdf', 'Не удалось прочитать PDF. Проверьте файл или сохраните текстовую копию.') from None


def _worker(conn, data, name):
    try:
        # Linux Space: bound decompression memory as well as wall-clock time.
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        except ImportError:
            pass  # Windows uses the process deadline and file/page limits.
        conn.send(('ok', extract_document(data, name)))
    except DocumentError as exc:
        conn.send(('error', (exc.code, str(exc))))
    except Exception:
        conn.send(('error', ('invalid_document', 'Не удалось обработать документ.')))
    finally:
        conn.close()


def extract_bounded(data, name, timeout=25):
    """Terminate pathological PDF parsing; don't leave timed-out threads running."""
    ctx = mp.get_context('spawn')
    parent, child = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(child, data, name), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(timeout):
            raise DocumentError('parse_timeout', 'Обработка заняла слишком много времени. Разделите PDF на части.')
        try:
            status, payload = parent.recv()
        except EOFError:
            raise DocumentError('parse_failed', 'Не удалось обработать документ.') from None
        if status == 'error':
            raise DocumentError(*payload)
        return payload
    finally:
        parent.close()
        process.join(timeout=1)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
