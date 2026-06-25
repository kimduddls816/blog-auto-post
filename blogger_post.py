import os
import re
import json
import time
import random
import requests
from datetime import datetime

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
        ],
        "feed_kw": [
            "philosophy", "stoic", "wisdom", "ethics", "meaning", "virtue",
            "buddhist", "existential", "consciousness", "identity", "freedom",
            "happiness", "justice", "mind", "moral", "thinker", "theory",
        ],
    },
]

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

def get_blogger_service():
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     BLOGGER_CLIENT_ID,
        "client_secret": BLOGGER_CLIENT_SECRET,
        "refresh_token": BLOGGER_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    })
    res.raise_for_status()
    return res.json()["access_token"]

def extract_covered_topics(category_name, posted_titles):
    if not posted_titles:
        return []
    titles_text = "\n".join(f"- {t}" for t in posted_titles[-30:])
    prompt = f"""These are already published post titles in the '{category_name}' category:

{titles_text}

Extract the key topics covered (people, theories, locations, tickers, concepts, etc.).
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

    # 철학 카테고리: 사상가 선택을 별도 API 호출 없이 글 생성 프롬프트에 통합
    philosophy_block = ""
    if is_philosophy:
        philosophy_block = f"""
[PHILOSOPHER SELECTION — MANDATORY FIRST STEP]
Before writing, you must select ONE philosopher or school of thought to write about.
- Choose from ALL of human history and ALL cultures (Western, Eastern, African, Islamic, Latin American, Indigenous, etc.)
- DO NOT choose anyone already covered: {covered_text}
- DO NOT repeat themes from these titles: {posted_text}
- Prioritize lesser-known thinkers when well-known ones are already covered
- Must be someone whose ideas apply to modern everyday life

Then write the entire post about THAT chosen thinker only.
Include the chosen thinker's name in the "title" field naturally.
"""

    prompt = f"""Today is {today}. Write an English blog post for the '{category['name']}' category.
Direction: {category['direction']}
{philosophy_block}
[Latest Trends — use one as context if relevant, or ignore if not applicable]
{trend_text}

[Date Rules]
- When referencing a news article, use the article's published date accurately.
- Do NOT fabricate dates.

[Already Covered Topics — DO NOT repeat]
{covered_text}

[Already Published Titles — avoid similar angles]
{posted_text}

[Writing Style]
- Friendly, conversational — like talking to a friend
- Second person ("you") encouraged
- No cliché endings like "In conclusion" or "Start today!"

[Format]
- Length: 600~900 words
- HTML: <h2> subheadings, <p> paragraphs, <ul><li> lists where appropriate
- Do NOT repeat the title inside the body

[Source Reference]
- source_index: index number of the trend article actually used. -1 if none used.

Respond with ONLY this JSON (no other text):
{{"title": "Title", "content": "HTML body", "tags": ["tag1","tag2","tag3"], "source_index": -1}}"""

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

def build_sources_html(post_data, trends):
    idx = post_data.get("source_index", -1)
    if not isinstance(idx, int) or idx < 0 or idx >= len(trends):
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

def publish_post(access_token, category, post_data, sources_html):
    content = post_data["content"] + sources_html
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/"
    res = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "title":   post_data["title"],
            "content": content,
            "labels":  post_data.get("tags", []) + [category["label"]],
        }
    )
    res.raise_for_status()
    return res.json().get("url", "")

def main():
    print(f"🚀 Blogger auto-post started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    access_token = get_blogger_service()
    print("✅ Blogger access token issued")
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
                    print(f"       [{i}] {t['title'][:50]} | {t['link'][:60] if t['link'] else 'no link'}")

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
