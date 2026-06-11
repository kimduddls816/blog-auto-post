import os
import json
import time
import urllib.parse
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
    {"name": "자동 수익 투자", "prompt": "파이어족, ETF 적립식 투자, 배당주 등 초보도 따라할 수 있는 자동 수익 투자법. 실제 종목명/ETF명 포함. 검색 키워드: 배당투자, ETF추천, 적립식투자, 파이어족", "img": "money investment finance savings, minimal clean photography"},
    {"name": "초간단 시사", "prompt": "국내외 경제·정치·사회 이슈를 일반인이 3분 안에 이해할 수 있게 설명. 최근 뉴스 흐름 반영. 검색 키워드: 경제뉴스, 시사상식, 금리, 환율", "img": "newspaper economy news world, modern editorial photography"},
    {"name": "웰니스 자기관리", "prompt": "최신 웰니스 트렌드(수면, 루틴, 번아웃, 식단 등)를 쉽게 설명하고 바로 적용 가능한 실용 가이드. 검색 키워드: 웰니스, 자기관리, 번아웃, 수면루틴", "img": "wellness self care calm morning routine, soft natural light"},
    {"name": "2030 핫플 여행", "prompt": "20~30대가 좋아하는 국내 핫플레이스, 감성 카페, 여행 코스 소개. SNS에서 뜨는 곳 위주. 검색 키워드: 국내여행, 핫플레이스, 감성카페, 당일치기", "img": "aesthetic korea cafe travel trip, instagram style photography"},
    {"name": "철학 기반 자기계발", "prompt": "니체, 공자, 스토아 철학 등 고대~현대 철학/사상을 중학생도 이해하는 수준으로 현대 실생활에 적용하는 자기계발 칼럼. 검색 키워드: 자기계발, 철학, 니체, 스토아철학, 인간관계", "img": "philosophy books thinking quiet study, warm moody photography"}
]

GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

# ── 액세스 토큰 확보 ───────────────────────────────────
def get_access_token():
    if WP_ACCESS_TOKEN:
        print("✅ 기존 액세스 토큰 사용")
        return WP_ACCESS_TOKEN
    if not WP_AUTH_CODE:
        raise RuntimeError("WP_ACCESS_TOKEN 또는 WP_AUTH_CODE 둘 중 하나는 필요합니다.")
    print("🔄 auth code로 토큰 교환 중...")
    res = requests.post("https://public-api.wordpress.com/oauth2/token", data={
        "client_id": WP_CLIENT_ID, "client_secret": WP_CLIENT_SECRET,
        "code": WP_AUTH_CODE, "grant_type": "authorization_code",
        "redirect_uri": "https://localhost",
    })
    if res.status_code != 200:
        print("❌ 토큰 교환 실패:", res.text); res.raise_for_status()
    token = res.json()["access_token"]
    print("=" * 60)
    print("🎉 토큰 발급 성공! GitHub Secret에 WP_ACCESS_TOKEN 으로 저장:")
    print(token)
    print("=" * 60)
    return token

# ── 글 주제에 맞는 이미지 URL 생성 (Pollinations, 키 불필요) ──
def make_image_html(category, title):
    # 제목+카테고리 키워드로 이미지 생성 프롬프트 구성
    prompt = f"{category['img']}, no text, no words"
    encoded = urllib.parse.quote(prompt)
    img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1200&height=630&nologo=true"
    return f'<figure><img src="{img_url}" alt="{title}" style="width:100%;border-radius:12px;"/></figure>\n'

# ── Gemini API로 글 생성 (사람 티 나는 스타일) ──────────
def generate_post(category):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    prompt = f"""너는 직접 블로그를 운영하는 30대 한국인 작성자다. AI가 아니라 진짜 사람처럼 써라.
오늘({today}) '{category['name']}' 주제로 블로그 글 하나를 써라.
주제 설명: {category['prompt']}

[사람처럼 쓰는 규칙 — 반드시 지켜라]
- 가끔 짧은 문장과 긴 문장을 섞어라. 리듬이 단조롭지 않게.
- 개인적인 경험이나 솔직한 생각을 한두 문장 넣어라. (예: "사실 나도 처음엔 헷갈렸다")
- "~할 수 있습니다", "~입니다" 만 반복하지 말고 "~더라", "~거든요", "~인 것 같아요" 같은 자연스러운 말투도 섞어라.
- 완벽하게 정돈된 목록 나열식은 피해라. 글이 대화처럼 흐르게.
- 뻔한 마무리("결론적으로", "지금 바로 시작하세요") 금지. 여운 있게 끝내라.
- 과장·광고 느낌 금지. 솔직하고 담백하게.
- 중학생도 이해할 만큼 쉽게.

[형식]
- 길이: 800~1100자
- HTML 형식: 소제목은 <h2>, 문단은 <p>, 필요하면 <ul><li>. (제목은 본문에 다시 쓰지 마)
- SEO: 핵심 키워드 3~4회 자연스럽게.
- 제목: 궁금증을 자극하되 낚시성·과장 없이.

반드시 아래 JSON만 응답 (다른 말 절대 금지):
{{"title": "제목", "content": "HTML본문", "tags": ["태그1","태그2","태그3"]}}"""

    last_err = None
    for model in GEMINI_MODELS:
        for attempt in range(3):
            try:
                res = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=60
                )
                if res.status_code == 200:
                    text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    return json.loads(text)
                if res.status_code in (429, 500, 502, 503):
                    last_err = f"{model} 상태 {res.status_code}"
                    print(f"     ⏳ {model} 재시도 {attempt+1}/3 (상태 {res.status_code})")
                    time.sleep(8); continue
                last_err = f"{model} 상태 {res.status_code}"
                print(f"     ↪ {model} 사용 불가 (상태 {res.status_code}), 다음 모델")
                break
            except Exception as e:
                last_err = str(e); time.sleep(5)
    raise RuntimeError(f"모든 모델 실패: {last_err}")

# ── WordPress에 발행 ───────────────────────────────────
def publish_post(token, category, post_data):
    # 글 맨 위에 이미지 삽입
    image_html = make_image_html(category, post_data["title"])
    full_content = image_html + post_data["content"]

    res = requests.post(
        f"https://public-api.wordpress.com/rest/v1.1/sites/{WP_SITE}/posts/new",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": post_data["title"],
            "content": full_content,
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
    success = 0
    for cat in CATEGORIES:
        try:
            print(f"  ✍️  [{cat['name']}] 글 생성 중...")
            post = generate_post(cat)
            url = publish_post(token, cat, post)
            print(f"  ✅ 발행 완료: {post['title']}")
            print(f"     {url}")
            success += 1
            time.sleep(3)
        except Exception as e:
            print(f"  ❌ [{cat['name']}] 오류: {e}")
    print(f"🎉 작업 완료! {success}/{len(CATEGORIES)}개 발행")

if __name__ == "__main__":
    main()
