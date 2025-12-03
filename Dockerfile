# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制当前目录下的所有文件 (包含 modules/ 和 templates/) 到容器
COPY . .

RUN mkdir -p /app/data
EXPOSE 5000

# 启动命令保持不变，因为 main.py 里的 app 对象依然叫 app
CMD ["hypercorn", "main:app", "--bind", "0.0.0.0:5000"]