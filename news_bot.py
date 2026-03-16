import feedparser
import os
from google import genai
from datetime import datetime

# API 키 설정 (GitHub Secrets)
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

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
    # 뉴스 제목 리스트 생성
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
            model="gemini-3-flash", # 2026년 기준 최적의 속도를 내는 모델
            contents=prompt
        )
        
        # 번호 파싱
        selected_text = response.text.strip()
        indices = [int(i.strip()) for i in selected_text.split(",") if i.strip().isdigit()]
        
        # 상위 20개 리턴
        return [news_list[i] for i in indices if i < len(news_list)][:20]
    except Exception as e:
        print(f"Error during AI analysis: {e}")
        return news_list[:20] # 에러 발생 시 단순 상위 20개 반환

def main():
    report = f"# 🗞️ AI 선정 오늘의 핵심 뉴스 ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    report += "> 제미나이(Gemini) AI가 대량의 뉴스 중 가장 중요한 이슈만 선별했습니다.\n\n"
    
    for category, url in NEWS_SOURCES.items():
        print(f"[{category}] 데이터 수집 및 분석 중...")
        raw_news = fetch_news(url)
        top_news = filter_news_with_gemini(category, raw_news)
        
        report += f"## 📌 {category} Top 20\n"
        for i, news in enumerate(top_news):
            report += f"{i+1}. [{news['title']}]({news['link']})\n"
        report += "\n---\n"

    # README.md 파일로 저장
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("뉴스 리포트 생성 완료!")

if __name__ == "__main__":
    main()