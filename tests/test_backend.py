from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from backend.analysis import analyze
from backend.documents import DocumentError, extract_document, extract_bounded, MAX_BYTES
from backend.main import app, model, slots

BASE = 'Предмет закупки: бумага для офиса. Условия поставки согласуются с заказчиком.'


def result(text=BASE, filename='document.pdf'):
    return analyze([{'number': 1, 'text': text}], filename)


def keys(text):
    return {f['category'] for f in result(text)['findings']}


def pdf_bytes(count=1, blank=False):
    writer = PdfWriter()
    for i in range(count):
        page = writer.add_blank_page(width=595, height=842)
        if not blank:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(b'BT /F1 12 Tf 50 700 Td (Office paper supply and standard delivery terms for public procurement.) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(stream)
    out=BytesIO(); writer.write(out); return out.getvalue()


@pytest.mark.parametrize('text', ['', '   ', '123456789', '...'*40])
def test_empty_never_becomes_clean(text):
    with pytest.raises(DocumentError): result(text)


def test_filename_does_not_affect_score():
    a=result(filename='document.pdf'); b=result(filename='Dell Samsung строго.pdf')
    assert a['score']==b['score']==0
    assert a['findings']==b['findings']


@pytest.mark.parametrize('days', [13,21,30,31,101])
def test_number_boundaries(days):
    assert 'deadline' not in keys(BASE+f' Срок поставки: {days} рабочих дней.')


@pytest.mark.parametrize('days', [1,2,3])
def test_short_deadline(days):
    assert 'deadline' in keys(BASE+f' Срок поставки: {days} рабочих дня.')


def test_deadline_requires_delivery_context():
    assert 'deadline' not in keys(BASE+' Срок подачи заявок: 2 рабочих дня.')


def test_equivalent_and_negation():
    assert 'brand' not in keys(BASE+' Поставка Samsung или эквивалент.')
    assert 'brand' not in keys(BASE+' Бренд Samsung не требуется.')
    assert 'dealer' not in keys(BASE+' Авторизованный дилер не требуется.')


def test_kazakh_signals():
    found=keys('Тек Samsung жеткізу қажет. Баламалар қабылданбайды. Жеткізу мерзімі 1 күн.')
    assert {'restriction','deadline','brand'} <= found
    assert 'brand' not in keys('Мектепке арналған тауарды жеткізу қажет. Samsung немесе балама.')


def test_experience_above_ten():
    assert 'experience' in keys(BASE+' Опыт работы не менее 11 лет.')


def test_never_invents_supplier_history():
    r=result(BASE+' ТОО АлматыТрейд. Dell.')
    assert r['supplier_history']=={'status':'unavailable'}
    assert 'ТехноПарк' not in str(r)


def test_price_and_repeated_signals():
    r=result(BASE+' Цена 15000 тенге\nПоставка строго Dell.\n'*3)
    assert r['requirements'][-1]['value']=='15000 тенге'
    assert r['score']==45


def test_detailed_technical_specification_is_visible():
    r = result('Компьютер. Процессор: Intel Core i3-тен төмен емес. Оперативная память: 16 ГБ.')
    categories = {finding['category'] for finding in r['findings']}
    assert {'brand', 'technical_specification'} <= categories
    assert r['score'] == 30


def test_pages_and_partial_extraction():
    r=analyze([{'number':1,'text':BASE},{'number':12,'text':'Поставка строго Dell. Аналоги не принимаются.'}],warnings=['Недостаточно текста на страницах: 2.'])
    assert r['score'] is None and r['priority']=='incomplete'
    assert all(f['page']==12 for f in r['findings'])


def test_all_pdf_pages_read():
    pages, warnings=extract_document(pdf_bytes(12),'file.PDF')
    assert len(pages)==12 and not warnings


def test_scan_rejected():
    with pytest.raises(DocumentError): extract_document(pdf_bytes(blank=True),'scan.pdf')


@pytest.mark.parametrize('data,name', [(b'broken','a.pdf'),(b'', 'a.txt'),(b'\xff\xff','a.txt'),(b'word document','a.docx'),(b'x'*(MAX_BYTES+1),'a.txt')], ids=['broken-pdf','empty','encoding','unsupported','too-large'])
def test_bad_files(data,name):
    with pytest.raises(DocumentError): extract_document(data,name)


def test_pdf_page_limit():
    with pytest.raises(DocumentError, match='100'): extract_document(pdf_bytes(101,True),'a.pdf')


def test_process_extraction():
    pages,warnings=extract_bounded(pdf_bytes(),'valid.pdf')
    assert len(pages)==1 and not warnings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(model,'enabled',False)
    with TestClient(app) as c: yield c


def test_api_json_validation_and_no_echo(client):
    assert client.post('/api/analyze-text',json={'text':''}).status_code==422
    r=client.post('/api/analyze-text',json={'text':BASE}).json()
    assert r['schema_version']==2 and r['mode']=='rules'
    assert client.get('/api/health').json()['status']=='ready'


def test_model_failure_has_no_result(client,monkeypatch):
    monkeypatch.setattr(model,'enabled',True)
    monkeypatch.setattr(model,'ready',False)
    assert client.get('/api/health').status_code==503
    assert client.post('/api/analyze-text',json={'text':BASE}).status_code==503


def test_api_upload(client):
    r=client.post('/api/analyze-file',files={'file':('terms.txt',BASE.encode(),'text/plain')})
    assert r.status_code==200, r.text
    assert r.json()['document']['name']=='terms.txt'
    assert client.post('/api/analyze-file',files={'file':('bad.pdf',b'broken','application/pdf')}).status_code==422


def test_busy_is_explicit(client):
    slots.acquire(); slots.acquire()
    try: assert client.post('/api/analyze-text',json={'text':BASE}).status_code==429
    finally: slots.release(); slots.release()


def test_body_size_limit(client):
    r=client.post('/api/analyze-file',content=b'x'*(MAX_BYTES+65537))
    assert r.status_code==413


def test_server_assets_and_cors(client):
    assert client.get('/').status_code==200
    assert 'script-src' in client.get('/').headers['content-security-policy']
    assert client.get('/model.pkl').status_code==404
    allowed=client.options('/api/analyze-text',headers={'Origin':'https://entelexiya.github.io','Access-Control-Request-Method':'POST'})
    assert allowed.headers.get('access-control-allow-origin')=='https://entelexiya.github.io'
    denied=client.options('/api/analyze-text',headers={'Origin':'https://unknown.example','Access-Control-Request-Method':'POST'})
    assert 'access-control-allow-origin' not in denied.headers
