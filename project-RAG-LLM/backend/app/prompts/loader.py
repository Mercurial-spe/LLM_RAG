# backend/app/prompts/loader.py

"""
Prompt 加载器
负责从 Markdown 文件加载 Prompt 模板
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Prompts 目录路径
PROMPTS_DIR = Path(__file__).parent

# Prompt 缓存（避免重复读取文件）
_prompt_cache: Dict[str, str] = {}


def load_prompt(prompt_name: str, use_cache: bool = True) -> str:
    """
    从 Markdown 文件加载 Prompt

    Args:
        prompt_name: Prompt 文件名（不含 .md 后缀）
        use_cache: 是否使用缓存（默认 True）

    Returns:
        Prompt 文本内容

    Raises:
        FileNotFoundError: 如果 Prompt 文件不存在
        IOError: 如果读取文件失败

    Examples:
        >>> load_prompt("rag_system")
        "你是一门计算机网络课程的助教..."

        >>> load_prompt("custom_prompt", use_cache=False)
        "自定义提示词内容..."
    """
    # 检查缓存
    if use_cache and prompt_name in _prompt_cache:
        logger.debug(f"从缓存加载 Prompt: {prompt_name}")
        return _prompt_cache[prompt_name]

    # 构建文件路径
    prompt_file = PROMPTS_DIR / f"{prompt_name}.md"

    # 检查文件是否存在
    if not prompt_file.exists():
        error_msg = f"Prompt 文件不存在: {prompt_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # 读取文件内容
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # 缓存内容
        _prompt_cache[prompt_name] = content

        logger.info(f"成功加载 Prompt: {prompt_name} ({len(content)} 字符)")
        return content

    except Exception as e:
        error_msg = f"读取 Prompt 文件失败: {prompt_file}, 错误: {e}"
        logger.error(error_msg, exc_info=True)
        raise IOError(error_msg) from e


def reload_prompt(prompt_name: str) -> str:
    """
    强制重新加载 Prompt（忽略缓存）

    Args:
        prompt_name: Prompt 文件名（不含 .md 后缀）

    Returns:
        Prompt 文本内容
    """
    # 清除缓存
    if prompt_name in _prompt_cache:
        del _prompt_cache[prompt_name]

    return load_prompt(prompt_name, use_cache=False)


def clear_cache():
    """清空所有 Prompt 缓存"""
    global _prompt_cache
    _prompt_cache.clear()
    logger.info("已清空 Prompt 缓存")


def list_available_prompts() -> list[str]:
    """
    列出所有可用的 Prompt 文件

    Returns:
        Prompt 名称列表（不含 .md 后缀）
    """
    prompts = []
    for file in PROMPTS_DIR.glob("*.md"):
        prompts.append(file.stem)

    logger.debug(f"可用 Prompt: {prompts}")
    return sorted(prompts)
