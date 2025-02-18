import asyncio
import smtplib
import hashlib
import json
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import akshare as ak
from ollama import Client
from vnpy_mongodb.mongodb_database import MongodbDatabase

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 配置信息
CONFIG = {
    "database": "bse_stock",
    "news_collection": "trading_data",
    "ollama_model": "deepseek-r1:32b",
    "polling_interval": 120,  # 拉取间隔：2分钟
    "target_stocks": ["837092", "839493", "873806","834415","835305"],  # 北交所股票代码列表
    "ollama_host": "http://localhost:11434",
    "email": {
        "server": "smtp.qq.com",
        "port": 465,
        "username": "569539050@qq.com",
        "password": "purahcwlqzbabdab",
        "sender": "569539050@qq.com",
        "receiver": ["569539050@qq.com", "jiaykkk@163.com"]  # 收件人列表
    }
}

# 初始化数据库连接
db_instance = MongodbDatabase()
client = db_instance.client
db = client[CONFIG["database"]]
ollama = Client(host=CONFIG["ollama_host"])


def fetch_bse_news(stock_code: str):
    """使用 akshare 获取近三天的北交所新闻"""
    try:
        news_df = ak.stock_news_em(symbol=stock_code)
        news_list = news_df.to_dict(orient="records")

        # 过滤近3天的数据
        three_days_ago = datetime.now() - timedelta(days=3)
        filtered_news = []
        for news in news_list:
            pub_date = news.get("发布时间")
            if isinstance(pub_date, str):
                try:
                    pub_date = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            if isinstance(pub_date, datetime) and pub_date >= three_days_ago:
                # 映射字段名称
                news["标题"] = news.get("新闻标题", "")
                news["内容"] = news.get("新闻内容", "")
                news["信息来源"] = news.get("文章来源", "")
                news["stock_code"] = stock_code  # 确保 key 存在
                filtered_news.append(news)

        logging.info(f"成功拉取 {stock_code} 的新闻数据，共 {len(filtered_news)} 条")
        return filtered_news
    except Exception as e:
        logging.error(f"获取 {stock_code} 新闻失败: {str(e)}")
        return []


def fetch_all_recent_news():
    """拉取所有目标股票的新闻数据"""
    all_news = []
    for stock_code in CONFIG["target_stocks"]:
        all_news.extend(fetch_bse_news(stock_code))
    return all_news


def generate_unique_id(stock_code, title):
    """生成唯一 ID 防止重复存储"""
    return hashlib.md5(f"{stock_code}_{title}".encode()).hexdigest()


def generate_advice(news):
    """调用大模型生成交易建议"""
    prompt = f"""
    你是一名专业股票分析师，请根据以下新闻内容：
    {news["内容"][:2000]}

    对该北交所股票（代码：{news["stock_code"]}）给出交易建议，按以下JSON格式回答：
    {{
        "reason": "不超过50字的分析理由",
        "advice": "BUY|SELL|HOLD",
        "confidence": 1-5的置信度评分
    }}
    """
    try:
        response = ollama.generate(model=CONFIG["ollama_model"], prompt=prompt)
        logging.info(f"Ollama 响应: {response}")  # 记录详细的响应内容
        response_content = response.get("response", "")
        if not response_content:
            logging.error("Ollama 响应内容为空")
            return {"reason": "分析失败", "advice": "HOLD", "confidence": 1}

        # 提取 JSON 部分
        json_start = response_content.find('{')
        json_end = response_content.rfind('}')
        if json_start == -1 or json_end == -1:
            logging.error(f"响应内容中未找到有效的 JSON 部分: {response_content}")
            return {"reason": "分析失败", "advice": "HOLD", "confidence": 1}

        response_json_str = response_content[json_start:json_end + 1]
        advice_json = json.loads(response_json_str)
        return advice_json
    except json.JSONDecodeError as e:
        logging.error(f"JSON 解析失败: {str(e)} - 响应内容: {response_content}")
        return {"reason": "分析失败", "advice": "HOLD", "confidence": 1}
    except Exception as e:
        logging.error(f"生成建议失败: {str(e)}")
        return {"reason": "分析失败", "advice": "HOLD", "confidence": 1}


