"""通用文件与文本工具函数

包含：
- 文件基础信息提取（名称/大小/修改时间/后缀）
- 文本 SHA1 计算
- 当前 UTC ISO8601 时间生成
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any, Dict


def get_file_info(file_path: str) -> Dict[str, Any]:
	"""提取文件【物理】基本信息。

	返回字段：
	- file_name: 文件名（不含路径）
	- file_size: 文件大小（字节）
	- file_mtime: 最近修改时间（浮点数 Unix 时间戳）
	- source_type: 文件后缀（小写、不含点）
	"""
	st = os.stat(file_path)
	return {
		"file_name": os.path.basename(file_path),
		"file_size": st.st_size,
		# 返回原始 mtime 时间戳，便于差异比较
		"file_mtime": st.st_mtime,
		"source_type": os.path.splitext(file_path)[1].lstrip(".").lower(),
	}


def sha1_text(text: str) -> str:
	"""计算字符串的 SHA1 哈希（十六进制）。"""
	return hashlib.sha1(text.encode("utf-8")).hexdigest()


def now_iso() -> str:
	"""获取当前 UTC 时间的 ISO8601 字符串（结尾带 Z）。"""
	return datetime.utcnow().isoformat() + "Z"




