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

# ── 뉴스 소스 ──────────────────────────────────────────────────
# 카테고리별로 여러 매체의 RSS를 묶어서 수집합니다.
NEWS_SOURCES = {
    "국내 일반 뉴스": [
        "https://www.yonhapnewstv.co.kr/browse/feed/",          # 연합뉴스TV
        "https://rss.chosun.com/site/data/rss/rss.xml",         # 조선일보
        "https://www.hani.co.kr/rss/",                          # 한겨레
        "https://rss.joins.com/joins_news_list.xml",             # 중앙일보
        "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",  # 구글 뉴스 KR
    ],
    "AI · 테크 뉴스": [
        "https://news.google.com/rss/search?q=AI+인공지능+chatgpt&hl=ko&gl=KR&ceid=KR:ko",
        "https://feeds.feedburner.com/venturebeat/SZYF",         # VentureBeat AI
        "https://techcrunch.com/feed/",                          # TechCrunch
        "https://www.technologyreview.com/feed/",                # MIT Tech Review
        "https://news.google.com/rss/search?q=artificial+intelligence&hl=en&gl=US&ceid=US:en",
    ],
    "코인 · 경제 뉴스": [
        "https://news.google.com/rss/search?q=비트코인+이더리움+코인&hl=ko&gl=KR&ceid=KR:ko",
        "https://cointelegraph.com/rss",                         # CoinTelegraph
        "https://coindesk.com/arc/outboundfeeds/rss/",          # CoinDesk
        "https://feeds.bloomberg.com/markets/news.rss",          # Bloomberg Markets
        "https://feeds.reuters.com/reuters/businessNews",        # Reuters Business
    ],
}
# ───────────────────────────────────────────────────────────────


def fetch_news(urls: list) -> list:
    """여러 RSS URL에서 뉴스를 수집하고 중복 제목을 제거합니다."""
    seen_titles = set()
    all_news = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link  = entry.get("link", "").strip()
                if title and link and title not in seen_titles:
                    seen_titles.add(title)
                    all_news.append({"title": title, "link": link})
        except Exception as e:
            print(f"  ⚠️ RSS 수집 오류 ({url}): {e}")
    return all_news


def filter_news_with_gemini(category: str, news_list: list) -> list:
    """제미나이를 사용하여 Top 10 뉴스 선별"""
    if not news_list:
        return []

    titles_text = "\n".join([f"{i}. {n['title']}" for i, n in enumerate(news_list[:100])])

    prompt = f"""
    당신은 전문 뉴스 큐레이터입니다. 아래는 오늘 수집된 {category} 목록(최대 100개)입니다.
    이 중에서 가장 중요도가 높고 독자가 꼭 알아야 할 뉴스 10개를 엄선하세요.

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

        return [news_list[i] for i in indices if i < len(news_list)][:10]
    except Exception as e:
        print(f"  ❌ AI 분석 오류: {e}")
        return news_list[:10]


def split_message(message: str, max_length: int = 4000) -> list:
    """긴 메시지를 줄 단위로 나눠서 여러 조각으로 분할"""
    lines = message.split("\n")
    chunks, current_chunk = [], ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.rstrip("\n"))
            current_chunk = line + "\n"

    if current_chunk:
        chunks.append(current_chunk.rstrip("\n"))

    return chunks


def send_telegram_message(message: str):
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
                print(f"  ✅ [{i}/{len(chunks)}] 텔레그램 전송 성공!")
            else:
                print(f"  ❌ [{i}/{len(chunks)}] 전송 실패: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"  ❌ [{i}/{len(chunks)}] 전송 에러: {e}")


def main():
    today = datetime.now().strftime('%Y-%m-%d')

    # README용 마크다운 리포트
    report  = f"# 🗞️ AI 선정 오늘의 핵심 뉴스 ({today})\n\n"
    report += "> 제미나이(Gemini) AI가 여러 국내외 매체에서 수집한 뉴스 중 가장 중요한 이슈만 선별했습니다.\n\n"

    # 텔레그램용 텍스트
    telegram_text = f"🚀 *오늘의 AI 선정 뉴스 ({today})*\n\n"

    for category, urls in NEWS_SOURCES.items():
        print(f"\n[{category}] 데이터 수집 중... (소스 {len(urls)}개)")
        raw_news = fetch_news(urls)
        print(f"  📥 수집된 뉴스: {len(raw_news)}건 → AI 분석 시작")
        top_news = filter_news_with_gemini(category, raw_news)

        # README용
        report += f"## 📌 {category} Top 10\n"
        for i, news in enumerate(top_news):
            report += f"{i+1}. [{news['title']}]({news['link']})\n"
        report += "\n---\n"

        # 텔레그램용
        telegram_text += f"📌 *{category} Top 10*\n"
        for i, news in enumerate(top_news):
            telegram_text += f"{i+1}. [{news['title']}]({news['link']})\n"
        telegram_text += "\n"

    # 1. README.md 파일로 저장
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\n📄 뉴스 리포트(README.md) 생성 완료!")

    # 2. 텔레그램으로 전송
    send_telegram_message(telegram_text)


if __name__ == "__main__":
    main()
