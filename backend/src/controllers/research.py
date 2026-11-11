import json

from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import select

from src.constants.enums import RunStatus
from src.models import Product
from src.services import runs, proposals, artifacts
from src.utils.csv_export import csv_response


def _succeeded_result(run):
    """只有状态成功且结果结构完整时才允许对外发布，杜绝半成品被下载误用。"""
    if run.status != RunStatus.SUCCEEDED:
        raise HTTPException(409, '研究尚未成功完成，暂不可导出结果')
    result = run.result or {}
    if not artifacts.is_complete_result(result):
        raise HTTPException(409, '结果不完整，请重新投递该研究')
    return result


def export_rules(db, id):
    r = runs.get_run(db, id)
    result = _succeeded_result(r)
    names = {p.sku: p.name for p in db.scalars(select(Product))}
    rules = result.get('rules', [])
    return csv_response(
        f'rules-{id}.csv',
        [[','.join(names.get(s, s) for s in x['antecedent']),
          ','.join(names.get(s, s) for s in x['consequent']),
          x['support_count'], x['support'], x['confidence'], x['lift'],
          x['gross_profit'], x['margin']] for x in rules],
        ['前件', '后件', '支持数', '支持度', '置信度', '提升度', '组合毛利', '毛利率'])


def download_result_file(db, id):
    """下载与页面、CSV 同源的完整结果文件；损坏文件即时从数据库重建。"""
    r = runs.get_run(db, id)
    result = _succeeded_result(r)
    payload = artifacts.read_artifact(id)
    if payload is None:
        # 文件缺失/损坏：以数据库成功结果为准原子重建，保证三者对应同一份结果
        artifacts.publish_artifact(id, result)
        payload = result
    return Response(
        json.dumps(payload, ensure_ascii=False),
        media_type='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="run-{id}.json"'})


def export_proposals(db):
    return csv_response('bundle-proposals.csv', [[p['id'], p['name'], p['status'], ','.join(p['rule']['antecedent']), ','.join(p['rule']['consequent']), p['rule']['lift'], p['note']] for p in proposals.list_proposals(db)], ['编号', '提案', '状态', '前件SKU', '后件SKU', '提升度', '说明'])
