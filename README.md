# 胡哥说餐饮公众号自动化

这个项目用于每天自动生成「餐饮要赚钱 听我10句劝」文章、封面图、文中图、公众号 HTML 排版，并可在配置公众号密钥后上传到公众号草稿箱。

## 当前能力

- 自动生成一篇每日栏目文章。
- 自动生成公众号封面图 `cover.jpg`。
- 自动生成胡哥漫画风格正文配图 `inline-card.jpg`。
- 封面图和正文配图会结合文章标题、关键词、摘要和建议内容生成，并在写入正文后检查图片是否能正常引用。
- 自动渲染公众号正文 HTML。
- 可调用微信公众平台官方接口创建草稿。
- 使用 `data/topic_library.json` 做内容库。
- 使用 `data/publish_history.json` 记录已发选题，自动避开近期重复。
- 默认联网抓取昨天餐饮相关新闻/热点，提炼关键词后生成当天文章。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env`：

```dotenv
WECHAT_APP_ID=你的公众号AppID
WECHAT_APP_SECRET=你的公众号AppSecret
BRAND_NAME=胡哥说餐饮
COLUMN_NAME=餐饮要赚钱 听我10句劝
AUTHOR_NAME=胡哥
OUTPUT_DIR=outputs
TOPIC_LIBRARY=data/topic_library.json
START_ISSUE_NUMBER=229
```

公众号后台还需要把运行机器的公网 IP 加到开发者配置的 IP 白名单。

## 本地生成预览

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.cli
```

指定日期：

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.cli --date 2026-05-20
```

生成物会在：

```text
outputs/YYYY-MM-DD/
  article.html
  cover.jpg
  inline-card.jpg
  metadata.json
```

## 网页后台

启动网页后台：

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.webapp
```

浏览器打开：

```text
http://127.0.0.1:8765
```

页面支持：

- 点击按钮生成 10 篇文章预览。
- 预览标题、关键词、封面图、胡哥漫画图和正文排版。
- 点击按钮上传单篇到公众号草稿箱。
- 点击按钮批量上传本批次到公众号草稿箱。
- 在「生成设置」里调整文章角度、关键词覆盖、标题风格和配图方式。
- 生成后会检查正文图片，只允许本地原创生成图片；上传草稿后只允许微信素材域名图片。

### 浏览器里配置文章和配图

打开网页后台后，点击顶部「生成设置」：

- 文章设定：可以选择标题风格，填写生成角度，也可以手动覆盖关键词。
- 配图设定：默认使用本地漫画图；如果选择 OpenAI 图片生成，需要填写 `OPENAI_API_KEY`。
- 胡哥形象和图片风格：会一起写入图片提示词，用于生成更贴合文章内容的漫画风格配图。

这里的 OpenAI 连接方式是 API Key，不是模拟登录 ChatGPT 网页账号。API Key 只保存在本机 `data/tool_settings.json` 或 `.env`，不会上传到 GitHub。若 OpenAI 图片生成失败，程序会自动回退到本地漫画图，避免整批草稿中断。

## 上传公众号草稿

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.cli --upload-draft
```

这一步会：

1. 获取公众号 `access_token`。
2. 上传正文图片。
3. 上传封面缩略图素材。
4. 调用草稿箱接口创建草稿。

注意：这里创建的是公众号后台草稿。群发/发布仍建议由你最后审核确认，避免错字、违规表述或平台风控。

## 调整内容风格和选题

内容库在：

```text
data/topic_library.json
```

每个选题包含：

```text
id       选题唯一标识，不要重复
name     选题分类
title    公众号标题
digest   摘要
intro    开头
advices  10句劝，每句包含标题和正文
```

程序每次生成时会读取：

```text
data/publish_history.json
```

如果当天已经生成过，会沿用当天的选题；如果是新的一天，会优先避开近期用过的选题。当前 10 篇都生成完以后，程序会自动写入下一组 10 篇新选题，并继续避开 `data/publish_history.json` 里已经用过的 `topic_id` 和标题。

标题末尾使用连续自然数期号，默认从 `.env` 里的 `START_ISSUE_NUMBER=229` 开始。期号会写入 `data/publish_history.json`，同一天重复运行会沿用同一个期号。

默认启用热点生成：

```dotenv
ENABLE_TREND_CONTENT=true
```

程序会抓取昨天餐饮相关新闻 RSS，提炼关键词，再用热门文章常见的“热点提醒/老板注意/先别跟风/10个经营信号”格式生成标题。网络失败时会自动回到本地内容库。

热点源现在使用 Bing 新闻搜索和抖音热点。Bing 用餐饮关键词搜索新闻结果；抖音热点只采纳餐饮、外卖、食品、茶饮、预制菜等相关热词，避免把无关泛热点写进文章。

## 每天自动运行

可以用 Windows 任务计划程序每天运行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\Users\regal\Documents\胡哥说餐饮\scripts\run_daily.ps1"
```

建议先不加自动群发，只自动生成草稿。等你确认内容风格和微信接口都稳定，再决定是否继续接发布接口。

## 上传到 GitHub，本地运行

GitHub 用来托管代码和做版本备份；程序可以继续在本地电脑运行，不需要部署到 GitHub。

本地启动网页后台：

```powershell
cd "C:\Users\regal\Documents\胡哥说餐饮"
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.webapp --port 8766
```

浏览器打开：

```text
http://127.0.0.1:8766
```

上传 GitHub 的具体步骤见：

```text
UPLOAD_TO_GITHUB.md
```

如果未来要真正放到公网运行，再部署到 Render、Railway、Fly.io 或云服务器。

部署平台需要配置环境变量：

```dotenv
WECHAT_APP_ID=你的公众号AppID
WECHAT_APP_SECRET=你的公众号AppSecret
BRAND_NAME=胡哥说餐饮
COLUMN_NAME=餐饮要赚钱 听我10句劝
AUTHOR_NAME=胡哥
OUTPUT_DIR=outputs
TOPIC_LIBRARY=data/topic_library.json
START_ISSUE_NUMBER=229
ENABLE_TREND_CONTENT=true
OPENAI_API_KEY=可选，OpenAI图片生成使用
```

部署启动命令：

```bash
python -m huge_catering.webapp --host 0.0.0.0 --port $PORT
```

## 项目结构

```text
src/huge_catering/
  cli.py          命令行入口
  config.py       .env 配置
  content.py      文章内容生成
  images.py       封面和文中图生成
  render.py       HTML 排版渲染
  wechat.py       微信公众平台 API 客户端
  pipeline.py     每日流水线
```
