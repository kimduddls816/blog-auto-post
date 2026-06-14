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

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ── 카테고리 정의 ──────────────────────────────────────
CATEGORIES = [
    {
        "name": "자동 수익 투자",
        "direction": "파이어족, ETF 적립식 투자, 배당주 등 초보도 따라할 수 있는 자동 수익 투자법. 실제 종목명/ETF명 포함.",
        "feeds": [
            "https://www.investing.com/rss/news_25.rss",
            "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            "https://www.etf.com/rss.xml",
        ],
        "feed_kw": ["etf", "dividend", "invest", "stock", "retire", "fund", "portfolio", "배당", "투자"],
    },
    {
        "name": "초간단 시사",
        "direction": "국내외 경제·정치·사회 이슈를 일반인이 3분 안에 이해할 수 있게 설명. 최근 뉴스 흐름 반영.",
        "feeds": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            "https://rss.cnn.com/rss/edition_world.rss",
        ],
        "feed_kw": ["economy", "korea", "election", "rate", "market", "trade", "policy", "war", "ai"],
    },
    {
        "name": "웰니스 자기관리",
        "direction": "최신 웰니스 트렌드(수면, 루틴, 번아웃, 식단 등)를 쉽게 설명하고 바로 적용 가능한 실용 가이드.",
        "feeds": [
            "https://www.healthline.com/rss/news",
            "https://feeds.feedburner.com/MindBodyGreen",
            "https://www.medicalnewstoday.com/rss/medical-news-today.xml",
        ],
        "feed_kw": ["sleep", "stress", "mental", "anxiety", "wellness", "habit", "diet", "burnout", "mindful"],
    },
    {
        "name": "2030 핫플 여행",
        "direction": "20~30대가 좋아하는 국내 핫플레이스, 감성 카페, 여행 코스 소개. SNS에서 뜨는 곳 위주.",
        "feeds": [
            "https://www.lonelyplanet.com/news/feed",
            "https://www.cntraveler.com/feed/rss",
            "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        ],
        "feed_kw": ["travel", "trip", "cafe", "city", "korea", "seoul", "weekend", "destination"],
    },
    {
        "name": "철학 기반 자기계발",
        "direction": "니체, 공자, 스토아 철학 등 고대~현대 철학/사상을 중학생도 이해하는 수준으로 현대 실생활에 적용하는 자기계발 칼럼.",
        "feeds": [
            "https://aeon.co/feed.rss",
            "https://dailystoic.com/feed/",
            "https://www.brainpickings.org/feed/",
        ],
        "feed_kw": ["philosophy", "stoic", "wisdom", "mind", "meaning", "habit", "self", "life", "growth"],
    },
]

# ── 발행 이력 관리 ─────────────────────────────────────
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_posted(data):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 트렌드 크롤링 (다중 소스 + 강화된 파싱) ───────────
def crawl_trends(feeds, feed_kw):
    headers = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    collected = []
    for url in feeds:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            # <item> 또는 <entry> 내부의 <title> 추출
            items = re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", r.text, re.DOTALL | re.IGNORECASE)
            for item in items[:12]:
                m = re.search(r"<title[^>]*>(.*?)</title>", item, re.DOTALL | re.IGNORECASE)
                if not m:
                    continue
                title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.DOTALL)
                title = re.sub(r"<[^>]+>", "", title).strip()
                if 8 < len(title) < 140:
                    collected.append(title)
        except Exception:
            continue
    # 키워드 필터 (있으면 우선, 없으면 전체에서)
    filtered = [t for t in collected if any(kw in t.lower() for kw in feed_kw)]
    result = filtered if filtered else collected
    # 중복 제거
    seen, uniq = set(), []
    for t in result:
        if t not in seen:
            seen.add(t); uniq.append(t)
    return uniq[:12]

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

