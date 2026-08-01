# IP门禁远程解锁
项目 Docker 部署指南
本项目提供了 Dockerfile，你可以通过以下步骤快速进行容器化部署。

前置要求
已安装 Docker

⚙️ 第一步：配置环境变量
在项目根目录下创建一个 .env 配置文件（可以参考 .env.example），填写你的环境参数：

```Ini
# 系统密钥配置
参见 .env.example

# 门禁控制器硬件配置
参见 doors_config.json.example
```

📦 第二步：构建与运行
你可以选择使用 纯 Docker 命令 或 Docker Compose 方式进行部署。

方式一：使用 Docker 原生命令（推荐单容器部署）
构建镜像：

在项目根目录下执行以下命令构建 Docker 镜像：

```Bash
docker build -t door-opener:latest .
```

运行容器：

启动容器并传入 .env 配置文件：

```Bash
docker run -d \
  --name door-opener-app \
  -p 8089:8000 \
  --env-file .env \
  --restart always \
  door-opener:latest
```

访问服务：
打开浏览器访问：http://localhost:8089/