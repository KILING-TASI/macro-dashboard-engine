# SPDX-License-Identifier: MIT
"""Keep industry price/capacity/utilization/inventory evidence separate."""
from review_io import cli, day, number, evidence, instant

FAMILIES = {'price':'价格', 'capacity':'产能', 'utilization':'开工率', 'inventory':'库存'}


def review(spec):
    if spec.get('inputSchema') != 'industry-evidence/1':
        raise ValueError('输入须为 industry-evidence/1')
    if not spec.get('industry') or not spec.get('classificationVersion'):
        raise ValueError('须注明行业与分类版本')
    cutoff=day(spec['asOfDate']); rows=[]; seen=set(); excluded=[]
    if instant(spec['asOf']).date()!=cutoff:
        raise ValueError('报告截止日期与截止时间须一致')
    for row in spec['records']:
        family=row['family']
        if family not in FAMILIES or not row.get('id') or row['id'] in seen:
            raise ValueError('证据类型无效或ID重复')
        seen.add(row['id'])
        if not row.get('unit') or not row.get('scope') or not row.get('valueType') in {'disclosed','estimated','proxy'}:
            raise ValueError('证据须明确单位、覆盖范围及披露/估算/代理')
        if day(row['dataDate'])>cutoff or not evidence(row,spec['asOf']):
            excluded.append(row['id']);continue
        value=number(row['value']) if row.get('value') is not None else None
        benchmark=row.get('benchmark'); change=None
        if benchmark is not None:
            for k in ('unit','scope','sourceVersion'):
                if benchmark.get(k)!=row[k]:raise ValueError('基准口径变化：'+k+'，须先完成显式转换')
            if day(benchmark['dataDate'])>=day(row['dataDate']) or not evidence(benchmark,spec['asOf']):
                raise ValueError('基准须为截止内取得的更早期证据')
            base=number(benchmark['value']) if benchmark.get('value') is not None else None
            change=str(value-base) if value is not None and base is not None else None
        rows.append(dict(row, change=change, sourceVerified=False))
    missing=[FAMILIES[f] for f in FAMILIES if not any(r['family']==f and r.get('value') is not None for r in rows)]
    coverage='缺少'+ '、'.join(missing)+'证据' if missing else '四类证据均有声明值'
    return {'methodVersion':'industry-evidence/1', 'status':'partial' if missing or excluded else 'ready-for-review', 'conclusion':('原创教学样本，非真实研究结论。' if spec.get('sampleType')=='teaching' else '')+f"{spec['industry']}按价格、产能、开工率和库存分别展示；{coverage}，不合成为确定的景气或盈利预测。", 'records':rows,'excludedAfterCutoff':excluded,'missingFamilies':missing,'humanRows':[[FAMILIES[r['family']]+' · '+r['id'],(str(r['value']) if r.get('value') is not None else '未知')+' '+r['unit']+'；较所填基准变化 '+(r['change'] if r['change'] is not None else '未知')+'；'+{'disclosed':'披露值','estimated':'估算值','proxy':'代理指标'}[r['valueType']]] for r in rows], 'limitations':['只检查声明口径与时点，未认证原始来源','价格上涨不等于盈利改善；库存增加可能来自补库或滞销','行业分类与样本范围不一致不可直接排名；未覆盖全部31行业','本模块读取资料；新增采集器和数据落库仍由数据仓负责']}


if __name__ == '__main__':
    raise SystemExit(cli({'review':review}, '行业四类证据对照'))
