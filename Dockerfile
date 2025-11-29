# 使用官方 Python 轻量镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
# --no-cache-dir 减小镜像体积
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有项目文件
COPY . .

# 创建数据目录 (用于挂载卷)
RUN mkdir -p /app/data

# 暴露端口 (Zeabur 默认识别 80 或 5000 等，这里用 5000)
EXPOSE 5000

# 启动命令
# 使用 hypercorn 运行 Quart 应用 (兼容 asyncio)
# main:app 指的是 main.py 中的 app 对象
CMD ["hypercorn", "main:app", "--bind", "0.0.0.0:5000"]