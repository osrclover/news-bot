import feedparser
import requests
import os
from google import genai
from datetime import datetime

# API 키 설정 (GitHub Secrets)
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# 텔레그램 설정
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# 뉴스 소스 (구글 뉴스 RSS 활용)
NEWS_SOURCES = {
    "일반 뉴스": "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
    "AI 뉴스": "https://news.google.com/rss/search?q=AI+인공지능&hl=ko&gl=KR&ceid=KR:ko",
    "코인 뉴스": "https://news.google.com/rss/search?q=비트코인+암호화폐+코인&hl=ko&gl=KR&ceid=KR:ko"
}


def fetch_news(url):
    """RSS를 통해 뉴스 수집"""
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries]


def filter_news_with_gemini(category, news_list):
    """제미나이를 사용하여 Top 20 뉴스 선별"""
    titles_text = "\n".join([f"{i}. {n['title']}" for i, n in enumerate(news_list[:100])])

    prompt = f"""
    당신은 전문 뉴스 큐레이터입니다. 아래는 오늘 수집된 {category} 목록(최대 100개)입니다.
    이 중에서 가장 중요도가 높고 독자가 꼭 알아야 할 뉴스 20개를 엄선하세요.
    
    결과는 오직 선택된 뉴스의 '번호'만 쉼표로 구분해서 답변하세요. (예: 1, 3, 15, 22...)
    ---
    {titles_text}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        selected_text = response.text.strip()
        indices = [int(i.strip()) for i in selected_text.split(",") if i.strip().isdigit()]

        return [news_list[i] for i in indices if i < len(news_list)][:20]
    except Exception as e:
        print(f"Error during AI analysis: {e}")
        return news_list[:20]


def split_message(message, max_length=4000):
    """긴 메시지를 줄 단위로 나눠서 여러 조각으로 분할"""
    lines = message.split("\n")
    chunks = []
    current_chunk = ""

    for line in lines:
        # 현재 조각에 이 줄을 추가해도 제한 이내인지 확인
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + "\n"
        else:
            # 현재 조각 저장하고 새 조각 시작
            if current_chunk:
                chunks.append(current_chunk.rstrip("\n"))
            current_chunk = line + "\n"

    # 마지막 조각 저장
    if current_chunk:
        chunks.append(current_chunk.rstrip("\n"))

    return chunks


def send_telegram_message(message):
    """텔레그램으로 메시지를 보내는 함수 (긴 메시지는 자동 분할 전송)"""
    if not telegram_token or not telegram_chat_id:
        print("⚠️ TELEGRAM_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return

    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    chunks = split_message(message)

    print(f"📨 총 {len(chunks)}개 메시지로 나눠서 전송합니다...")

    for i, chunk in enumerate(chunks, 1):
        data = {
            "chat_id": telegram_chat_id,
            "text": chunk,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print(f"✅ [{i}/{len(chunks)}] 텔레그램 전송 성공!")
            else:
                print(f"❌ [{i}/{len(chunks)}] 텔레그램 전송 실패: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ [{i}/{len(chunks)}] 텔레그램 전송 에러: {e}")


def main():
    today = datetime.now().strftime('%Y-%m-%d')

    # README용 마크다운 리포트
    report = f"# 🗞️ AI 선정 오늘의 핵심 뉴스 ({today})\n\n"
    report += "> 제미나이(Gemini) AI가 대량의 뉴스 중 가장 중요한 이슈만 선별했습니다.\n\n"

    # 텔레그램용 텍스트
    telegram_text = f"🚀 *오늘의 AI 선정 뉴스 ({today})*\n\n"

    for category, url in NEWS_SOURCES.items():
        print(f"[{category}] 데이터 수집 및 분석 중...")
        raw_news = fetch_news(url)
        top_news = filter_news_with_gemini(category, raw_news)

        # README용
        report += f"## 📌 {category} Top 20\n"
        for i, news in enumerate(top_news):
            report += f"{i+1}. [{news['title']}]({news['link']})\n"
        report += "\n---\n"

        # 텔레그램용
        telegram_text += f"📌 *{category} Top 20*\n"
        for i, news in enumerate(top_news):
            telegram_text += f"{i+1}. [{news['title']}]({news['link']})\n"
        telegram_text += "\n"

    # 1. README.md 파일로 저장
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("📄 뉴스 리포트(README.md) 생성 완료!")

    # 2. 텔레그램으로 전송
    send_telegram_message(telegram_text)


if __name__ == "__main__":
    main()
