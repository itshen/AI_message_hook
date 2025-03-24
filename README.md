# AI 请求 HOOKER

一个用于捕获和记录 AI API 请求和响应的代理服务器。支持多种主流 AI 服务，包括 OpenAI、千问、智谱等。

## 支持的 API 服务

目前支持以下 AI 服务：

- OpenAI ([获取 Key](https://platform.openai.com/api-keys))
- 千问 ([获取 Key](https://bailian.console.aliyun.com/?apiKey=1))
- 智谱 AI ([获取 Key](https://open.bigmodel.cn/usercenter/apikeys))
- MiniMax ([获取 Key](https://platform.minimaxi.com/user-center/basic-information/interface-key))
- DeepSeek ([获取 Key](https://platform.deepseek.com/))
- 硅基流动 ([获取 Key](https://cloud.siliconflow.cn/i/gQhQNfpv))
- OpenRouter ([获取 Key](https://openrouter.ai/settings/keys))

## 使用前准备（以 OpenRouter 为例）

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
python run.py
```

## 主要功能

- 支持多种主流 AI API 服务
- 自动替换/补全 API Key
- 自动替换/补全模型名称
- 实时监控请求和响应
- 支持流式响应的实时监控
- 请求历史记录和详情查看
- 请求头和请求体变更对比
- 简洁美观的用户界面

## 使用说明

1. 启动服务后，访问 `http://localhost:7860`
2. 在设置中配置相应服务的 API Key
3. 选择需要使用的 AI 服务
4. 开始使用您的应用程序，所有的 API 请求都会被记录

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

版权所有 © 2024 Miyang Technology (Shenzhen) Co., Ltd. 