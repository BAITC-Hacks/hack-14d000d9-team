"""Source-preserving, conservative normalization. No electrical compatibility inference."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


def number(value):
    if value is None or isinstance(value, bool):
        return None
    text = str(value).replace('\u00a0', '').replace(' ', '')
    # Ranges, ratios and multiple values are not a single confirmed rating.
    if re.search(r'\d\s*(?:[-–—…/]|\.\.)\s*\d', text):
        return None
    match = re.search(r'-?\d+(?:[.,]\d+)?', text)
    return float(match.group().replace(',', '.')) if match else None


def safe_url(value):
    if not isinstance(value, str):
        return None
    p = urlparse(value)
    return value if p.scheme == 'https' and p.hostname in {'ekt.kz', 'www.ekt.kz'} and not p.username else None


def normalize(raw, source, sellable_ids=(), default_currency=None):
    props = raw.get('properties') or {}
    name = str(raw.get('name', 'Без названия'))
    desc = re.sub('<[^>]*>', ' ', str(raw.get('description') or ''))
    category = raw.get('_category')
    if not category:
        n = name.lower()
        category = 'mccb' if 'drx' in n else 'rcbo' if 'диф.' in n else 'relay' if 'реле' in n else 'light' if any(x in n for x in ['led', 'светильник']) else 'other'
    evidence = {}
    def field(key, prop, pattern=None):
        observations = []
        if props.get(prop) is not None:
            value = number(props[prop])
            unit = str(props[prop]).lower().replace(' ', '')
            if value is not None:
                if key == 'current' and re.search(r'(?:ма|ma)$', unit): value /= 1000
                if key == 'voltage' and re.search(r'(?:кв|kv)$', unit): value *= 1000
                if key == 'breaking' and re.search(r'(?<![кk])[аa]$', unit): value /= 1000
            observations.append({'value': value, 'raw': props[prop], 'path': 'properties.' + prop})
        if pattern:
            for path, text in [('name', name), ('description', desc)]:
                for m in re.finditer(pattern, text, re.I):
                    observations.append({'value': number(m.group(1)), 'raw': m.group(), 'path': path})
        observations = [o for o in observations if o['value'] is not None]
        evidence[key] = observations
        vals = {o['value'] for o in observations}
        return next(iter(vals)) if len(vals) == 1 else None
    specs = {
        'current': field('current', 'NOMINALNYY_TOK', r'(?<![\w.,])([0-9]+(?:[.,][0-9]+)?)\s*[АA](?![a-zа-я])'),
        'poles': field('poles', 'KOLICHESTVO_POLYUSOV', r'(?<!\w)([1-4])\s*(?:P|ф)(?!\w)'),
        'voltage': field('voltage', 'NOMINALNOE_NAPRYAZHENIE', r'(?<![\w.,])([0-9]+)\s*(?:В|V)(?![a-zа-я])'),
        'breaking': field('breaking', 'NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST', r'(?<!\w)([0-9]+(?:[.,][0-9]+)?)\s*(?:кА|ka)(?!\w)'),
        'curve': props.get('CURVE'), 'mounting': props.get('TIP_USTANOVKI'),
        'trip': props.get('TRIP_TYPE'), 'power': number(props.get('POWER_W')),
        'socket': props.get('SOCKET'), 'temperature': number(props.get('COLOR_K')),
    }
    conflicts = [{'field': k, 'values': sorted({o['value'] for o in obs}), 'message': 'Противоречие источников. Требуется уточнение у менеджера.'} for k, obs in evidence.items() if len({o['value'] for o in obs}) > 1]
    stores = raw.get('stores') if isinstance(raw.get('stores'), list) else []
    allowed = [s for s in stores if str(s.get('id')) in set(map(str, sellable_ids))]
    quantities = [number(s.get('quantity')) for s in allowed]
    stock = sum(quantities) if allowed and all(q is not None and q >= 0 for q in quantities) else None
    quantity = number(raw.get('quantity'))
    if stock is not None and quantity is not None:
        stock = min(stock, max(0, quantity))
    supplier = str(props.get('ARTIKULPOSTAVSHCHIKA') or '')
    if not supplier and re.match(r'^\d{6}\s', name):
        supplier = name.split()[0]
    return dict(id=str(raw['id']), name=name, article=str(raw.get('article', '')), supplier_article=supplier,
                description=desc, category=category, brand=props.get('TORGOVAYA_MARKA') or ('Legrand' if 'legrand' in name.lower() else None),
                price=number(raw.get('price')), currency=raw.get('currency') or default_currency,
                currency_source='catalog' if raw.get('currency') else ('project_config' if default_currency else None), quantity=quantity, stock=stock,
                stores=stores, specs=specs, evidence=evidence, conflicts=conflicts,
                image=safe_url(raw.get('image')), url=safe_url(raw.get('url')),
                certificate_url=safe_url(raw.get('certificate_url')), source=source, raw=raw)


def timestamp():
    return datetime.now(timezone.utc).isoformat()
