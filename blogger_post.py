import os
import re
import json
import time
import random
import requests
from datetime import datetime

# ── 환경변수 ──────────────────────────────────────────
GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
BLOGGER_CLIENT_ID     = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOGGER_BLOG_ID       = os.environ["BLOGGER_BLOG_ID"]

POSTED_FILE   = "posted_topics_en.json"
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

MONTHS = {m: i+1 for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])}

# ── 카테고리 정의 ──────────────────────────────────────
CATEGORIES = [
    {
        "name": "Passive Income Investing",
        "label": "Passive Income Investing",
        "direction": "Beginner-friendly guides on FIRE movement, ETF investing, dividend stocks, and automated wealth building. Include real ticker names and ETF names.",
        "feeds": [
            "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            "https://feeds.feedburner.com/TheMoneyNinjas",
            "https://www.dividendgrowthinvestor.com/feeds/posts/default",
            "https://seekingalpha.com/feed.xml",
            "https://rss.app/feeds/etf-news.xml",
        ],
        "feed_kw": ["etf", "dividend", "invest", "stock", "retire", "fund", "portfolio", "yield", "passive", "income"],
    },
    {
        "name": "World News Simplified",
        "label": "World News Simplified",
        "direction": "Global economic, political and social issues explained in plain English that anyone can understand in 3 minutes. Reflect recent news trends.",
        "feeds": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.reuters.com/reuters/businessNews",
            "https://www.aljazeera.com/xml/rss/all.xml",
        ],
        "feed_kw": ["economy", "election", "rate", "market", "trade", "policy", "war", "ai", "crisis", "global"],
    },
    {
        "name": "Wellness and Self-Care",
        "label": "Wellness and Self-Care",
        "direction": "Latest wellness trends (sleep, routines, burnout, diet, mindfulness) explained simply with practical guides readers can apply immediately.",
        "feeds": [
            "https://www.healthline.com/rss/news",
            "https://www.medicalnewstoday.com/rss/medical-news-today.xml",
            "https://www.psychologytoday.com/us/articles/feed",
            "https://greatergood.berkeley.edu/feeds/news",
            "https://www.verywellmind.com/feeds/all",
        ],
        "feed_kw": ["sleep", "stress", "mental", "anxiety", "wellness", "habit", "diet", "burnout", "mindful", "therapy", "mood"],
    },
    {
        "name": "Travel & Hidden Gems",
        "label": "Travel & Hidden Gems",
        "direction": "Travel destinations, hidden gems, cafes and weekend getaways popular among millennials and Gen Z. Focus on trending and Instagram-worthy spots.",
        "feeds": [
            "https://www.cntraveler.com/feed/rss",
            "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
            "https://www.travelandleisure.com/rss",
            "https://feeds.fodors.com/fodors",
            "https://matadornetwork.com/feed/",
        ],
        "feed_kw": ["travel", "trip", "cafe", "city", "weekend", "destination", "hidden", "explore", "guide", "visit"],
    },
    {
        "name": "Philosophy for Modern Life",
        "label": "Philosophy for Modern Life",
        "direction": (
            "Apply a specific philosopher's or school of thought's ideas to a concrete modern-life problem "
            "(work stress, social media, relationships, money anxiety, identity, etc.). "
            "Write for a general audience — no jargon, no academic tone. "
            "Each post must focus on ONE specific thinker or school assigned in the prompt."
        ),
        "feeds": [
            "https://aeon.co/feed.rss",
            "https://philosophynow.org/rss",
            "https://iep.utm.edu/feed/",
            "https://blog.oup.com/category/philosophy/feed/",
            "https://www.philosophytalk.org/blog/feed",
        ],
        "feed_kw": [
            "philosophy", "stoic", "wisdom", "ethics", "meaning", "virtue",
            "buddhist", "existential", "consciousness", "identity", "freedom",
            "happiness", "justice", "mind", "logic", "metaphysics", "moral",
            "thinker", "theory", "idea", "argument", "reason",
        ],
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
            return f"{mon}/{day}/{year}", f"{year}-{mon:02d}-{int(day):02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return f"{mo}/{d}/{y}", f"{y}-{mo:02d}-{d:02d}"
    return None

# ── RSS 링크 추출 ──────────────────────────────────────
def extract_link(item_text):
    m = re.search(r'<link[^>]+href=["\']([^"\'>\s]+)["\']', item_text, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
        if url.startswith("http"):
            return url
    m = re.search(r"<link[^>]*>(.*?)</link>", item_text, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1)
        raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.DOTALL)
        raw = re.sub(r"<[^>]+>", "", raw).strip()
        if raw.startswith("http"):
            return raw
    m = re.search(r'<guid[^>]*isPermaLink=["\']true["\'][^>]*>(.*?)</guid>', item_text, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        if raw.startswith("http"):
            return raw
    return ""

# ── 트렌드 크롤링 ─────────────────────────────────────
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
                date_en = date_info[0] if date_info else None
                collected.append({"title": title, "link": link, "date": date_en})
        except Exception:
            continue
    filtered = [c for c in collected if any(kw in c["title"].lower() for kw in feed_kw)]
    result = filtered if filtered else collected
    seen, uniq = set(), []
    for c in result:
        if c["title"] not in seen:
            seen.add(c["title"]); uniq.append(c)
    return uniq[:10]

# ── Blogger 액세스 토큰 확보 ──────────────────────────
def get_blogger_service():
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    })
    res.raise_for_status()
    access_token = res.json()["access_token"]
    print("✅ Blogger access token issued")
    return access_token

