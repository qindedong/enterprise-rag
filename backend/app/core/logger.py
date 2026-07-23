"""
统一日志系统

所有模块通过 get_logger(__name__) 获取日志实例。
日志格式：时间 | 级别 | 模块名 | 消息

使用示例:
    from app.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("文档处理完成", extra={"doc_id": doc_id, "chunk_count": 15})
"""

import logging
import sys


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 如果有额外字段，追加到日志中
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # 异常信息
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return str(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    获取统一的 Logger 实例

    每个模块在顶部调用一次，后续复用同一个 Logger 实例。

    Args:
        name: 通常传入 __name__，用于标识日志来源模块

    Returns:
        配置好的 logging.Logger 实例

    Examples:
        >>> logger = get_logger(__name__)
        >>> logger.info("服务启动成功")
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # 控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # 使用结构化格式
        formatter = StructuredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.propagate = False

    return logger
