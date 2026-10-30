FROM python:3.11-slim

WORKDIR /app

# 设置环境变量，防止 Python 生成 .pyc 文件并关闭 stdout 缓冲，日志响应更实时
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY main.py .
COPY config.py .
COPY web ./web
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]