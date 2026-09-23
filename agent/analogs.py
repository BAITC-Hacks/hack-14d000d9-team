"""Adapted from the supplied rank_analogs; critical unknowns now block ranking."""
RULES={
 'mcb':('current','poles','voltage','curve','breaking','mounting'),
 'mccb':('current','poles','voltage','breaking','trip','mounting'),
 'light':('power','socket','voltage','temperature'),
}
LABELS={'current':'ток, А','poles':'полюса','voltage':'напряжение, В','curve':'характеристика','breaking':'отключающая способность, кА','mounting':'монтаж','trip':'расцепитель','power':'мощность, Вт','socket':'цоколь','temperature':'температура, К'}

def rank_analogs(original,candidates,limit=3):
    required=RULES.get(original['category'])
    if not required: return {'items':[],'reason':'Для этой категории критерии аналогов ещё не подтверждены.'}
    missing=[LABELS[k] for k in required if original['specs'].get(k) is None]
    if original['conflicts'] or missing:
        return {'items':[],'reason':'Подбор заблокирован: спорные или неизвестные параметры исходного товара. Уточните: '+', '.join(missing or ['противоречия источников'])}
    results=[]
    for item in candidates:
        if item['id']==original['id'] or item['category']!=original['category'] or item['conflicts']: continue
        if item['stock'] is None or item['stock']<=0: continue
        if any(item['specs'].get(k)!=original['specs'][k] for k in required): continue
        differences=[f"{k}: {original.get(k)} → {item.get(k)}" for k in ['brand','price'] if item.get(k)!=original.get(k)]
        results.append({'product':item,'matches':[f'{LABELS[k]}: {item["specs"][k]}' for k in required],
                        'differences':differences,'unknown':['габариты и условия установки в конкретном щите'],
                        'note':'Кандидат по известным характеристикам; окончательная совместимость требует проверки.'})
    return {'items':results[:limit],'reason':None if results else 'В импортированной выборке нет доступных кандидатов с полным совпадением обязательных параметров.'}
