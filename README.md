# AI 请求 HOOKER

一个用于捕获和记录 OpenRouter API 请求和响应的代理服务器。

## 功能特点

- 拦截所有到 OpenRouter API 的请求
- 记录请求和响应数据到 SQLite 数据库
- 支持普通请求和流式请求
- 提供美观的 Web 界面查看请求历史
- 可复制请求和响应数据

## 技术栈

- 后端：Flask
- 前端：HTML + TailwindCSS + Vue.js
- 数据库：SQLite

## 安装方法

1. 克隆此仓库

```bash
git clone https://github.com/yourusername/AI_message_hook.git
cd AI_message_hook
```

2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或者
venv\Scripts\activate  # Windows
```

3. 安装依赖

```bash
pip install flask flask-sqlalchemy requests
```

## 使用方法

1. 启动服务器

```bash
python run.py
```

2. 访问 Web 界面

在浏览器中打开 http://localhost:8876 查看 Web 界面。

3. 配置客户端

将您的 OpenRouter 客户端配置为使用 `http://localhost:8876/api/v1` 代替 `https://openrouter.ai/api/v1`。

## 请求路由

所有发送到 `/api/v1/*` 的请求将被代理到 OpenRouter API，并记录请求和响应数据。

例如：
- 原始请求：`https://openrouter.ai/api/v1/chat/completions`
- 代理请求：`http://localhost:8876/api/v1/chat/completions`

## 许可证

MIT 