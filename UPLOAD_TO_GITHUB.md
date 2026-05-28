# 上传代码到 GitHub，本地运行程序

这个项目不需要部署到 GitHub 才能使用。GitHub 只用于保存代码；程序仍然在本地电脑运行。

## 1. 在 GitHub 新建仓库

打开 GitHub，新建一个仓库，例如：

```text
huge-catering-wechat
```

建议选择：

```text
Private
```

不要勾选自动创建 README、.gitignore 或 license。

## 2. 复制仓库地址

仓库创建后，复制 HTTPS 地址，格式类似：

```text
https://github.com/你的用户名/huge-catering-wechat.git
```

## 3. 本地推送代码

在 PowerShell 执行：

```powershell
cd "C:\Users\regal\Documents\胡哥说餐饮"
git remote add origin https://github.com/你的用户名/huge-catering-wechat.git
git push -u origin main
```

如果 `origin` 已经存在，改用：

```powershell
git remote set-url origin https://github.com/你的用户名/huge-catering-wechat.git
git push -u origin main
```

## 4. 本地运行网页后台

```powershell
cd "C:\Users\regal\Documents\胡哥说餐饮"
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m huge_catering.webapp --port 8766
```

浏览器打开：

```text
http://127.0.0.1:8766
```

## 不会上传的内容

以下内容已经被 `.gitignore` 排除，不会上传到 GitHub：

```text
.env
.venv/
outputs/
logs/
token_cache.json
data/publish_history.json
data/trend_cache.json
```