# ── 발행 이력에서 다룬 소재 추출 ───────────────────────
def extract_covered_topics(category_name, posted_titles):
    if not posted_titles:
        return []
    titles_text = "\n".join(f"- {t}" for t in posted_titles[-30:])
    prompt = f"""These are already published post titles in the '{category_name}' category:

{titles_text}

Extract the key topics covered (people, theories, locations, tickers, concepts, etc.).
The goal is to avoid repeating them in future posts.

Respond with JSON array only (no other text):
["topic1", "topic2", "topic3"]"""
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
        print(f"     ⚠️ Topic extraction failed (ignored): {e}")
    return []

# ── 철학 카테고리: Gemini가 사상가 선택 ───────────────
def pick_philosopher(covered_topics, posted_titles):
    """
    Gemini에게 전세계 철학자/사상 DB에서 아직 안 쓴 것을 직접 골라달라고 요청.
    하드코딩 풀 없이 동적으로 선택 — 인류 역사 전체 철학자 커버 가능.
    """
    covered_text = ", ".join(covered_topics) if covered_topics else "None so far"
    posted_text  = "\n".join(f"- {t}" for t in posted_titles[-30:]) if posted_titles else "None so far"

    prompt = f"""You are a philosophy expert with knowledge of ALL philosophers and schools of thought from every culture, era, and tradition worldwide — Western, Eastern, African, Islamic, Latin American, Indigenous, and more.

Already covered topics to AVOID:
{covered_text}

Already published post titles to AVOID duplicating:
{posted_text}

Your task: Choose ONE philosopher or school of thought that has NOT been covered yet.
- Must be someone genuinely different from what's already been written about
- Can be from any era (ancient, medieval, modern, contemporary) and any culture
- Prioritize lesser-known but intellectually rich thinkers when popular ones are already covered
- The choice should be someone whose ideas can be applied to modern everyday life

Respond with ONLY a JSON object (no other text):
{{"name": "Philosopher or School Name", "era": "e.g. Ancient Greek / 20th Century / Song Dynasty", "known_for": "one-sentence summary of their key idea"}}"""

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
            data = json.loads(text)
            name     = data.get("name", "")
            era      = data.get("era", "")
            known_for= data.get("known_for", "")
            if name:
                print(f"     🎯 Assigned: {name} ({era}) — {known_for}")
                return name, era, known_for
    except Exception as e:
        print(f"     ⚠️ Philosopher pick failed: {e}")

    # 폴백: 완전 랜덤 지시
    fallbacks = [
        ("Wang Yangming", "Ming Dynasty China", "knowledge and action are one"),
        ("Simone Weil", "20th Century France", "attention as a form of love"),
        ("Ibn Khaldun", "14th Century Islamic", "social cohesion drives civilizations"),
        ("Hypatia", "Late Antiquity Alexandria", "reason and intellectual freedom"),
        ("Ubuntu Philosophy", "African tradition", "I am because we are"),
    ]
    chosen = random.choice(fallbacks)
    print(f"     🎯 Fallback assigned: {chosen[0]} ({chosen[1]})")
    return chosen

