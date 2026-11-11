"""规则结果留痕（结果文件）服务。

设计要点（gb-0004 数据发布链修复）：
- 结果文件只允许由数据库里已成功的结果派生，二者永远来自同一份 result 字典；
- 写入采用“临时文件 + fsync + 原子 rename”，任何中途失败都只留下 .tmp，
  不会出现被截断的正式结果文件；
- 发布失败由调用方回滚数据库，保证“成功结果落库”与“完整结果文件”同时成立或同时不成立；
- 读取时校验结构，损坏/残缺文件按缺失处理，不会被当成可用结果误用；
- 启动时清理孤儿 .tmp，并为历史成功研究补齐缺失文件（历史研究仍可查看/下载）。
"""
import json
import logging
import os
import tempfile
from pathlib import Path

from sqlalchemy import select

from src.config.settings import ARTIFACT_DIR
from src.models import RuleRun

REQUIRED_KEYS = ("receipt_count", "frequent_itemsets", "rules", "checksum")


def artifact_path(run_id: int) -> Path:
    return Path(ARTIFACT_DIR) / f"run-{run_id}.json"


def is_complete_result(payload) -> bool:
    """对外的结果完整性判定：完整结果才可被页面、CSV、结果文件引用。"""
    return _is_complete(payload)


def _is_complete(payload) -> bool:
    return (
        isinstance(payload, dict)
        and all(key in payload for key in REQUIRED_KEYS)
        and isinstance(payload.get("rules"), list)
        and isinstance(payload.get("checksum"), str)
        and bool(payload["checksum"])
    )


def publish_artifact(run_id: int, result: dict) -> Path:
    """原子发布结果文件。成功返回正式文件路径，失败抛异常且不留半成品正式文件。"""
    if not _is_complete(result):
        raise ValueError("结果结构不完整，拒绝写入结果文件")
    directory = Path(ARTIFACT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    target = artifact_path(run_id)
    # delete=False 自行管理：成功才 close+rename，失败统一清理
    fd, tmp_name = tempfile.mkstemp(prefix=f".run-{run_id}.", suffix=".tmp", dir=directory)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)  # 同目录原子替换，并发发布也只会留下完整文件
        return target
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def read_artifact(run_id: int):
    """读取结果文件；文件缺失或损坏返回 None，绝不返回半成品内容。"""
    path = artifact_path(run_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if _is_complete(payload) else None


def reconcile(db) -> dict:
    """启动对账：清孤儿临时文件，给历史成功研究补齐/修复结果文件。"""
    directory = Path(ARTIFACT_DIR)
    removed_tmp = 0
    repaired = 0
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for tmp in directory.glob(".run-*.tmp"):
            tmp.unlink(missing_ok=True)
            removed_tmp += 1
    except OSError:
        logging.exception("清理结果文件临时目录失败")
    for run in db.scalars(select(RuleRun).where(RuleRun.status == "succeeded")):
        result = run.result
        if not _is_complete(result):
            # 数据库里的成功结果本身不完整：不应存在，标记出来交由人工/重试处理
            logging.error("run %s 标记成功但结果不完整，请重新投递", run.id)
            continue
        if read_artifact(run.id) is None:
            try:
                publish_artifact(run.id, result)
                repaired += 1
            except OSError:
                logging.exception("run %s 结果文件补齐失败", run.id)
    return {"removed_tmp": removed_tmp, "repaired": repaired}
