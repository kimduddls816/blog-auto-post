import os
import json
import requests
from datetime import datetime

# ── 환경변수 ──────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
WP_CLIENT_ID     = os.environ["WP_CLIENT_ID"]
WP_CLIENT_SECRET = os.environ["WP_CLIENT_SECRET"]
WP_USERNAME      = os.environ["WP_USERNAME"]
WP_PASSWORD      = os.environ["WP_PASSWORD"]
WP_SITE          = "wellnesslifeguide.wordpress.com"

# ── 카테고리 정의 ──────────────────────────────────────
CATEGORIES = [
    {
        "id": 1,
        "name": "자동 수익 & 투자",
        "prompt": "파이어족, ETF 적립식 투자, 배당주 등 초보도 따라할 수 있는 자동 수익 투자법을 다룬다. 실제 종목명/ETF명 포함. 검색 키워드: 배당투자, ETF추천, 적립식투자, 파이어족"
    },
    {
        "id": 2,
        "name": "초간단 시사",
        "prompt": "국내외 경제·정치·사회 이슈를 일반인이 3분 안에 이해할 수 있게 설명한다. 최근 뉴스 흐름 반영. 검색 키워드: 경제뉴스, 시사상식, 금리, 환율"
    },
    {
        "id": 3,
        "name": "웰니스 & 자기관리",
        "prompt": "최신 웰니스 트렌드(수면, 루틴, 번아웃, 식단 등)를 쉽게 설명하고 일반인이 바로 적용할 수 있는 실용 가이드를 제공한다. 검색 키워드: 웰니스, 자기관리, 번아웃, 수면루틴"
    },
    {
        "id": 4,
        "name": "2030 핫플 여행",
        "prompt": "20~30대가 좋아하는 국내 핫플레이스, 감성 카페, 여행 코스를 소개한다. 최근 SNS에서 뜨는 곳 위주. 검색 키워드: 국내여행, 핫플레이스, 감성카페, 당일치기"
    },
    {
        "id": 5,
        "name": "철학 기반 자기계발",
        "prompt": "니체, 공자, 스토아 철학 등 고대~현대 철학/사상을 중학생도 이해하는 수준으로 현대 실생활에 적용하는 자기계발 칼럼을 쓴다. 검색 키워드: 자기계발, 철학, 니체, 스토아철학, 인간관계"
    }
]

# ── WordPress 토큰 발급 ────────────────────────────────
def get_wp_token():
    res = requests.post("https://public-api.wordpress.com/oauth2/token", data={
        "client_id":     WP_CLIENT_ID,
        "client_secret": WP_CLIENT_SECRET,
        "grant_type":    "password",
        "username":      WP_USERNAME,
        "password":      WP_PASSWORD,
    })
    res.raise_for_status()
    return res.json()["access_token"]

# ── Claude API로 글 생성 ───────────────────────────────
def generate_post(category):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    system_prompt = """너는 검색 트래픽과 수익을 만들어내는 한국어 블로그 운영 AI다.
규칙:
- 중학생도 이해할 수 있는 쉬운 말
- AI 티 절대 금지 (사람이 쓴 것처럼)
- 과장 없이 현실적
- 구조: Hook → 핵심 설명 → 실전 적용 → 한줄 결론
- 길이: 700~1000자 (집중력 유지되는 분량)
- SEO: 핵심 키워드 3~5회 자연스럽게 삽입
- HTML 형식으로 출력 (h2, p, ul 태그 사용)
- 제목은 숫자/결과 강조/궁금증 유발
- 응답은 JSON으로만: {"title": "...", "content": "...", "tags": ["태그1","태그2","태그3"]}"""

    user_prompt = f"""오늘({today}) 날짜 기준으로 '{category['name']}' 카테고리 블로그 글 1개를 작성해라.
카테고리 설명: {category['prompt']}
지금 검색량 높을 만한 트렌디한 주제를 스스로 선정해서 써라."""

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }
    )
    res.raise_for_status()
    text = res.json()["content"][0]["text"].strip()
    
    # JSON 파싱
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    return json.loads(text)

# ── WordPress에 발행 ───────────────────────────────────
def publish_post(token, category, post_data):
    res = requests.post(
        f"https://public-api.wordpress.com/rest/v1.1/sites/{WP_SITE}/posts/new",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title":      post_data["title"],
            "content":    post_data["content"],
            "status":     "publish",
            "categories": category["name"],
            "tags":       ",".join(post_data.get("tags", [])),
        }
    )
    res.raise_for_status()
    return res.json()["URL"]

# ── 메인 실행 ──────────────────────────────────────────
def main():
    print(f"🚀 자동 발행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    token = get_wp_token()
    
    for cat in CATEGORIES:
        try:
            print(f"  ✍️  [{cat['name']}] 글 생성 중...")
            post = generate_post(cat)
            url  = publish_post(token, cat, post)
            print(f"  ✅ 발행 완료: {post['title']}")
            print(f"     {url}")
        except Exception as e:
            print(f"  ❌ [{cat['name']}] 오류: {e}")
    
    print("🎉 오늘 5개 발행 완료!")

if __name__ == "__main__":
    main()
