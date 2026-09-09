"""Versioned, explainable review signals, not a legal verdict or probability."""
from datetime import datetime, timezone
import hashlib
import re
try:  # Supports both package imports and a Vercel project rooted at backend/.
    from .documents import validate_text
except ImportError:  # pragma: no cover - Vercel backend-root runtime
    from documents import validate_text

VERSION = '2.1.0'
BRAND = re.compile(r'\b(?:Dell|HP|Lenovo|Apple|Samsung|Philips|Siemens|Toyota|BMW|Mercedes|Xerox|Canon|Cisco|Huawei|Xiaomi|Asus|Acer|Intel|AMD|Sony|Epson)\b', re.I)
EQUIVALENT = re.compile(r'или\s+(?:эквивалент|аналог)|(?:эквивалент|аналог)\w*\s+допуска\w*|немесе\s+балама|балама\w*\s+рұқсат', re.I)
NEGATED_BRAND = re.compile(r'(?:бренд|марк\w*|производитель)\s+(?:\w+\s+){0,3}не\s+(?:требуется|указан|ограничен)|бренд\s+маңызды\s+емес', re.I)
RESTRICTION = re.compile(r'аналоги\s+не\s+принимаются|никаких\s+аналогов|без\s+аналогов|не\s+допускается\s+замена|баламалар\s+қабылданбайды|баламаға\s+жол\s+берілмейді|\b(?:строго|исключительно|только|тек)\s+(?=(?:Dell|HP|Lenovo|Apple|Samsung|Philips|Siemens|Toyota|BMW|Mercedes|Xerox|Canon|Cisco|Huawei|Xiaomi|Asus|Acer|Intel|AMD|Sony|Epson)\b)', re.I)
DEALER = re.compile(r'(?:авторизованн\w*|уполномоченн\w*|официальн\w*)\s+(?:дилер\w*|дистрибьютор\w*)|өкілетті\s+дилер', re.I)
DAYS = re.compile(r'(?<!\d)(\d{1,4})\s*(?:(?:рабоч\w*|календар\w*|жұмыс|күнтізбелік)\s+)?(?:день|дня|дней|күн)\b', re.I)
DELIVERY = re.compile(r'постав\w*|достав\w*|жеткіз\w*', re.I)
TECHNICAL_SPEC = re.compile(
    r'(?:процессор|processor|жедел\s+жад|оперативн\w*\s+памят|накопител\w*|диск\w*|экран\w*|монитор\w*|разрешени\w*|ядр\w*|Intel\s+Core|AMD\s+Ryzen|Core\s+i[3579]|i[3579][-–]\d{3,}|\d+\s*(?:ГГц|ГБ|МБ|Гц|дюйм|мм|кг)|\d{3,}[x×]\d{3,})',
    re.I,
)
DOCUMENT_CONTEXT = re.compile(r'предмет\s+закупки|техническ\w*\s+(?:спецификац|требован)|характеристик|требовани\w*|поставк\w*|тауардың\s+атауы|техникалық\s+сипаттама|жеткізу\s+мерзімі', re.I)
POINTS = {'brand': 15, 'technical_specification': 15, 'restriction': 30, 'dealer': 20, 'deadline': 20, 'experience': 15}
LABELS = {'brand': 'Упоминание бренда', 'technical_specification': 'Детальные технические параметры', 'restriction': 'Ограничение аналогов', 'dealer': 'Требование дилерства', 'deadline': 'Короткий срок поставки', 'experience': 'Требование опыта'}
ACTIONS = {
    'brand': 'Уточните, допускается ли эквивалент и чем обосновано указание бренда.',
    'technical_specification': 'Проверьте, действительно ли все точные параметры необходимы и допускается ли эквивалент с сопоставимыми характеристиками.',
    'restriction': 'Запросите обоснование ограничения и возможность предложить эквивалент.',
    'dealer': 'Уточните необходимость статуса дилера и допустимые подтверждающие документы.',
    'deadline': 'Проверьте точку отсчёта срока и возможность поставки в указанные дни.',
    'experience': 'Уточните обоснование требуемого опыта для предмета закупки.',
}


def segments(text):
    # Preserve decimals and initials; retain page-local source quotes.
    return [s.strip() for s in re.split(r'\n+|(?<=[.!?;])\s+(?=[А-ЯӘҒҚҢӨҰҮҺІA-Z])', text) if s.strip()]


