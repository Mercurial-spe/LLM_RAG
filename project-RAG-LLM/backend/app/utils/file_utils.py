"""通用文件工具函数"""

import hashlib
import os


def calculate_file_md5(file_path: str) -> str:
	"""计算文件的 MD5 哈希

	Args:
		file_path: 文件路径
	Returns:
		32位十六进制 MD5 字符串
	Raises:
		FileNotFoundError: 当文件不存在时
	"""
	if not os.path.exists(file_path):
		raise FileNotFoundError(f"文件不存在: {file_path}")

	md5_hash = hashlib.md5()
	with open(file_path, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			md5_hash.update(chunk)
	return md5_hash.hexdigest()

