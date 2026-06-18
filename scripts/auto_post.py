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

MONTHS = {m: i+1 for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])}

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

# ── 기사 발행일 파싱 ───────────────────────────────────
def parse_pubdate(raw):
    if not raw:
        return None
    raw = raw.strip()
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})", raw)
    if m:
        day, mon, year = int(m.group(1)), MONTHS.get(m.group(2), 0), m.group(3)
        if mon:
            return f"{year}년 {mon}월 {day}일", f"{year}-{mon:02d}-{int(day):02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{y}년 {mo}월 {d}일", f"{y}-{mo:02d}-{d:02d}"
    return None

# ── RSS 링크 추출 (정제) ───────────────────────────────
def extract_link(item_text):
    """RSS item에서 URL을 정확하게 추출하고 정제"""
    # 1순위: Atom <link href="...">
    m = re.search(r'<link[^>]+href=["\']([^"\'>\s]+)["\']', item_text, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
        if url.startswith("http"):
            return url

    # 2순위: RSS <link>...</link> (CDATA 제거, 공백 제거)
    m = re.search(r"<link[^>]*>(.*?)</link>", item_text, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1)
        raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.DOTALL)
        raw = re.sub(r"<[^>]+>", "", raw).strip()
        if raw.startswith("http"):
            return raw

    # 3순위: <guid isPermaLink="true">...</guid>
    m = re.search(r'<guid[^>]*isPermaLink=["\']true["\'][^>]*>(.*?)</guid>', item_text, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        if raw.startswith("http"):
            return raw

    return ""

# ── 트렌드 크롤링 (제목 + URL + 날짜) ──────────────────
def crawl_trends(feeds, feed_kw):
    headers = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    collected = []
    for url in feeds:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            items = re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", r.text, re.DOTALL | re.IGNORECASE)
            for item in items[:12]:
                tm = re.search(r"<title[^>]*>(.*?)</title>", item, re.DOTALL | re.IGNORECASE)
                if not tm:
                    continue
                title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", tm.group(1), flags=re.DOTALL)
                title = re.sub(r"<[^>]+>", "", title).strip()
                if not (8 < len(title) < 140):
                    continue

                link = extract_link(item)

                dm = re.search(r"<(?:pubDate|published|updated|dc:date)[^>]*>(.*?)</(?:pubDate|published|updated|dc:date)>",
                               item, re.DOTALL | re.IGNORECASE)
                date_info = parse_pubdate(dm.group(1)) if dm else None
                date_kr = date_info[0] if date_info else None

                collected.append({"title": title, "link": link, "date": date_kr})
        except Exception:
            continue

    filtered = [c for c in collected if any(kw in c["title"].lower() for kw in feed_kw)]
    result = filtered if filtered else collected
    seen, uniq = set(), []
    for c in result:
        if c["title"] not in seen:
            seen.add(c["title"]); uniq.append(c)
    return uniq[:10]

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

# ── 발행 이력에서 다룬 소재 추출 ───────────────────────
def extract_covered_topics(category_name, posted_titles):
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
def generate_post(category, posted_titles, covered_topics, trends):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    posted_text  = "\n".join(f"- {t}" for t in posted_titles[-20:]) if posted_titles else "없음"
    covered_text = ", ".join(covered_topics) if covered_topics else "없음"

    # 트렌드를 인덱스 포함해서 제시 → Gemini가 몇 번 기사를 참고했는지 반환하게
    if trends:
        lines = []
        for i, c in enumerate(trends):
            d = f" (발행일: {c['date']})" if c.get("date") else ""
            lines.append(f"[{i}] {c['title']}{d}")
        trend_text = "\n".join(lines)
    else:
        trend_text = "없음"

    prompt = f"""오늘은 {today}입니다. '{category['name']}' 블로그 글을 작성해 주세요.
방향: {category['direction']}

[최신 트렌드 — 이 중 하나를 소재로 적극 활용]
{trend_text}

[날짜 표현 규칙 — 중요]
- 기사를 소재로 쓸 때, 위에 표시된 '발행일'을 정확히 반영하세요. (예: "6월 14일 발표된 보도에 따르면")
- 오늘 날짜로 착각해서 쓰지 마세요. 기사가 며칠 전 것이면 그 날짜를 그대로 쓰세요.
- 발행일 정보가 없는 소재는 무리하게 날짜를 지어내지 마세요.

[이미 다룬 핵심 소재 — 절대 다시 쓰지 말 것]
{covered_text}

[이미 발행한 제목 — 비슷한 각도 금지]
{posted_text}

[소재 선정 규칙]
- 위 '이미 다룬 핵심 소재'의 인물·사상·이론·지역·종목은 이번 글에서 다루지 마세요.
- 매번 신선하고 구체적인 새 주제를 잡으세요.

[말투]
- 정중한 존댓말(~합니다, ~입니다, ~요)로 일관되게. 반말 금지.
- 딱딱하지 않게, 독자에게 말 거는 것처럼 부드럽게.

[글 구조]
- 두괄식: 도입부 첫 문장에 핵심 답/요약
- 소제목마다 하나의 요점만
- "결론적으로", "지금 바로 시작하세요" 같은 뻔한 마무리 금지

[형식]
- 길이: 800~1100자
- HTML: 소제목 <h2>, 문단 <p>, 필요시 <ul><li>
- 키워드는 글에 자연스럽게 녹일 것. 별도 나열 금지.
- 제목은 본문에 다시 쓰지 말 것

[참고 기사 반환 — 중요]
- 위 트렌드 목록에서 실제로 이 글의 소재로 활용한 기사의 인덱스 번호([0], [1] 등)를 "source_index" 필드에 넣어 주세요.
- 트렌드를 전혀 활용하지 않은 경우 source_index는 -1로 하세요.

반드시 아래 JSON만 응답 (다른 말 절대 금지):
{{"title": "제목", "content": "HTML본문", "tags": ["태그1","태그2","태그3"], "source_index": 0}}"""

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

# ── 출처 링크 HTML 생성 (실제 사용 기사만) ────────────
def build_sources_html(post_data, trends):
    """Gemini가 실제로 참고한 기사 하나만 정확하게 달기"""
    idx = post_data.get("source_index", -1)
    if idx == -1 or not isinstance(idx, int):
        return ""
    if idx < 0 or idx >= len(trends):
        return ""
    article = trends[idx]
    link = article.get("link", "").strip()
    title = article.get("title", "").strip()
    if not link or not link.startswith("http"):
        return ""
    date = f" ({article['date']})" if article.get("date") else ""
    html = (
        '\n<hr/>\n'
        '<p><strong>참고 자료</strong></p>\n'
        '<ul>\n'
        f'  <li><a href="{link}" target="_blank" rel="noopener">{title}</a>{date}</li>\n'
        '</ul>\n'
    )
    return html

# ── WordPress에 발행 ───────────────────────────────────
def publish_post(token, category, post_data, sources_html):
    content = post_data["content"] + sources_html
    res = requests.post(
        f"https://public-api.wordpress.com/rest/v1.1/sites/{WP_SITE}/posts/new",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title":      post_data["title"],
            "content":    content,
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
            if trends:
                for i, t in enumerate(trends[:5]):
                    link_preview = t['link'][:60] if t['link'] else '링크없음'
                    print(f"       [{i}] {t['title'][:50]} | {link_preview}")

            posted_titles = posted.get(name, [])
            print(f"  🧠 [{name}] 기존 소재 분석 중...")
            covered = extract_covered_topics(name, posted_titles)
            if covered:
                print(f"     회피할 소재: {', '.join(covered[:8])}")

            print(f"  ✍️  [{name}] 글 생성 중...")
            post = generate_post(cat, posted_titles, covered, trends)

            src_idx = post.get("source_index", -1)
            print(f"     참고 기사 인덱스: {src_idx}")

            sources_html = build_sources_html(post, trends)
            if sources_html:
                print(f"     참고 링크 첨부: {trends[src_idx]['title'][:50]}")
            else:
                print(f"     참고 링크 없음 (트렌드 미활용 또는 링크 없음)")

            url = publish_post(token, cat, post, sources_html)
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