# ── 발행 이력에서 다룬 소재 추출 (Gemini) ──────────────
def extract_covered_topics(category_name, posted_titles):
    """이미 발행한 제목들에서 핵심 소재(인물/사상/지역/종목 등)를 뽑아 회피 목록 생성"""
    if not posted_titles:
        return []
    titles_text = "\n".join(f"- {t}" for t in posted_titles[-30:])
    prompt = f"""다음은 '{category_name}' 카테고리에 이미 발행한 글 제목들입니다.

{titles_text}

이 제목들에서 핵심 소재(다룬 인물·사상·이론·지역·종목·개념 등)를 추출해 주세요.
앞으로 새 글을 쓸 때 이것들과 겹치지 않게 하려는 목적입니다.

JSON 배열로만 응답 (다른 말 없이):
["소재1", "소재2", "소재3"]"""
    try:
        res = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=40
        )
        if res.status_code == 200:
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            items = json.loads(text)
            if isinstance(items, list):
                return [str(x) for x in items]
    except Exception as e:
        print(f"     ⚠️ 소재 추출 실패(무시): {e}")
    return []

# ── Gemini로 글 생성 ───────────────────────────────────
def generate_post(category, posted_titles, covered_topics, trend_hints):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    posted_text  = "\n".join(f"- {t}" for t in posted_titles[-20:]) if posted_titles else "없음"
    covered_text = ", ".join(covered_topics) if covered_topics else "없음"
    trend_text   = "\n".join(f"- {t}" for t in trend_hints) if trend_hints else "없음"

    prompt = f"""오늘({today}) '{category['name']}' 블로그 글을 써라.
방향: {category['direction']}

[최신 트렌드 — 이 중 하나를 소재로 적극 활용하라]
{trend_text}

[이미 다룬 핵심 소재 — 절대 다시 쓰지 말 것]
{covered_text}

[이미 발행한 제목 — 비슷한 각도 금지]
{posted_text}

[소재 선정 규칙 — 매우 중요]
- 위 '이미 다룬 핵심 소재'에 나온 인물·사상·이론·지역·종목은 이번 글에서 절대 다루지 마라.
- 예: 철학 카테고리에서 이미 '니체', '스토아'를 다뤘다면 이번엔 공자, 노자, 사르트르, 칸트, 아들러 등 완전히 다른 사상가/관점으로.
- 예: 투자 카테고리에서 이미 'S&P500 ETF'를 다뤘다면 이번엔 배당성장주, 채권, 리츠 등 다른 주제로.
- 매번 신선하고 구체적인 새 주제를 잡아라.

[말투 — 반드시 지킬 것]
- 전체적으로 정중한 존댓말(~합니다, ~입니다, ~요)로 일관되게
- 반말("~다", "~거야") 절대 금지
- 딱딱하지 않게, 독자에게 말 거는 것처럼 부드럽게

[글 구조]
- 두괄식: 제목에서 핵심 궁금증 던지고, 도입부 첫 문장에 바로 핵심 답 또는 요약
- 소제목마다 하나의 요점만 명확하게
- 마무리는 "결론적으로", "지금 바로 시작하세요" 같은 뻔한 표현 금지, 여운 있게

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
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 1.0}},
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
            name = cat["name"]
            print(f"\n  🔍 [{name}] 트렌드 수집 중...")
            trends = crawl_trends(cat["feeds"], cat["feed_kw"])
            print(f"     트렌드 {len(trends)}개 수집")

            posted_titles = posted.get(name, [])
            print(f"  🧠 [{name}] 기존 소재 분석 중...")
            covered = extract_covered_topics(name, posted_titles)
            if covered:
                print(f"     회피할 소재: {', '.join(covered[:8])}")

            print(f"  ✍️  [{name}] 글 생성 중...")
            post = generate_post(cat, posted_titles, covered, trends)

            url = publish_post(token, cat, post)
            print(f"  ✅ 발행 완료: {post['title']}")
            print(f"     {url}")

            posted.setdefault(name, []).append(post["title"])
            posted[name] = posted[name][-50:]

            success += 1
            time.sleep(3)

        except Exception as e:
            print(f"  ❌ [{cat['name']}] 오류: {e}")

    save_posted(posted)
    print(f"\n🎉 완료! {success}/{len(CATEGORIES)}개 발행")

if __name__ == "__main__":
    main()
