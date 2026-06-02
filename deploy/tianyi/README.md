# 天翼云 Ubuntu 部署说明

适用环境：Ubuntu 22.04/24.04，开放安全组 80 端口。

## 1. 登录服务器

```bash
ssh root@你的服务器IP
```

## 2. 克隆代码并执行部署

```bash
git clone https://github.com/regalhu/HUGEGONGZHONGHAO.git /opt/huge-catering
cd /opt/huge-catering
sudo bash deploy/tianyi/deploy_ubuntu.sh
```

## 3. 配置公众号环境变量

```bash
sudo nano /opt/huge-catering/.env
```

至少填写：

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

保存后重启：

```bash
sudo systemctl restart huge-catering
```

## 4. 访问

```text
http://你的服务器IP/
```

## 5. 常用命令

```bash
sudo systemctl status huge-catering --no-pager
sudo journalctl -u huge-catering -f
sudo systemctl restart huge-catering
sudo nginx -t
```

## 6. 更新代码

```bash
cd /opt/huge-catering
sudo git pull
sudo /opt/huge-catering/.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart huge-catering
```
