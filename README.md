# AI 请求 HOOKER

一个用于捕获和记录 OpenRouter API 请求和响应的代理服务器。

## 使用前准备

### 注册 OpenRouter 账号

1. 访问 [OpenRouter 官网](https://openrouter.ai/)
2. 点击右上角的 "Sign In" 按钮
3. 选择您喜欢的登录方式（GitHub、Google 或 Email）
4. 按照提示完成注册流程

### 获取 API 密钥

1. 登录 OpenRouter 账号后，访问 [API 密钥设置页面](https://openrouter.ai/settings/keys)
2. 点击 "Create Key" 按钮创建新的 API 密钥
3. 为密钥添加描述（可选）
4. 复制生成的 API 密钥，它将用于您的应用程序中（比如 Cline）

## 安装与配置

```bash
# 克隆仓库
git clone https://github.com/itshen/AI_message_hook
cd AI_message_hook

# 安装依赖
pip install -r requirements.txt

# 启动应用
python app.py
```

## 特性

- 捕获所有 OpenRouter API 请求
- 查看请求和响应的详细信息
- 支持流式响应的实时监控
- 简洁美观的用户界面

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

版权所有 © 2024 Miyang Technology (Shenzhen) Co., Ltd. 