def process_and_save_news(news):
    """处理新闻并保存交易建议"""
    try:
        # 检查必要的字段是否存在且有效
        required_fields = ["标题", "内容", "发布时间", "信息来源", "stock_code"]
        for field in required_fields:
            if field not in news or not news[field]:
                logging.warning(f"新闻记录缺少必要的字段或字段值无效: {news}")
                return

        # 确保发布时间格式
        pub_date = news.get("发布时间", "")
        if isinstance(pub_date, datetime):
            pub_date = pub_date.strftime('%Y-%m-%d %H:%M:%S')
        elif not isinstance(pub_date, str):
            pub_date = str(pub_date)

        # 生成唯一 ID
        unique_id = generate_unique_id(news["stock_code"], news["标题"])

        # 检查数据库是否已有该新闻
        if db[CONFIG["news_collection"]].find_one({"unique_id": unique_id}):
            logging.info(f"新闻已存在，跳过: {news['标题']}")
            return

        # 生成交易建议
        advice = generate_advice(news)

        # 合并新闻和交易建议
        news_record = {
            "unique_id": unique_id,
            "stock_code": news["stock_code"],
            "title": news["标题"],
            "content": news["内容"],
            "source": news["信息来源"],
            "pub_date": pub_date,
            "processed": True,
            "advice": advice["advice"],
            "confidence": advice["confidence"],
            "reason": advice["reason"],
            "analysis_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        result = db[CONFIG["news_collection"]].insert_one(news_record)
        news_record["_id"] = str(result.inserted_id)  # 将 ObjectId 转换为字符串
        logging.info(f"存入新闻和交易建议: {news_record}")

        # 重要新闻或交易建议时发送邮件
        if "重要" in news["标题"] or advice["advice"] in ["BUY", "SELL"]:
            asyncio.create_task(send_email(
                f"交易建议 - {news['stock_code']} ({news['标题']})",
                f"标题: {news_record['title']}\n"
                f"内容: {news_record['content'][:100]}...\n"
                f"来源: {news_record['source']}\n"
                f"发布时间: {news_record['pub_date']}\n"
                f"建议: {news_record['advice']}\n"
                f"置信度: {news_record['confidence']}\n"
                f"理由: {news_record['reason']}",
                CONFIG["email"]["receiver"]
            ))
    except Exception as e:
        logging.error(f"处理新闻失败: {str(e)}")




async def send_email(subject, body, to_emails, retries=3):
    """发送邮件通知，增加重试机制"""
    msg = MIMEMultipart()
    msg["From"] = CONFIG["email"]["sender"]
    msg["To"] = ", ".join(to_emails)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    attempt = 0
    while attempt < retries:
        try:
            with smtplib.SMTP_SSL(CONFIG["email"]["server"], CONFIG["email"]["port"]) as server:
                server.login(CONFIG["email"]["username"], CONFIG["email"]["password"])
                server.sendmail(CONFIG["email"]["sender"], to_emails, msg.as_string())
                logging.info(f"邮件已发送至: {', '.join(to_emails)}")
                return  # 发送成功，退出循环
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP 认证失败: {str(e)}")
            break  # 认证失败，不再重试
        except smtplib.SMTPServerDisconnected as e:
            logging.error(f"SMTP 服务器断开连接: {str(e)}")
        except smtplib.SMTPException as e:
            logging.error(f"SMTP 异常: {str(e)}")
        except Exception as e:
            logging.error(f"发送邮件失败: {str(e)}")

        attempt += 1
        logging.info(f"尝试重新发送邮件，第 {attempt} 次")
        if attempt < retries:
            await asyncio.sleep(10)  # 等待10秒后重试


async def monitor_news():
    """实时监控新闻更新"""
    while True:
        logging.info("开始拉取新闻数据...")
        all_news = fetch_all_recent_news()
        for news in all_news:
            process_and_save_news(news)
        logging.info("完成新闻处理，等待下次抓取...")
        await asyncio.sleep(CONFIG["polling_interval"])


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(monitor_news())
    except KeyboardInterrupt:
        logging.info("实时新闻监控已停止")
    except Exception as e:
        logging.error(f"程序异常终止: {str(e)}")
