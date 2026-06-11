import os
import re
import json
import time
import requests
from datetime import datetime

# ── 환경변수 ──────────────────────────────────────────
GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
WP_CLIENT_ID     = os.environ["WP_CLIENT_ID"]
WP_CLIENT_SECRET = os.environ["WP_CLIENT_SECRET"]
WP_AUTH_CODE     = os.environ.get("WP_AUTH_CODE", "")
WP_ACCESS_TOKEN  = os.environ.get("WP_ACCESS_TOKEN", "")
WP_SITE          = "wellnesslifeguide.wordpress.com"

POSTED_FILE   = "posted_topics.json"
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

# ── 카테고리 정의 ──────────────────────────────────────
CATEGORIES = [
    {
        "name": "자동 수익 투자",
        "direction": "파이어족, ETF 적립식 투자, 배당주 등 초보도 따라할 수 있는 자동 수익 투자법. 실제 종목명/ETF명 포함.",
        "trend_kw": ["ETF", "배당", "투자", "파이어", "적립식", "금리", "주식", "재테크"]
    },
    {
        "name": "초간단 시사",
        "direction": "국내외 경제·정치·사회 이슈를 일반인이 3분 안에 이해할 수 있게 설명. 최근 뉴스 흐름 반영.",
        "trend_kw": ["경제", "금리", "환율", "뉴스", "정치", "사회", "시사", "물가"]
    },
    {
        "name": "웰니스 자기관리",
        "direction": "최신 웰니스 트렌드(수면, 루틴, 번아웃, 식단 등)를 쉽게 설명하고 바로 적용 가능한 실용 가이드.",
        "trend_kw": ["wellness", "health", "sleep", "stress", "meditation", "건강", "수면", "번아웃", "웰니스"]
    },
    {
        "name": "2030 핫플 여행",
        "direction": "20~30대가 좋아하는 국내 핫플레이스, 감성 카페, 여행 코스 소개. SNS에서 뜨는 곳 위주.",
        "trend_kw": ["여행", "핫플", "카페", "국내여행", "당일치기", "감성", "맛집"]
    },
    {
        "name": "철학 기반 자기계발",
        "direction": "니체, 공자, 스토아 철학 등 고대~현대 철학/사상을 중학생도 이해하는 수준으로 현대 실생활에 적용하는 자기계발 칼럼.",
        "trend_kw": ["철학", "자기계발", "니체", "스토아", "인간관계", "성장", "동기"]
    },
]

# ── 발행 이력 관리 ─────────────────────────────────────
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 트렌드 크롤링 ─────────────────────────────────────
def crawl_trends(cat_kw):
    keywords = []
    sources = [
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR",
        "https://www.healthline.com/rss/news",
        "https://feeds.feedburner.com/MindBodyGreen",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Well.xml",
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in sources:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", r.text)
                if not titles:
                    titles = re.findall(r"<title>([^<]{10,100})</title>", r.text)
                for t in titles[:15]:
                    t = t.strip()
                    if any(kw.lower() in t.lower() for kw in cat_kw):
                        keywords.append(t)
        except Exception:
            pass
    return keywords[:15]

# ── 액세스 토큰 확보 ───────────────────────────────────
def get_access_token():
    if WP_ACCESS_TOKEN:
        print("✅ 기존 액세스 토큰 사용")
        return WP_ACCESS_TOKEN
    if not WP_AUTH_CODE:
        raise RuntimeError("WP_ACCESS_TOKEN 또는 WP_AUTH_CODE 필요")
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
    print("🎉 토큰 발급! GitHub Secret WP_ACCESS_TOKEN 에 저장:")
    print(token)
    print("=" * 60)
    return token

# ── Gemini로 글 생성 ───────────────────────────────────
def generate_post(category, posted_titles, trend_hints):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    posted_text = "\n".join(f"- {t}" for t in posted_titles[-20:]) if posted_titles else "없음"
    trend_text  = "\n".join(f"- {t}" for t in trend_hints) if trend_hints else "없음"

    prompt = f"""오늘({today}) '{category['name']}' 블로그 글을 써라.
방향: {category['direction']}

최신 트렌드 (소재로 참고):
{trend_text}

이미 발행한 제목 (비슷한 내용 금지):
{posted_text}

[말투 — 반드시 지킬 것]
- 전체적으로 정중한 존댓말 (~합니다, ~입니다, ~요) 로 일관되게
- 반말("~다", "~거야") 절대 금지
- 딱딱하지 않게, 독자에게 말 거는 것처럼 부드럽게

[글 구조 — 예시 참고]
- 두괄식: 제목에서 핵심 궁금증 던지고, 도입부 첫 문장에 바로 핵심 답변 또는 요약
- 소제목마다 하나의 요점만 명확하게
- 마무리는 "결론적으로", "지금 바로 시작하세요" 같은 뻔한 표현 금지, 여운 있게

[예시 글 스타일]
"인간관계, 왜 이렇게 어렵게 느껴질까요?
친구와의 오해, 가족과의 갈등... '인간관계'는 가장 중요하면서도 가장 큰 고민을 안겨줍니다.
1. 내가 바꿀 수 없는 것을 받아들이기 (스토아 철학의 지혜)
스토아 철학의 핵심은 통제할 수 있는 것과 없는 것을 명확히 구분하는 것입니다..."

[형식]
- 길이: 800~1100자
- HTML: 소제목 <h2>, 문단 <p>, 필요시 <ul><li>
- 키워드는 글 내용에 자연스럽게 녹여 쓸 것. 절대 별도 항목으로 나열하지 말 것.
- 제목은 본문에 다시 쓰지 말 것

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
                    last_err = f"{model} {res.status_code}"
                    print(f"     ⏳ {model} 재시도 {attempt+1}/3")
                    time.sleep(8); continue
                last_err = f"{model} {res.status_code}"
                print(f"     ↪ {model} 불가, 다음 모델")
                break
            except Exception as e:
                last_err = str(e); time.sleep(5)
    raise RuntimeError(f"모든 모델 실패: {last_err}")

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

# ── 메인 ──────────────────────────────────────────────
def main():
    print(f"🚀 자동 발행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    token = get_access_token()
    posted = load_posted()
    success = 0

    for cat in CATEGORIES:
        try:
            print(f"\n  🔍 [{cat['name']}] 트렌드 수집 중...")
            trends = crawl_trends(cat["trend_kw"])
            print(f"     트렌드 {len(trends)}개 수집")

            posted_titles = posted.get(cat["name"], [])
            print(f"  ✍️  [{cat['name']}] 글 생성 중...")
            post = generate_post(cat, posted_titles, trends)

            url = publish_post(token, cat, post)
            print(f"  ✅ 발행 완료: {post['title']}")
            print(f"     {url}")

            if cat["name"] not in posted:
                posted[cat["name"]] = []
            posted[cat["name"]].append(post["title"])
            posted[cat["name"]] = posted[cat["name"]][-50:]

            success += 1
            time.sleep(3)

        except Exception as e:
            print(f"  ❌ [{cat['name']}] 오류: {e}")

    save_posted(posted)
    print(f"\n🎉 완료! {success}/{len(CATEGORIES)}개 발행")

if __name__ == "__main__":
    main()
