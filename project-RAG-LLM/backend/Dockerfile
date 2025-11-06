 # syntax=docker/dockerfile:1

 # 轻量 Python 基础镜像
 FROM python:3.11-slim

 ENV PYTHONDONTWRITEBYTECODE=1 \
     PYTHONUNBUFFERED=1 \
     PIP_NO_CACHE_DIR=1 \
     UV_SYSTEM_PYTHON=1

 # 可选：构建参数用于替换 APT/PyPI 源（不设置则使用官方默认源）
 ARG APT_MIRROR=deb.debian.org
 ARG APT_SECURITY_MIRROR=security.debian.org
 ARG PYPI_MIRROR=

# 安装系统依赖（先可选替换镜像源，再安装依赖），兼容 debian.sources
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
      sed -i "s|security.debian.org|${APT_SECURITY_MIRROR}|g" /etc/apt/sources.list; \
    elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i -E "s|^URIs:.*deb.debian.org/debian|URIs: http://${APT_MIRROR}/debian|g" /etc/apt/sources.list.d/debian.sources; \
      sed -i -E "s|^URIs:.*security.debian.org|URIs: http://${APT_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    else \
      . /etc/os-release; \
      echo "deb http://${APT_MIRROR} ${VERSION_CODENAME} main contrib non-free non-free-firmware" > /etc/apt/sources.list; \
      echo "deb http://${APT_SECURITY_MIRROR} ${VERSION_CODENAME}-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list; \
      echo "deb http://${APT_MIRROR} ${VERSION_CODENAME}-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      git \
      pkg-config \
      libssl-dev \
      libffi-dev \
      libsqlite3-dev \
      # 以下为常见运行依赖（opencv/unstructured/pdf 等）
      libglib2.0-0 \
      libsm6 \
      libxrender1 \
      libxext6 \
      libgl1 \
      libmagic1 \
      poppler-utils \
      qpdf \
      tesseract-ocr; \
    rm -rf /var/lib/apt/lists/*

 WORKDIR /app

 # 先复制仅依赖文件以利用 Docker 构建缓存
 COPY ./project-RAG-LLM/backend/requirements.txt ./project-RAG-LLM/backend/requirements.txt

 # 先安装 uv（随后用 uv 来安装 requirements）
 RUN pip install --no-cache-dir uv

 # 使用 uv 安装后端依赖到系统环境（可选使用 PyPI 镜像）
 RUN if [ -n "${PYPI_MIRROR}" ]; then \
       uv pip install --system -i "${PYPI_MIRROR}" -r project-RAG-LLM/backend/requirements.txt; \
     else \
       uv pip install --system -r project-RAG-LLM/backend/requirements.txt; \
     fi

 # 再复制项目代码（利用缓存）
 COPY . /app

 # 暴露后端端口（见 backend/app/config.py PORT=5000）
 EXPOSE 5000

 # 运行 Flask 应用（按项目现有入口）
 CMD ["python", "project-RAG-LLM/backend/run.py"]


