"""Real API smoke checks plus deterministic failure responses; no document uploads to third parties."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path(__file__).resolve().parent.parent/'test-results'
OUT.mkdir(exist_ok=True)
CHROME=r'C:\Program Files\Google\Chrome\Application\chrome.exe'


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=CHROME,headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
        errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8000',wait_until='networkidle')
        expect(page.locator('#service-status')).to_contain_text('Доступен')
        page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
        for width in [320,390,768,1024]:
            page.set_viewport_size({'width':width,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'overflow at {width}'
            if width==390: page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':1050})
        page.locator('#example-button').click()
        page.locator('#submit-button').click()
        expect(page.locator('#result')).to_be_visible(timeout=30000)
        expect(page.locator('.finding')).to_have_count(6)
        expect(page.locator('#report-count')).to_have_text('1')
        page.locator('#result').screenshot(path=str(OUT/'result.png'))
        with page.expect_download() as download:
            page.locator('#export-json').click()
        path=download.value.path(); report=json.loads(Path(path).read_text(encoding='utf-8'))
        assert report['score']==100 and report['example']
        page.locator('#new-analysis').click()
        page.locator('#document-text').fill('Предмет закупки: бумага для офиса. Срок поставки: 21 день. Цена 15000 тенге.')
        page.locator('#submit-button').click()
        expect(page.locator('#report-count')).to_have_text('2',timeout=30000)
        page.locator('#compare-button').click()
        expect(page.locator('#comparison')).to_contain_text('не доказательство большей безопасности')
        # Same file can be uploaded again after reset; text can't create DOM nodes.
        page.locator('#new-analysis').click(); page.locator('#tab-file').click()
        payload='Предмет закупки: <img src=x onerror="window.auditFlag=1">. Поставка строго Dell. Аналоги не принимаются.'
        for count in ['3','4']:
            page.locator('#document-file').set_input_files({'name':'terms.txt','mimeType':'text/plain','buffer':payload.encode()})
            page.locator('#submit-button').click()
            expect(page.locator('#report-count')).to_have_text(count,timeout=30000)
            assert page.locator('#result-content img').count()==0
            assert page.evaluate('window.auditFlag') is None
            page.locator('#new-analysis').click()
        page.locator('#compare-a').select_option('2'); page.locator('#compare-b').select_option('3'); page.locator('#compare-button').click()
        expect(page.locator('#comparison')).to_contain_text('Индексы одинаковы')
        page.locator('#tab-text').click()
        page.locator('#document-text').fill('Поставка бумаги и канцелярских принадлежностей для учебного класса.')
        page.route('**/api/analyze-text',lambda route:route.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'Модель не готова. Анализ не выполнен.'})))
        page.locator('#submit-button').click()
        expect(page.locator('#error')).to_contain_text('Модель не готова')
        expect(page.locator('#result')).to_be_hidden()
        expect(page.locator('#report-count')).to_have_text('4')
        page.unroute('**/api/analyze-text')
        page.route('**/api/analyze-text',lambda route:route.fulfill(status=200,content_type='application/json',body='{"risk_score":12}'))
        page.locator('#submit-button').click(); expect(page.locator('#error')).to_contain_text('несовместима')
        page.unroute('**/api/analyze-text')
        page.locator('#clear-reports').click()
        expect(page.locator('#report-count')).to_have_text('0')
        assert not errors,errors
        browser.close()
        print('Browser checks passed: responsive 320/390/768/1024, real API, export, comparison, repeated file, XSS, 503, schema mismatch, clear reports.')

if __name__=='__main__': main()
