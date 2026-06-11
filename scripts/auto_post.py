import os
import json
import requests
from datetime import datetime

# ── 환경변수 ──────────────────────────────────────────
GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
WP_CLIENT_ID     = os.environ["WP_CLIENT_ID"]
WP_CLIENT_SECRET = os.environ["WP_CLIENT_SECRET"]
WP_AUTH_CODE     = os.environ.get("WP_AUTH_CODE", "")
WP_ACCESS_TOKEN  = os.environ.get("WP_ACCESS_TOKEN", "")
WP_SITE          = "wellnesslifeguide.wordpress.com"

# ── 카테고리 정의 ──────────────────────────────────────
CATEGORIES = [
    {"name": "자동 수익 & 투자", "prompt": "파이어족, ETF 적립식 투자, 배당주 등 초보도 따라할 수 있는 자동 수익 투자법. 실제 종목명/ETF명 포함. 검색 키워드: 배당투자, ETF추천, 적립식투자, 파이어족"},
    {"name": "초간단 시사", "prompt": "국내외 경제·정치·사회 이슈를 일반인이 3분 안에 이해할 수 있게 설명. 최근 뉴스 흐름 반영. 검색 키워드: 경제뉴스, 시사상식, 금리, 환율"},
    {"name": "웰니스 & 자기관리", "prompt": "최신 웰니스 트렌드(수면, 루틴, 번아웃, 식단 등)를 쉽게 설명하고 바로 적용 가능한 실용 가이드. 검색 키워드: 웰니스, 자기관리, 번아웃, 수면루틴"},
    {"name": "2030 핫플 여행", "prompt": "20~30대가 좋아하는 국내 핫플레이스, 감성 카페, 여행 코스 소개. SNS에서 뜨는 곳 위주. 검색 키워드: 국내여행, 핫플레이스, 감성카페, 당일치기"},
    {"name": "철학 기반 자기계발", "prompt": "니체, 공자, 스토아 철학 등 고대~현대 철학/사상을 중학생도 이해하는 수준으로 현대 실생활에 적용하는 자기계발 칼럼. 검색 키워드: 자기계발, 철학, 니체, 스토아철학, 인간관계"}
]

# ── 액세스 토큰 확보 ───────────────────────────────────
def get_access_token():
    # 이미 토큰이 있으면 그대로 사용
    if WP_ACCESS_TOKEN:
        print("✅ 기존 액세스 토큰 사용")
        return WP_ACCESS_TOKEN

    # 없으면 auth code로 교환
    if not WP_AUTH_CODE:
        raise RuntimeError("WP_ACCESS_TOKEN 또는 WP_AUTH_CODE 둘 중 하나는 필요합니다.")

    print("🔄 auth code로 토큰 교환 중...")
    res = requests.post("https://public-api.wordpress.com/oauth2/token", data={
        "client_id":     WP_CLIENT_ID,
        "client_secret": WP_CLIENT_SECRET,
        "code":          WP_AUTH_CODE,
        "grant_type":    "authorization_code",
        "redirect_uri":  "https://localhost",
    })
    if res.status_code != 200:
        print("❌ 토큰 교환 실패:", res.text)
        res.raise_for_status()

    token = res.json()["access_token"]
    print("=" * 60)
    print("🎉 토큰 발급 성공! 아래 값을 GitHub Secret에 저장하세요.")
    print("   Secret 이름: WP_ACCESS_TOKEN")
    print("   값:")
    print(token)
    print("=" * 60)
    return token

# ── Gemini API로 글 생성 ───────────────────────────────
def generate_post(category):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = f"""너는 검색 트래픽과 수익을 만들어내는 한국어 블로그 운영 AI다.
오늘({today}) '{category['name']}' 카테고리 블로그 글 1개를 작성해라.
카테고리 설명: {category['prompt']}
규칙: 중학생도 이해 가능, AI 티 금지, 700~1000자, HTML 형식(h2/p/ul), SEO 키워드 3~5회, 제목은 숫자/궁금증 유발
반드시 아래 JSON만 응답 (다른 말 금지):
{{"title": "제목", "content": "HTML본문", "tags": ["태그1","태그2","태그3"]}}"""

    import time
    for attempt in range(4):
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]}
        )
        if res.status_code == 200:
            break
        print(f"     ⏳ 재시도 {attempt+1}/4 (상태 {res.status_code})")
        time.sleep(10)
    res.raise_for_status()
    text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
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
            "title": post_data["title"],
            "content": post_data["content"],
            "status": "publish",
            "categories": category["name"],
            "tags": ",".join(post_data.get("tags", [])),
        }
    )
    res.raise_for_status()
    return res.json()["URL"]

# ── 메인 실행 ──────────────────────────────────────────
def main():
    print(f"🚀 자동 발행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    token = get_access_token()

    for cat in CATEGORIES:
        try:
            print(f"  ✍️  [{cat['name']}] 글 생성 중...")
            post = generate_post(cat)
            url = publish_post(token, cat, post)
            print(f"  ✅ 발행 완료: {post['title']}")
            print(f"     {url}")
        except Exception as e:
            print(f"  ❌ [{cat['name']}] 오류: {e}")

    print("🎉 작업 완료!")

if __name__ == "__main__":
    main()