# ── Gemini로 영어 글 생성 ──────────────────────────────
def generate_post(category, posted_titles, covered_topics, trends):
    today = datetime.now().strftime("%B %d, %Y")
    posted_text  = "\n".join(f"- {t}" for t in posted_titles[-20:]) if posted_titles else "None"
    covered_text = ", ".join(covered_topics) if covered_topics else "None"

    if trends:
        lines = []
        for i, c in enumerate(trends):
            d = f" (published: {c['date']})" if c.get("date") else ""
            lines.append(f"[{i}] {c['title']}{d}")
        trend_text = "\n".join(lines)
    else:
        trend_text = "None"

    is_philosophy = category["name"] == "Philosophy for Modern Life"

    philosophy_block = ""
    if is_philosophy:
        philosopher_info = pick_philosopher(covered_topics, posted_titles)
        p_name, p_era, p_known = philosopher_info
        philosophy_block = f"""
[ASSIGNED THINKER — MANDATORY]
You MUST write this post specifically about: **{p_name}** ({p_era})
Their key idea: {p_known}

Rules:
- Focus on this thinker's actual ideas, quotes, or specific concepts
- Apply their thinking to ONE concrete modern-life situation (e.g., burnout, social media, relationships, money anxiety, identity crisis)
- Do NOT switch to any other philosopher unless directly comparing
- Do NOT write a generic "philosophy of life" post — make it specific to {p_name}
- If this thinker is lesser-known, briefly introduce who they are before diving into their ideas
"""

    prompt = f"""Today is {today}. Write an English blog post for the '{category['name']}' category.
Direction: {category['direction']}
{philosophy_block}
[Latest Trends — use one as context if relevant, or ignore if not applicable]
{trend_text}

[Date Rules — Important]
- When referencing a news article, use the article's published date accurately.
- Do NOT assume it's today's date.
- Do NOT fabricate dates when no date info is available.

[Already Covered Topics — DO NOT repeat these]
{covered_text}

[Already Published Titles — avoid similar angles]
{posted_text}

[Topic Selection Rules]
- Do NOT cover the same people, theories, or concepts listed in 'Already Covered Topics'.
- Pick a fresh, specific angle each time.

[Writing Style]
- Friendly, conversational tone — like talking to a friend
- Clear and engaging, not academic or stiff
- Second person ("you") encouraged

[Structure]
- Lead with the key point in the first sentence (inverted pyramid)
- One main point per subheading
- No cliché endings like "In conclusion" or "Start today!"

[Format]
- Length: 600~900 words
- HTML: subheadings as <h2>, paragraphs as <p>, lists as <ul><li> where appropriate
- Naturally weave in keywords — do NOT list them separately
- Do NOT repeat the title inside the body

[Source Reference]
- In "source_index", put the index number of the trend article you actually used as the main source.
- If you didn't use any trend, set source_index to -1.

Respond with ONLY this JSON (no other text whatsoever):
{{"title": "Title", "content": "HTML body", "tags": ["tag1","tag2","tag3"], "source_index": 0}}"""

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
                    print(f"     ⏳ {model} retry {attempt+1}/3")
                    time.sleep(8); continue
                last_err = f"{model} {res.status_code}"
                print(f"     ↪ {model} unavailable, trying next")
                break
            except Exception as e:
                last_err = str(e); time.sleep(5)
    raise RuntimeError(f"All models failed: {last_err}")

# ── 출처 링크 HTML 생성 ───────────────────────────────
def build_sources_html(post_data, trends):
    idx = post_data.get("source_index", -1)
    if idx == -1 or not isinstance(idx, int):
        return ""
    if idx < 0 or idx >= len(trends):
        return ""
    article = trends[idx]
    link  = article.get("link", "").strip()
    title = article.get("title", "").strip()
    if not link or not link.startswith("http"):
        return ""
    date = f" ({article['date']})" if article.get("date") else ""
    return (
        '\n<hr/>\n'
        '<p><strong>Source</strong></p>\n'
        '<ul>\n'
        f'  <li><a href="{link}" target="_blank" rel="noopener">{title}</a>{date}</li>\n'
        '</ul>\n'
    )

# ── Blogger에 발행 ────────────────────────────────────
def publish_post(access_token, category, post_data, sources_html):
    content = post_data["content"] + sources_html
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/"
    res = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "title":   post_data["title"],
            "content": content,
            "labels":  post_data.get("tags", []) + [category["label"]],
        }
    )
    res.raise_for_status()
    return res.json().get("url", "")

# ── 메인 ──────────────────────────────────────────────
def main():
    print(f"🚀 Blogger auto-post started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    access_token = get_blogger_service()
    posted = load_posted()
    success = 0

    for cat in CATEGORIES:
        try:
            name = cat["name"]
            print(f"\n  🔍 [{name}] Collecting trends...")
            trends = crawl_trends(cat["feeds"], cat["feed_kw"])
            print(f"     {len(trends)} trends collected")
            if trends:
                for i, t in enumerate(trends[:5]):
                    link_preview = t['link'][:60] if t['link'] else 'no link'
                    print(f"       [{i}] {t['title'][:50]} | {link_preview}")

            posted_titles = posted.get(name, [])
            print(f"  🧠 [{name}] Analyzing covered topics...")
            covered = extract_covered_topics(name, posted_titles)
            if covered:
                print(f"     Topics to avoid: {', '.join(covered[:8])}")

            print(f"  ✍️  [{name}] Generating post...")
            post = generate_post(cat, posted_titles, covered, trends)

            src_idx = post.get("source_index", -1)
            sources_html = build_sources_html(post, trends)
            if sources_html and 0 <= src_idx < len(trends):
                print(f"     Source attached: {trends[src_idx]['title'][:50]}")
            else:
                print(f"     No source attached")

            post_url = publish_post(access_token, cat, post, sources_html)
            print(f"  ✅ Published: {post['title']}")
            print(f"     {post_url}")

            posted.setdefault(name, []).append(post["title"])
            posted[name] = posted[name][-50:]

            success += 1
            time.sleep(3)

        except Exception as e:
            print(f"  ❌ [{cat['name']}] Error: {e}")

    save_posted(posted)
    print(f"\n🎉 Done! {success}/{len(CATEGORIES)} posts published")

if __name__ == "__main__":
    main()
