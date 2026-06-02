# 胡哥说餐饮公众号自动化

这个项目用于在本地生成「胡哥说餐饮」公众号文章和公众号 HTML 排版，并可在配置公众号密钥后上传到公众号草稿箱。

## 当前能力

- 自动生成一篇每日栏目文章。
- 正文预留 `【图片插入位：请在这里插入本期配图】`，不接入图片生成 API。
- 自动渲染公众号正文 HTML。
- 可调用微信公众平台官方接口创建草稿。
- 使用 `data/topic_library.json` 做内容库。
- 使用 `data/publish_history.json` 记录已发选题，自动避开近期重复。
- 优先使用本地缓存和内置餐饮经营词库生成选题，先保证本地文章质量和排版效果。

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

如果希望登录 Windows 后自动启动网页后台，可以运行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\Users\regal\Documents\胡哥说餐饮\scripts\start_web.ps1"
```

本机已在 Windows 启动文件夹配置 `huge-catering-web.vbs` 和 `huge-catering-web.cmd`，登录电脑后会隐藏启动网页后台并拉起 `http://127.0.0.1:8766`。

主页面支持：

- 默认生成 5 篇文章预览，可改为 1-10 篇，也可一键重新生成。
- 预览标题、关键词、正文排版和质量检查。
- 点击按钮上传单篇到公众号草稿箱。
- 点击按钮批量上传本批次到公众号草稿箱。
- 在主页面直接调整文章类型和期号，并查看最近 5 天餐饮高频关键词。
- 正文保留 `【图片插入位：请在这里插入本期配图】`，不接入图片生成 API。
- 支持单篇归档/删除、全部归档/删除，以及勾选多篇后批量归档/删除。
- 支持复制全文、重新生成单篇、导出 Markdown、导出 HTML。

### 草稿管理

草稿列表里的管理动作只处理本地生成文件：

- 归档：把本地草稿移动到 `outputs/_archive/YYYY-MM-DD/`，从当前草稿列表移除。
- 删除：删除本地生成文件，并从当前批次里移除。
- 多选：勾选多篇后，可以批量归档或批量删除。
- 全部归档/全部删除：处理当前列表里的全部草稿。

如果某篇已经上传到微信公众号后台，删除本地草稿不会自动删除公众号后台里的远程草稿，需要到公众号后台手动处理。

### 草稿输出

每篇草稿支持复制全文、复制 HTML、重新生成单篇、导出 Markdown、导出 HTML。正文只预留图片插入位，不生成图片。

### 浏览器里配置文章

打开网页后台后，在主页面顶部直接配置：

- 文章类型：餐饮10句劝、餐饮热点解读、餐饮方法论
- 期号/标题：10句劝使用固定标题 `餐饮要赚钱 听我10句劝｜第X期`，热点解读和方法论自动生成公众号风格标题
- 关键词结果：展示本地缓存或内置词库中的餐饮经营关键词
- 热点词使用规则：同一个热点关键词不会连续两天使用，至少隔天再用
- 核心生成逻辑：1000 字以内、强实用性、措辞幽默、引用公开数据源

## 上传公众号草稿

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.cli --upload-draft
```

这一步会：

1. 获取公众号 `access_token`。
2. 上传封面缩略图素材。
3. 调用草稿箱接口创建草稿。

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

当前网页生成优先使用本地缓存和内置餐饮经营词库，避免依赖外部数据源。历史联网热点抓取代码仍保留给旧任务兼容，但本轮质量优化先以本地文章模板、结构和排版为主。

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

## 天翼云服务器部署

项目已准备 Ubuntu 服务器部署文件：

```text
deploy/tianyi/
```

服务器推荐使用 `Ubuntu 22.04/24.04`，安全组开放 `80` 端口。登录服务器后执行：

```bash
git clone https://github.com/regalhu/HUGEGONGZHONGHAO.git /opt/huge-catering
cd /opt/huge-catering
sudo bash deploy/tianyi/deploy_ubuntu.sh
sudo nano /opt/huge-catering/.env
sudo systemctl restart huge-catering
```

访问：

```text
http://你的服务器IP/
```

更详细步骤见：

```text
deploy/tianyi/README.md
```

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
ENABLE_TREND_CONTENT=false
```

部署启动命令：

```bash
gunicorn --workers 2 --bind 127.0.0.1:8766 huge_catering.wsgi:app
```

## 项目结构

```text
src/huge_catering/
  cli.py          命令行入口
  config.py       .env 配置
  content.py      文章内容生成
  images.py       兼容旧草稿的封面文件支持
  render.py       HTML 排版渲染
  wechat.py       微信公众平台 API 客户端
  pipeline.py     每日流水线
```
