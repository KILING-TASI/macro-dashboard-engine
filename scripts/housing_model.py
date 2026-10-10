# SPDX-License-Identifier: MIT
"""Fixed shared city-price interpretation; canonical owner cn-data-adapters."""
import math

def _num(value):
    if value is None or value == '' or isinstance(value,bool):return None
    try:
        parsed=float(value)
        return parsed if math.isfinite(parsed) else None
    except (ValueError,TypeError):return None

def build_house_price_series(rows, limit=36):
    if type(limit) is not int or not 1<=limit<=120:raise ValueError('房价区间须为1至120个月')
    fields={'new_yoy':'FIRST_COMHOUSE_SAME','new_mom':'FIRST_COMHOUSE_SEQUENTIAL','second_yoy':'SECOND_HOUSE_SAME','second_mom':'SECOND_HOUSE_SEQUENTIAL'}
    by_city={};by_month={};seen=set()
    for row in rows:
        city=row.get('CITY');observed=row.get('REPORT_DATE')
        if not isinstance(city,str) or not city.strip() or not isinstance(observed,str):raise ValueError('城市或统计期缺失')
        from datetime import date
        month=date.fromisoformat(observed[:10]).isoformat()[:7]
        key=(city,month)
        if key in seen:raise ValueError('同城市同月份记录重复；须核对版本')
        seen.add(key)
        values={name:_num(row.get(source)) for name,source in fields.items()}
        if any(v is not None and v<=0 for v in values.values()):raise ValueError('房价指数须为正数或未知')
        by_city.setdefault(city,{})[month]=values
        by_month.setdefault(month,[]).append(values)
    months=sorted(by_month)[-limit:];series={'new':[],'second':[]};coverage={}
    for month in months:
        items=by_month[month];coverage[month]={'cityCount':len(items),'expectedCityCount':70,'identityVerifiedAgainstOfficialList':False}
        for name,source in [('new','new_yoy'),('second','second_yoy')]:
            values=[item[source] for item in items if item[source] is not None]
            coverage[month][name+'KnownCount']=len(values)
            series[name].append(round(sum(values)/len(values),2) if len(items)==70 and len(values)==70 else None)
    latest=series['new'][-1] if months else None;previous=series['new'][-2] if len(months)>1 else None
    city_series={city:{'dates':months,'series':{field:[records.get(month,{}).get(field) for month in months] for field in fields}} for city,records in sorted(by_city.items())}
    return {'name':'城市样本同比指数等权均值（非全国房价指数）','unit':'指数(100=持平)','dates':months,'series':series,'latest':latest,'prev':previous,'mom':None,'yoy':None,
            'citySeries':city_series,'coverage':coverage,'sampleIndexChange':round(latest-previous,3) if latest is not None and previous is not None else None,
            'limitations':['每月70个有值城市时才给样本等权均值，不是官方全国指数','城市同比和环比为不同序列；样本同比指数的月间差不是房价环比','历史首次发布/原文一致性/城市名单与基期版本尚需核验，不能自动作历史已知资料']}
