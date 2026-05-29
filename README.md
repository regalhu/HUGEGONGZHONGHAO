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
- 默认联网抓取昨天餐饮相关新闻、公开网页、公众号搜索、头条搜索和可抓取社交媒体线索，按引用频次提炼前 10 个餐饮相关热点关键词后生成文章。

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
- 支持单篇归档/删除、全部归档/删除，以及勾选多篇后批量归档/删除。
- 文章结果页提供「图片生成工作台」，自动生成公众号封面、公众号文中配图、小红书封面、视频号/抖音封面的图片提示词，复制后可手动到 ChatGPT Plus 生成图片。

### 草稿管理

草稿列表里的管理动作只处理本地生成文件：

- 归档：把本地草稿移动到 `outputs/_archive/YYYY-MM-DD/`，从当前草稿列表移除。
- 删除：删除本地生成文件，并从当前批次里移除。
- 多选：勾选多篇后，可以批量归档或批量删除。
- 全部归档/全部删除：处理当前列表里的全部草稿。

如果某篇已经上传到微信公众号后台，删除本地草稿不会自动删除公众号后台里的远程草稿，需要到公众号后台手动处理。

### 图片生成工作台

每篇文章的预览结果页下方会自动生成 5 组图片提示词：

- 公众号封面图，推荐比例 2.35:1
- 公众号文中配图 1，推荐比例 16:9
- 公众号文中配图 2，推荐比例 16:9
- 小红书封面图，推荐比例 3:4
- 视频号/抖音封面图，推荐比例 9:16

每组都包含图片用途、推荐尺寸比例、中文提示词、英文提示词、风格说明和禁止元素，并提供「复制提示词」按钮。页面上的「打开 ChatGPT 图片生成」会打开 `https://chatgpt.com/`，由你手动粘贴提示词生成图片。

当前模式不接入 OpenAI API，不需要 API Key，不产生 token 费用。代码里已预留 `imageProvider=manual_chatgpt`，未来可以升级为 `openai_api`、`replicate`、`stability`、`local_sd` 等自动生成方式。

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

程序会抓取昨天餐饮相关新闻、公开网页和可抓取社交媒体线索，统计餐饮相关关键词在标题/摘要中的引用频次，取排名前 10 的关键词作为热点池，再用热门文章常见的“热点提醒/老板注意/先别跟风/10个经营信号”格式生成标题。网络失败时会自动回到本地内容库。

热点源现在使用 Bing 新闻、Bing 网页搜索、百度搜索、搜狗微信、头条搜索、抖音可抓热点，并通过公开搜索覆盖微博、小红书、知乎、B站、公众号等页面。受平台登录、反爬和公开索引限制，程序只使用能公开抓取到的信息，不绕过平台权限。

网页后台一次生成 10 篇时，会优先把热点池前 10 个关键词分别分配给 10 篇草稿，每篇围绕一个不同热点生成。

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