def extract_requirements(text):
    patterns = {
        'Предмет закупки': r'(?:предмет\s+закупки|наименование\s+товара|лоттың\s+атауы|тауардың\s+атауы)\s*:?\s*([^\n;]{3,120})',
        'Количество': r'(?:количество|кол-во|саны)\s*:?\s*(\d+\s*(?:штук|шт\.?|единиц|дана|наборов|комплектов)?)',
        'Срок поставки': r'(?:срок\s+поставки|жеткізу\s+мерзімі)\s*:?\s*([^\n;]{3,100})',
        'Цена / стоимость': r'(?:цена|стоимость|баға\w*)[^\d\n]{0,25}(\d[\d\s.,]*\s*(?:тенге|тг|₸|KZT))',
    }
    found = []
    for label, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            found.append({'label': label, 'value': re.sub(r'\s+', ' ', match.group(1)).strip()})
    return found


def analyze(pages, filename='Документ', warnings=None):
    warnings = list(warnings or [])
    text = '\n'.join(p['text'] for p in pages)
    validate_text(text)
    findings = []
    counts = {}
    context_quote = None
    context_page = None
    for page in pages:
        for quote in segments(page['text']):
            if context_quote is None and DOCUMENT_CONTEXT.search(quote):
                context_quote, context_page = quote, page['number']
            keys = []
            if BRAND.search(quote) and not (EQUIVALENT.search(quote) or NEGATED_BRAND.search(quote)):
                keys.append('brand')
            if TECHNICAL_SPEC.search(quote):
                keys.append('technical_specification')
            if RESTRICTION.search(quote):
                keys.append('restriction')
            if DEALER.search(quote) and not re.search(r'не\s+требуется|не\s+обязател\w*|талап\s+етілмейді', quote, re.I):
                keys.append('dealer')
            if DELIVERY.search(quote) and any(1 <= int(m.group(1)) <= 3 for m in DAYS.finditer(quote)):
                keys.append('deadline')
            experience = re.search(r'(?:опыт\s+работы|тәжірибе)\s*(?:не\s+менее|от|кемінде)?\s*(\d+)\s*(?:лет|год\w*|жыл)', quote, re.I)
            if experience and int(experience.group(1)) > 5:
                keys.append('experience')
            for key in keys:
                counts[key] = counts.get(key, 0) + 1
                if counts[key] <= 20:
                    findings.append({'category': key, 'title': LABELS[key], 'page': page['number'], 'quote': quote[:1500], 'action': ACTIONS[key], 'severity': 'attention' if key == 'brand' else 'review'})
    if not findings and context_quote:
        findings.append({
            'category': 'document_context',
            'title': 'Документ содержит условия закупки',
            'page': context_page,
            'quote': context_quote[:1500],
            'action': 'Настроенные признаки риска не найдены. Проверьте технические требования, срок поставки и условия участия вручную.',
            'severity': 'info',
        })
    if any(n > 20 for n in counts.values()):
        warnings.append('Показаны первые 20 фрагментов каждой категории. Приоритет учитывает все найденные категории.')
    incomplete = any('Недостаточно текста' in w for w in warnings)
    score = None if incomplete else min(100, sum(POINTS[k] for k in counts))
    priority = 'incomplete' if incomplete else 'high' if score >= 50 else 'review' if score else 'none'
    return {
        'schema_version': 2, 'analysis_version': VERSION,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'document': {'name': filename[:180], 'pages': len(pages), 'characters': len(text), 'sha256': hashlib.sha256(text.encode()).hexdigest()},
        'mode': 'rules', 'score': score, 'priority': priority,
        'summary': {'incomplete': 'Документ прочитан не полностью', 'high': 'Нужна подробная проверка условий', 'review': 'Есть условия, которые стоит уточнить', 'none': 'Автоматические признаки не найдены — проверьте условия вручную'}[priority],
        'score_explanation': 'Индекс приоритета проверки, не вероятность нарушения. Фиксированные веса категорий; точность на независимой экспертной выборке ещё не измерена.',
        'components': [{'key': k, 'label': LABELS[k], 'points': POINTS[k] if k in counts else 0, 'maximum': POINTS[k], 'count': counts.get(k, 0)} for k in POINTS],
        'findings': findings, 'requirements': extract_requirements(text), 'warnings': warnings,
        'limitations': ['Проверка по текстовым правилам не устанавливает нарушение закона и не заменяет экспертизу.', 'Отсутствие автоматических признаков не подтверждает безопасность закупки. Русские и казахские формулировки покрыты частично.', 'История поставщиков не подключена. Данные о победах и сговоре не формируются.'],
        'supplier_history': {'status': 'unavailable'},
        'ml': {'status': 'not_used', 'included_in_score': False, 'note': 'Проверка выполнена серверными правилами по тексту документа.'},
    }
