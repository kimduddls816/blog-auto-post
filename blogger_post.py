import os
import re
import json
import time
import random
import html as htmllib
import requests
from datetime import datetime

GEMINI_API_KEY        = os.environ["GEMINI_API_KEY"]
BLOGGER_CLIENT_ID     = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]
BLOGGER_BLOG_ID       = os.environ["BLOGGER_BLOG_ID"]

POSTED_FILE   = "posted_topics_en.json"
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

# ── 발행량: 한 번 실행에 몇 개 카테고리를 쓸지 (가장 오래 안 쓴 카테고리부터 순환)
#    신생 blogspot은 적게, 깊게 쓰는 게 색인률에 유리. GitHub Secrets/env로 POSTS_PER_RUN=5 주면 기존처럼 전부 발행.
POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN", "3"))

# ── 재시도 튜닝값
RETRY_MAX_ATTEMPTS   = 3
RETRY_BASE_SECONDS   = 10
RETRY_MULTIPLIER     = 3
RETRY_JITTER_SECONDS = 5

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

MONTHS = {m: i+1 for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])}

# ─────────────────────────────────────────────
# 투자 카테고리 전용: 고정 커리큘럼(1~100일차) + 안전 규칙
# ─────────────────────────────────────────────
INVESTING_CURRICULUM = [
    "What is capitalism? How money makes more money",
    "Saving vs investing: what's the real difference",
    "What is a stock? Owning a piece of a company",
    "How the stock market works (exchanges, going public)",
    "Why do stock prices go up and down",
    "What is an ETF? Buying many companies at once",
    "What is an index fund",
    "What are dividends? Why companies share profit",
    "What is compound interest and why starting early matters",
    "How to open a brokerage account",
    "How to place your first stock order",
    "What is diversification (don't put all eggs in one basket)",
    "What is risk in investing",
    "What is market cap (measuring company size)",
    "Long-term vs short-term investing: what fits you",
    "What are bonds (lending money to governments/companies)",
    "Stocks vs bonds: which is safer",
    "What are REITs (real estate without buying property)",
    "What is P/E ratio (is a stock cheap or expensive)",
    "What is P/B ratio",
    "What is dividend yield",
    "Dividend yield vs dividend growth: what to look at",
    "What is a retirement account (401k/IRA basics)",
    "Taxes and investing: the basics you need to know",
    "What is a sector (tech, healthcare, energy explained)",
    "Large-cap vs small-cap stocks",
    "Growth stocks vs value stocks",
    "What is a market cycle (boom and bust)",
    "How inflation affects your investments",
    "Why rising interest rates shake up stocks",
    "How currency exchange rates affect foreign investing",
    "What are commodities (gold, oil basics)",
    "What are emerging markets",
    "Emerging vs developed markets: the difference",
    "What is asset allocation",
    "What is a portfolio",
    "What is rebalancing",
    "How fees quietly eat your returns",
    "How to spot investment scams",
    "Building your own investing principles",
    "What is macroeconomics",
    "Interest rates and stocks: a deeper look",
    "What does a central bank actually do",
    "What is GDP and why it matters",
    "Unemployment rate and the stock market",
    "What are leading economic indicators",
    "What is sector rotation (money moving between industries)",
    "What is value investing (Warren Buffett basics)",
    "What is growth investing",
    "Dividend growth investing strategy",
    "Index investing vs active investing",
    "What is a smart beta ETF",
    "What is bond duration",
    "What are high-yield bonds",
    "Government bonds vs corporate bonds",
    "Monetary policy vs fiscal policy",
    "How trade and tariffs affect markets",
    "What is geopolitical risk",
    "What is market volatility (the VIX explained)",
    "What is a stop-loss order",
    "How to set a realistic target return",
    "Asset allocation by age",
    "Basics of retirement withdrawal strategy",
    "Direct real estate vs REITs",
    "What is alternative investing",
    "What is hedging",
    "What is short selling (just the concept)",
    "What are options (very basic concept)",
    "What is leverage and why it's risky",
    "How to avoid emotional investing decisions",
    "What is ESG investing",
    "Basics of investing in AI-related stocks",
    "Semiconductor industry and investing",
    "Renewable energy investing trends",
    "Healthcare and biotech sector investing",
    "Crypto vs traditional investing: the difference",
    "Global supply chains and investing",
    "What is a commodity supercycle",
    "Startup investing (angel/VC) basic concepts",
    "What is an IPO",
    "How to read an earnings report",
    "Reading financial statements: the income statement",
    "Reading financial statements: the balance sheet",
    "What is a cash flow statement",
    "Why debt-to-equity ratio matters",
    "What is a competitive moat",
    "What is a dividend cut and why it's a warning sign",
    "Demographic shifts and long-term investing",
    "Aging populations as an investing opportunity",
    "Investing strategy in a deglobalizing world",
    "What is a CBDC (digital central bank currency)",
    "What is private equity",
    "What is infrastructure investing",
    "What is the carbon credit market",
    "Space industry investing trends",
    "What are robo-advisors",
    "Building your own retirement simulation",
    "Investing psychology: avoiding herd mentality",
    "10 common mistakes long-term investors make",
    "Putting it all together: building your investing roadmap",
]

INVESTING_SAFETY_RULES = """
[MANDATORY SAFETY RULES]
- Do NOT cover leveraged products (2x or higher), crypto derivatives, meme coins, or high-risk short-term trading tactics.
- Only cover legitimate, well-established investment vehicles available worldwide (stocks, bonds, ETFs, REITs, commodities, savings accounts, etc).
- Never guarantee returns or use phrases like "guaranteed profit" or "sure thing."
- Include one natural sentence near the end noting that investing carries risk of loss of principal (write it fresh, not as a boilerplate disclaimer).
- Explain everything in plain language a beginner can follow.
"""

RECENT_DESTINATIONS_LIMIT = 60

# ─────────────────────────────────────────────
# 문장 다양성 장치
# ─────────────────────────────────────────────
OPENING_STYLES = [
    "Open with one specific, concrete scene or moment involving a person (clearly illustrative, not a fake real person) doing something related to the topic. No abstract framing.",
    "Open with a specific fact or number, but ONLY if that fact appears in the trend article summaries provided. If none is available there, open with a concrete scene instead.",
    "Open mid-thought, dropping the reader straight into the core idea with no throat-clearing.",
    "Open with a direct, concrete comparison between two specific things (not abstract concepts) that sets up the topic.",
    "Open by describing one specific tangible detail (a place, an object, a time of day, a routine) that grounds the topic immediately.",
    "Open with a common belief about the topic and, in the next sentence, show where it falls short.",
    "Open with a plain question a real reader would type into a search engine about this topic, then answer it directly in the next two sentences.",
]

SENTENCE_RHYTHMS = [
    "Favor short, punchy sentences throughout. Break ideas into small pieces.",
    "Favor longer, flowing sentences that connect ideas together, while staying clear.",
    "Deliberately alternate between very short sentences and longer explanatory ones.",
]

BANNED_STOCK_PHRASES = [
    "In today's fast-paced world", "Let's dive in", "Here's the thing",
    "We hear you", "Are you tired of", "Forget the old",
    "In this post, we'll", "Without further ado", "At the end of the day",
    "The bottom line is", "Here's what you need to know", "Buckle up",
    "It's no secret that", "In a world where", "Let's face it",
    "game-changer", "unlock the secrets", "delve into", "navigate the complexities",
    "a testament to", "in the realm of", "embark on a journey", "hidden gem",
]

BANNED_SECTION_HEADINGS = [
    "The Big Picture", "Final Thoughts", "Key Takeaways", "Conclusion",
    "In Summary", "Wrapping Up", "Know Before You Go", "The Bottom Line",
]

# ─────────────────────────────────────────────
# 구조 로테이션: 카테고리별 레이아웃을 여러 개 두고 직전과 다른 걸 배정
# (모든 글이 같은 HTML 뼈대면 구글이 템플릿 페이지로 묶어버림)
# ─────────────────────────────────────────────
STRUCTURE_VARIANTS = {
    "World News Simplified": [
        """Layout: headline list first.
1. Start directly with an <ol> of the 3-5 stories, one short line each. No sentence before the list.
2. Each story gets its own <h2> in the same order: what happened, why it matters, and, where genuinely relevant, how it could touch an ordinary reader's life (prices, travel, jobs, savings).
3. A short closing <h2> section (2-4 plain sentences) naming the one thread that connects today's stories and a concrete thing to watch next.""",
        """Layout: one lead story, then briefs.
1. Open straight into the single most important story and give it roughly half the post under its own <h2>, with real context and background.
2. Then an <h2> for shorter briefs: 2-4 other stories, each as its own <h3> with 1 short paragraph.
3. End with one short paragraph (no heading) on what to watch in the coming days. No numbered headline list in this layout.""",
        """Layout: theme-first.
1. Open with 2-3 sentences stating the single theme that links today's 3-4 stories.
2. Each story gets an <h2> written as the question a reader would actually ask about it (e.g. "Why are rice prices jumping in Japan?"), answered directly in the first sentence under it.
3. Close with a <ul> of 2-3 concrete "what this could mean next" points. No separate closing heading needed.""",
    ],
    "Travel & Hidden Gems": [
        """Layout: three equal destinations.
- One short connecting idea, then each of the 3 destinations under its own <h2> (destination name in the heading).
- For each: what makes it special, one or two specific named neighborhoods or landmarks, how to get there, one practical tip, plus a short practical block covering safety level for travelers and approximate cost level (a meal and a night's stay as ranges). Title that block differently for each destination, or fold it into the paragraph.""",
        """Layout: one featured destination plus two alternatives.
- The first destination gets about 60% of the post under its own <h2>, with 2-3 <h3> subsections (e.g. where to stay, what to do on day one, what locals do differently).
- Then an <h2> presenting the other 2 destinations as alternatives with a similar feel, each under its own <h3>, shorter.
- End with a compact <ul> comparing all 3 on safety, rough daily budget range, and best season.""",
        """Layout: theme-led comparison.
- Pick one concrete theme that genuinely links the 3 destinations (e.g. a type of food, a slow-travel style, a season, a transport experience) and state it in the first two sentences.
- Each destination gets an <h2> framed around how it delivers that theme, with specific named places and a practical tip.
- End with an <h2> that helps the reader choose between them ("pick X if..., pick Y if..."), including safety and approximate costs for each.""",
    ],
    "Passive Income Investing": [
        """Order: Market News → Investing Concept → New Asset Spotlight → ETF Picks. Each part under its own <h2> with a heading written fresh for this post (not the generic part names).""",
        """Order: Investing Concept first (connect it to today's market in one line) → Market News → New Asset Spotlight → ETF Picks. Each part under its own <h2> with a fresh heading.""",
        """Order: Investing Concept → New Asset Spotlight → Market News → ETF Picks, where the ETF picks explicitly follow from the market news just discussed. Each part under its own <h2> with a fresh heading. Present the 3 ETF picks as short paragraphs, not a bullet list.""",
    ],
    "Wellness and Self-Care": [
        """Layout: deep dive. Explain what the new research or trend actually found (only as described in the source summary), what it does NOT show, and how to apply it, each under its own <h2>.""",
        """Layout: belief vs evidence. Open with what most people assume about this topic, then use <h2> sections to walk through what the evidence actually suggests and what a sensible person could do differently.""",
        """Layout: a small practical experiment. Frame the post around trying one specific change for 7 days: why it might help, exactly how to do it, what to notice, and when to stop or ask a professional. Use <h2> sections and one <ol> for the steps.""",
        """Layout: reader questions. Organize the post as 4-6 <h2> headings, each a real question people search about this topic, each answered directly in its first sentence and then explained.""",
    ],
    "Philosophy for Modern Life": [
        """Layout: thinker first. Briefly who the thinker was and the one idea that matters here, then apply it to a concrete modern problem, then one small practice the reader can try this week. Use <h2> sections.""",
        """Layout: problem first. Open with a specific, relatable modern situation, then bring in the thinker as an unexpected answer to it, then show where the idea is limited or where critics push back. Use <h2> sections.""",
        """Layout: one idea, three situations. Explain the thinker's core idea briefly, then apply it to three different concrete modern situations, each under its own <h2>.""",
    ],
}

LENGTH_BY_CATEGORY = {
    "Passive Income Investing":   "900~1300 words",
    "World News Simplified":      "800~1100 words",
    "Wellness and Self-Care":     "800~1200 words",
    "Travel & Hidden Gems":       "900~1300 words",
    "Philosophy for Modern Life": "800~1200 words",
}

# 이보다 짧으면 1회 재생성 (얇은 콘텐츠 = 색인 거절 1순위)
MIN_WORDS = {
    "Passive Income Investing":   800,
    "World News Simplified":      700,
    "Wellness and Self-Care":     700,
    "Travel & Hidden Gems":       800,
    "Philosophy for Modern Life": 700,
}

RELATED_HEADINGS = ["Keep reading", "You might also like", "Related reads", "Worth reading next", "More from the blog"]

CATEGORIES = [
    {
        "name": "Passive Income Investing",
        "label": "Passive Income Investing",
        "direction": "Beginner-friendly guides on long-term investing, ETFs, dividend stocks, and building wealth steadily. Include real ticker names and ETF names.",
        "feeds": [
            "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            "https://www.dividendgrowthinvestor.com/feeds/posts/default",
            "https://feeds.reuters.com/reuters/businessNews",
            "https://www.fool.com/feeds/index.aspx",
            "https://seekingalpha.com/feed.xml",
        ],
        "feed_kw": ["etf", "dividend", "invest", "stock", "retire", "fund", "portfolio", "yield", "passive", "income", "wealth", "market"],
    },
    {
        "name": "World News Simplified",
        "label": "World News Simplified",
        "direction": "Global economic, political and social issues explained in plain English that anyone can understand in a few minutes, with context the headlines leave out.",
        "feeds": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            "https://feeds.reuters.com/reuters/topNews",
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://feeds.skynews.com/feeds/rss/world.xml",
        ],
        "feed_kw": ["economy", "election", "rate", "market", "trade", "policy", "war", "ai", "crisis", "global", "deal", "sanctions"],
    },
    {
        "name": "Wellness and Self-Care",
        "label": "Wellness and Self-Care",
        "direction": "Wellness research and trends explained simply, with practical steps readers can apply. Covers the full range: physical and mental health, sleep, nutrition, fitness, relationships, productivity, longevity, hormones, skin, gut health, stress, and habits. Relevant to readers of any age or gender.",
        "feeds": [
            "https://www.healthline.com/rss/news",
            "https://www.medicalnewstoday.com/rss/medical-news-today.xml",
            "https://www.psychologytoday.com/us/articles/feed",
            "https://greatergood.berkeley.edu/feeds/news",
            "https://www.health.com/rss",
            "https://well.blogs.nytimes.com/feed/",
            "https://www.self.com/feed/rss",
            "https://www.womenshealthmag.com/rss/all.xml/",
        ],
        "feed_kw": ["health", "sleep", "stress", "mental", "anxiety", "wellness", "habit", "diet", "burnout", "mindful", "therapy", "mood", "exercise", "nutrition", "gut", "brain", "longevity", "weight", "immune", "fitness", "hormone", "skin", "supplement", "research", "study"],
    },
    {
        "name": "Travel & Hidden Gems",
        "label": "Travel & Hidden Gems",
        "direction": "Destinations and specific experiences worth planning a trip around, from lesser-known towns to fresh angles on known regions. Practical, specific, and honest about costs and trade-offs.",
        "feeds": [
            "https://www.cntraveler.com/feed/rss",
            "https://www.travelandleisure.com/rss",
            "https://matadornetwork.com/feed/",
            "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
            "https://www.lonelyplanet.com/news/feed",
        ],
        "feed_kw": ["travel", "trip", "cafe", "city", "weekend", "destination", "hidden", "explore", "guide", "visit", "hotel", "beach", "mountain", "road trip", "airbnb"],
    },
    {
        "name": "Philosophy for Modern Life",
        "label": "Philosophy for Modern Life",
        "direction": (
            "Apply a specific philosopher's or school of thought's ideas to a concrete modern-life problem "
            "(work stress, social media, relationships, money worries, identity, etc.). "
            "Write for a general audience, no jargon, no academic tone. "
            "Each post must focus on ONE specific thinker or school."
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

# ─────────────────────────────────────────────
# 저장/파싱 유틸
# ─────────────────────────────────────────────
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

def extract_summary(item_text, max_chars=500):
    """RSS 항목의 요약/본문 일부를 추출. AI가 제목 한 줄이 아니라 실제 사실을 바탕으로 쓰게 하기 위함."""
    m = re.search(r"<(description|summary|content:encoded|content)\b[^>]*>(.*?)</\1>",
                  item_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    raw = m.group(2)
    raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.DOTALL)
    raw = htmllib.unescape(htmllib.unescape(raw))
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s{2,}", " ", raw).strip()
    if len(raw) > max_chars:
        raw = raw[:max_chars].rsplit(" ", 1)[0] + "..."
    return raw

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
                title = htmllib.unescape(re.sub(r"<[^>]+>", "", title)).strip()
                if not (8 < len(title) < 140):
                    continue
                link = extract_link(item)
                dm = re.search(r"<(?:pubDate|published|updated|dc:date)[^>]*>(.*?)</(?:pubDate|published|updated|dc:date)>",
                               item, re.DOTALL | re.IGNORECASE)
                date_info = parse_pubdate(dm.group(1)) if dm else None
                date_en = date_info[0] if date_info else None
                summary = extract_summary(item)
                collected.append({"title": title, "link": link, "date": date_en, "summary": summary})
        except Exception:
            continue
    filtered = [c for c in collected if any(kw in c["title"].lower() for kw in feed_kw)]
    result = filtered if filtered else collected
    # 요약 있는 기사를 앞으로 (AI가 쓸 재료가 있는 기사 우선)
    result.sort(key=lambda c: 0 if c.get("summary") else 1)
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

def fetch_recent_posts(access_token, max_results=100):
    """내부 링크용: 블로그에 이미 발행된 글 목록(제목/URL/라벨)을 가져옴."""
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts"
    posts, page_token = [], None
    try:
        while len(posts) < max_results:
            params = {"maxResults": 50, "fetchBodies": "false", "status": "live"}
            if page_token:
                params["pageToken"] = page_token
            r = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params, timeout=20)
            if r.status_code != 200:
                print(f"     ⚠️ Recent posts fetch failed ({r.status_code}), related links skipped")
                break
            j = r.json()
            for p in j.get("items", []):
                if p.get("url") and p.get("title"):
                    posts.append({"title": p["title"], "url": p["url"], "labels": p.get("labels", []) or []})
            page_token = j.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"     ⚠️ Recent posts fetch error (ignored): {e}")
    return posts[:max_results]

def build_related_html(category_label, recent_posts, exclude_title=""):
    """같은 카테고리 이전 글 3개 + 다른 카테고리 1개를 내부 링크로 연결."""
    if not recent_posts:
        return ""
    same = [p for p in recent_posts[:40] if category_label in p["labels"] and p["title"] != exclude_title]
    other = [p for p in recent_posts[:40] if category_label not in p["labels"]]
    picks = random.sample(same, min(3, len(same)))
    if other:
        picks.append(random.choice(other))
    if not picks:
        return ""
    items = "".join(
        f'  <li><a href="{htmllib.escape(p["url"], quote=True)}">{htmllib.escape(p["title"])}</a></li>\n'
        for p in picks
    )
    heading = random.choice(RELATED_HEADINGS)
    return f'\n<p><strong>{heading}</strong></p>\n<ul>\n{items}</ul>\n'

def extract_covered_topics(category_name, posted_titles):
    if not posted_titles:
        return []
    titles_text = "\n".join(f"- {t}" for t in posted_titles[-30:])
    prompt = f"""These are already published post titles in the '{category_name}' category:

{titles_text}

Extract the key specific topics/stories/angles covered, as specifically as possible.
Not just "economy" but "mortgage rates affecting home sales", not just "ETF investing" but "broad market ETF + dividend aristocrats basics for beginners".
The goal is a precise list of what NOT to repeat, including angles that LOOK different but cover the same underlying concept.

Respond with JSON array only (no other text):
["specific topic 1", "specific topic 2", "specific topic 3"]"""
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

def clean_markdown_artifacts(text):
    if not text:
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(?!\*)(.+?)(?<!\*)\*(?!\w)", r"\1", text)
    text = text.replace("—", ", ").replace("–", "-")
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text

def html_to_text(content_html):
    text = re.sub(r"<[^>]+>", " ", content_html or "")
    return re.sub(r"\s{2,}", " ", htmllib.unescape(text)).strip()

def word_count(content_html):
    return len(html_to_text(content_html).split())

def extract_opening_text(content_html, max_chars=220):
    return html_to_text(content_html)[:max_chars]

def pick_different(options, previous):
    choices = [o for o in options if o != previous] or options
    return random.choice(choices)

def pick_categories(meta):
    """가장 오래 발행 안 된 카테고리부터 POSTS_PER_RUN개 선택."""
    last = meta.get("last_posted_at", {})
    cats = CATEGORIES[:]
    random.shuffle(cats)
    cats.sort(key=lambda c: last.get(c["name"], "0000"))
    n = max(1, min(POSTS_PER_RUN, len(cats)))
    return cats[:n]

# ─────────────────────────────────────────────
# 글 생성
# ─────────────────────────────────────────────
def generate_post(category, posted_titles, covered_topics, trends, investing_progress=0,
                  recent_tickers=None, recent_destinations=None, recent_openings=None,
                  opening_style=None, sentence_rhythm=None, structure_variant=None):
    posted_text  = "\n".join(f"- {t}" for t in posted_titles[-20:]) if posted_titles else "None"
    covered_text = ", ".join(covered_topics) if covered_topics else "None"
    tickers_text = ", ".join(recent_tickers or []) or "None"
    destinations_text = ", ".join(recent_destinations or []) or "None"
    openings_text = "\n".join(f"- \"{o}...\"" for o in (recent_openings or [])) or "None"
    opening_style = opening_style or OPENING_STYLES[0]
    sentence_rhythm = sentence_rhythm or SENTENCE_RHYTHMS[0]
    banned_phrases_text = ", ".join(f'"{p}"' for p in BANNED_STOCK_PHRASES)
    banned_headings_text = ", ".join(f'"{h}"' for h in BANNED_SECTION_HEADINGS)
    name = category["name"]
    structure_variant = structure_variant or STRUCTURE_VARIANTS[name][0]
    length_text = LENGTH_BY_CATEGORY.get(name, "800~1200 words")

    if trends:
        lines = []
        for i, c in enumerate(trends):
            d = f" (published: {c['date']})" if c.get("date") else ""
            s = f"\n    Summary: {c['summary']}" if c.get("summary") else "\n    Summary: (not available)"
            lines.append(f"[{i}] {c['title']}{d}{s}")
        trend_text = "\n".join(lines)
    else:
        trend_text = "None available today"

    is_philosophy = name == "Philosophy for Modern Life"
    is_investing  = name == "Passive Income Investing"
    is_travel     = name == "Travel & Hidden Gems"
    is_news       = name == "World News Simplified"

    if is_investing:
        title_hook_block = ""
    else:
        title_hook_block = """
[TITLE CRAFT — WRITE THIS AFTER DRAFTING THE BODY]
- Pull the single most interesting, concrete detail from the body and build the title around it, not around a generic label for the topic.
- Include one real, specific detail (a number from the sources, a place, a named thing, a specific situation).
- A curiosity gap is fine only if the body actually pays it off. No clickbait, no exaggeration.
- Do not default to fear- or anxiety-based framing.
- If you could swap one noun and the title would fit a different post, it is too generic.
"""

    common_rules = f"""
[FORMATTING RULES — MANDATORY]
- Write ONLY valid HTML. NEVER use markdown (**bold**, *italic*, # headers).
- For emphasis use <strong> or <em>, sparingly.
- NEVER use the em dash (—) or en dash (–). Use a period, comma, or rewrite the sentence.
- Keep paragraphs short (2-4 sentences).

[ACCURACY RULES — MANDATORY, THIS DECIDES WHETHER GOOGLE TRUSTS THE PAGE]
- Only use specific numbers, statistics, study findings, quotes, and dates that appear in the trend article summaries provided below. If you need a figure that isn't there, describe it qualitatively instead of inventing one.
- Never invent studies, researchers, experts, quotes, businesses, restaurants, hotels, or street addresses. Only name places and things you are confident actually exist.
- Costs and prices must be given as approximate ranges and clearly described as approximate.
- If a summary is thin, stay honest about what is known. Do not pad with made-up detail.

[ORIGINAL VALUE — MANDATORY]
- The post must add something the source articles don't: a practical implication for the reader, a common misconception corrected, a useful comparison, a trade-off, or a concrete "how to actually do this" step. A rewrite of the source is not enough.
- Every section should contain at least one specific, concrete detail. No filler paragraphs that could appear in any post on this topic.

[INTRO RULES — MANDATORY]
- Start the body directly with substantive content. Do not open with the category name, today's date, a welcome line, or a scene-setting sentence about "today's post".

[TITLE RULES — MANDATORY]
- 45 to 70 characters. Natural, readable, matching what a real person might search for.
- Do not default to one recurring emotional frame across posts.
- Do not share the sentence structure, opening word pattern, or tone of the recent titles below. If recent titles were mostly questions, don't write a question.
{title_hook_block}
[OPENING RULES — MANDATORY]
- Use this opening approach: {opening_style}
- Do NOT resemble any of these recent openings from this category: {openings_text}

[SENTENCE RHYTHM — MANDATORY]
- {sentence_rhythm}

[BANNED PHRASES — MANDATORY]
- Never use these or close variants: {banned_phrases_text}
- Never use these as section headings: {banned_headings_text}. Write every <h2>/<h3> fresh and specific to this post.
"""

    if is_philosophy:
        topic_block = f"""
[PHILOSOPHER SELECTION — MANDATORY FIRST STEP]
Select ONE philosopher or school of thought.
- Choose from ALL of human history and ALL cultures (Western, Eastern, African, Islamic, Latin American, Indigenous, etc.)
- DO NOT choose anyone already covered: {covered_text}
- DO NOT repeat themes from these titles: {posted_text}
- Prefer lesser-known thinkers when well-known ones are already covered.
- Only attribute ideas and quotes the thinker is genuinely known for. If unsure of an exact quote, paraphrase and say it is a paraphrase.
Include the thinker's name in the title naturally.
"""
    elif is_investing:
        if investing_progress < len(INVESTING_CURRICULUM):
            concept = INVESTING_CURRICULUM[investing_progress]
            concept_block = f"""Today's assigned concept (day {investing_progress + 1} of the curriculum): "{concept}"
Explain ONLY this concept, assuming only basic knowledge from earlier curriculum days."""
        else:
            concept_block = f"""Pick ONE new, specific investing concept not covered before (avoid these even with a different title: {covered_text}).
Intermediate to advanced concepts are welcome now."""

        topic_block = f"""
[MANDATORY 4-PART CONTENT]
- Market News: what's happening in markets today, based ONLY on the trend article summaries below.
- Investing Concept: {concept_block}
- New Asset/Method Spotlight: ONE legitimate asset, product, or method not covered before (e.g. gold, TIPS, municipal bonds, DRIP, covered call ETFs, international markets, tax-advantaged accounts). Must differ from: {covered_text}. Explain what it is and how someone could realistically start.
- ETF Picks: exactly 3 ETF tickers that fit today's conditions from the summaries. Avoid these recent tickers unless there's a strong reason: {tickers_text}. 1-2 sentences each on why.
A new angle on an already-covered concept still counts as a repeat.
{INVESTING_SAFETY_RULES}
"""
    elif is_news:
        topic_block = f"""
[TOPIC SELECTION — MANDATORY]
Cover the most significant stories from the trend articles below (the layout says how many), explained for a general reader.
- Prefer stories that HAVE a summary, since you may only state facts that appear there.
- Stories must be genuinely different from what's already covered: {covered_text}
- Do NOT reuse stories from already published titles, even if still in the news: {posted_text}
- Add context the headline leaves out (background, why now, who is affected), without inventing facts.
"""
    elif is_travel:
        topic_block = f"""
[TOPIC SELECTION — MANDATORY FIRST STEP]
Cover 3 SEPARATE destinations (different cities/towns/regions, not 3 spots in one city), ideally from different continents.
- Use trend articles if they fit, otherwise choose fresh ones.
- NO active conflict zones or places under official advisories against travel.
- Must differ from everything already covered: {covered_text}

[DESTINATION BAN LIST — CHECK ALL 3 PICKS]
Already featured and STRICTLY OFF LIMITS (including other neighborhoods of the same city or the same region under another name): {destinations_text}
If your first instinct is on this list, go more niche.

[TRAVEL TITLE RULES]
- Build the title from the actual character of these 3 destinations. No stock phrases like "Insta-Worthy", "Hidden Gems", "Off-the-Radar", "Millennials & Gen Z", "Your Next Escape".
- Vary the title format each time and avoid the structure of: {posted_text}
"""
    else:
        topic_block = f"""
[TOPIC SELECTION — MANDATORY FIRST STEP]
Pick ONE trend article below (prefer one with a summary) and build the whole post around that specific topic, going deep rather than broad.
- If no trends are usable, pick one narrow, well-established wellness topic and explain it accurately without citing specific studies you can't see.
- Never write a broad "5 tips for sleep, diet, and stress" overview.
- Must differ from everything already covered: {covered_text}
- This is general information, not medical advice. Where it genuinely matters (supplements, medications, symptoms, big diet changes), say once, naturally, that a doctor or qualified professional should be consulted. Never claim anything cures or treats a disease.
"""

    structure_block = f"""
[STRUCTURE — THIS POST'S LAYOUT, MANDATORY]
{structure_variant}
- Length: {length_text}. Reach the length with substance, never with filler.
- HTML: <h2>/<h3> subheadings, <p> paragraphs, <ul>/<ol> lists only where they genuinely help.
- Do NOT repeat the title inside the body.
"""

    source_ref_block = """
[Source Reference]
- For Philosophy, Wellness, Travel, Investing: source_index = index of the ONE trend article used as main source, or -1 if none.
- For World News Simplified ONLY: source_indices = ARRAY of indices of ALL trend articles referenced (one per story).
- For Passive Income Investing ONLY: "tickers" = ARRAY of the 3 ETF tickers recommended.
- For Travel & Hidden Gems ONLY: "destinations" = ARRAY of exactly the 3 destinations covered, as "City/Region, Country".
"""

    prompt = f"""Write an English blog post for the '{name}' category of a general-interest lifestyle blog.
Direction: {category['direction']}
{common_rules}
{topic_block}
[Latest Trend Articles — crawled today, with summaries]
{trend_text}

[Already Covered Topics — DO NOT repeat these angles, even with a different title]
{covered_text}

[Already Published Titles — avoid similar angles and structure]
{posted_text}

[Writing Style]
- Friendly and conversational, like a knowledgeable friend. "You" is encouraged.
- No cliché endings like "In conclusion" or "Start today!"
- Specific, concrete, actionable.
- For Passive Income Investing: adult, conversational tone, never childish. Explain every financial term in plain language with a concrete example the first time it appears.
{structure_block}
{source_ref_block}
Respond with ONLY this JSON (no other text):
{{"title": "Title", "content": "HTML body", "source_index": 0, "source_indices": [], "tickers": [], "destinations": []}}"""

    last_err = None
    for model in GEMINI_MODELS:
        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                res = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 1.0}},
                    timeout=90
                )
                if res.status_code == 200:
                    text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    data = json.loads(text)
                    data["title"]   = clean_markdown_artifacts(data.get("title", "")).strip()
                    data["content"] = clean_markdown_artifacts(data.get("content", ""))
                    return data
                if res.status_code in (429, 500, 502, 503):
                    last_err = f"{model} {res.status_code}"
                    if attempt < RETRY_MAX_ATTEMPTS - 1:
                        wait = (RETRY_BASE_SECONDS * (RETRY_MULTIPLIER ** attempt)) + random.uniform(0, RETRY_JITTER_SECONDS)
                        print(f"     ⏳ {model} {res.status_code}, {wait:.1f}s 대기 후 재시도 ({attempt+1}/{RETRY_MAX_ATTEMPTS})")
                        time.sleep(wait)
                    continue
                last_err = f"{model} {res.status_code}"
                print(f"     ↪ {model} unavailable, trying next")
                break
            except Exception as e:
                last_err = str(e)
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    wait = (RETRY_BASE_SECONDS * (RETRY_MULTIPLIER ** attempt)) + random.uniform(0, RETRY_JITTER_SECONDS)
                    print(f"     ⏳ {model} exception, {wait:.1f}s 대기 후 재시도 ({attempt+1}/{RETRY_MAX_ATTEMPTS})")
                    time.sleep(wait)
    raise RuntimeError(f"All models failed: {last_err}")

def build_sources_html(post_data, trends):
    indices = post_data.get("source_indices")
    if isinstance(indices, list) and indices:
        items, seen = [], set()
        for idx in indices:
            if not isinstance(idx, int) or idx < 0 or idx >= len(trends) or idx in seen:
                continue
            seen.add(idx)
            article = trends[idx]
            link  = article.get("link", "").strip()
            title = article.get("title", "").strip()
            if not link.startswith("http"):
                continue
            date = f" ({article['date']})" if article.get("date") else ""
            items.append(f'  <li><a href="{htmllib.escape(link, quote=True)}" target="_blank" rel="noopener nofollow">{htmllib.escape(title)}</a>{date}</li>\n')
        if items:
            return '\n<hr/>\n<p><strong>Sources</strong></p>\n<ul>\n' + "".join(items) + '</ul>\n'
        return ""

    idx = post_data.get("source_index", -1)
    if not isinstance(idx, int) or idx < 0 or idx >= len(trends):
        return ""
    article = trends[idx]
    link  = article.get("link", "").strip()
    title = article.get("title", "").strip()
    if not link.startswith("http"):
        return ""
    date = f" ({article['date']})" if article.get("date") else ""
    return (
        '\n<hr/>\n<p><strong>Source</strong></p>\n<ul>\n'
        f'  <li><a href="{htmllib.escape(link, quote=True)}" target="_blank" rel="noopener nofollow">{htmllib.escape(title)}</a>{date}</li>\n'
        '</ul>\n'
    )

def publish_post(access_token, category, post_data, extra_html):
    content = post_data["content"] + extra_html
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/"
    res = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "title":   post_data["title"],
            "content": content,
            # 라벨은 카테고리 하나만: AI 태그가 얇은 라벨 페이지를 양산해 크롤링 예산을 잡아먹던 문제 차단
            "labels":  [category["label"]],
        }
    )
    res.raise_for_status()
    return res.json().get("url", "")

# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    print(f"🚀 Blogger auto-post started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    access_token = get_blogger_service()
    print("✅ Blogger access token issued")
    posted = load_posted()
    posted.setdefault("_meta", {})
    meta = posted["_meta"]
    success = 0

    investing_progress     = meta.get("investing_progress", 0)
    recent_tickers         = meta.get("recent_tickers", [])
    recent_destinations    = meta.get("recent_destinations", [])
    recent_openings_by_cat = meta.get("recent_openings", {})
    last_style_by_cat      = meta.get("last_opening_style", {})
    last_rhythm_by_cat     = meta.get("last_sentence_rhythm", {})
    last_structure_by_cat  = meta.get("last_structure", {})
    last_posted_at         = meta.get("last_posted_at", {})

    recent_posts = fetch_recent_posts(access_token)
    print(f"🔗 {len(recent_posts)} existing posts loaded for internal links")

    selected = pick_categories(meta)
    print(f"📋 This run: {', '.join(c['name'] for c in selected)} ({len(selected)}/{len(CATEGORIES)})")

    for cat in selected:
        try:
            name = cat["name"]
            print(f"\n  🔍 [{name}] Collecting trends...")
            trends = crawl_trends(cat["feeds"], cat["feed_kw"])
            with_summary = sum(1 for t in trends if t.get("summary"))
            print(f"     {len(trends)} trends collected ({with_summary} with summary)")

            posted_titles = posted.get(name, [])
            covered = extract_covered_topics(name, posted_titles)
            if covered:
                print(f"     Topics to avoid: {', '.join(covered[:8])}")

            chosen_style     = pick_different(OPENING_STYLES, last_style_by_cat.get(name))
            chosen_rhythm    = pick_different(SENTENCE_RHYTHMS, last_rhythm_by_cat.get(name))
            chosen_structure = pick_different(STRUCTURE_VARIANTS[name], last_structure_by_cat.get(name))
            cat_openings     = recent_openings_by_cat.get(name, [])

            kwargs = dict(recent_openings=cat_openings, opening_style=chosen_style,
                          sentence_rhythm=chosen_rhythm, structure_variant=chosen_structure)
            if name == "Passive Income Investing":
                print(f"     Investing curriculum progress: day {investing_progress + 1}")
                kwargs.update(investing_progress=investing_progress, recent_tickers=recent_tickers)
            elif name == "Travel & Hidden Gems":
                kwargs.update(recent_destinations=recent_destinations)

            print(f"  ✍️  [{name}] Generating post...")
            post = generate_post(cat, posted_titles, covered, trends, **kwargs)

            # 품질 게이트: 너무 짧으면 1회 재생성, 더 긴 쪽 사용
            wc = word_count(post.get("content", ""))
            if wc < MIN_WORDS[name]:
                print(f"     ⚠️ Too short ({wc} words), regenerating once...")
                retry = generate_post(cat, posted_titles, covered, trends, **kwargs)
                if word_count(retry.get("content", "")) > wc:
                    post = retry
                wc = word_count(post.get("content", ""))
            print(f"     {wc} words")

            if not post.get("title") or not post.get("content"):
                raise RuntimeError("Empty title or content")

            actual_opening_text = extract_opening_text(post.get("content", ""))
            sources_html = build_sources_html(post, trends)
            related_html = build_related_html(cat["label"], recent_posts, post["title"])

            post_url = publish_post(access_token, cat, post, sources_html + related_html)
            print(f"  ✅ Published: {post['title']}")
            print(f"     {post_url}")

            # 같은 실행 내 다음 글이 이 글을 내부 링크할 수 있게 목록 맨 앞에 추가
            if post_url:
                recent_posts.insert(0, {"title": post["title"], "url": post_url, "labels": [cat["label"]]})

            posted.setdefault(name, []).append(post["title"])
            posted[name] = posted[name][-50:]

            if actual_opening_text:
                recent_openings_by_cat[name] = (cat_openings + [actual_opening_text])[-6:]
            last_style_by_cat[name]     = chosen_style
            last_rhythm_by_cat[name]    = chosen_rhythm
            last_structure_by_cat[name] = chosen_structure
            last_posted_at[name]        = datetime.now().isoformat(timespec="seconds")

            meta["recent_openings"]      = recent_openings_by_cat
            meta["last_opening_style"]   = last_style_by_cat
            meta["last_sentence_rhythm"] = last_rhythm_by_cat
            meta["last_structure"]       = last_structure_by_cat
            meta["last_posted_at"]       = last_posted_at

            if name == "Passive Income Investing":
                investing_progress += 1
                meta["investing_progress"] = investing_progress
                new_tickers = post.get("tickers", [])
                if isinstance(new_tickers, list):
                    recent_tickers = (recent_tickers + [t for t in new_tickers if isinstance(t, str)])[-15:]
                    meta["recent_tickers"] = recent_tickers

            if name == "Travel & Hidden Gems":
                new_destinations = post.get("destinations", [])
                if isinstance(new_destinations, list):
                    combined = recent_destinations + [d.strip() for d in new_destinations if isinstance(d, str) and d.strip()]
                    recent_destinations = combined[-RECENT_DESTINATIONS_LIMIT:]
                    meta["recent_destinations"] = recent_destinations

            success += 1
            save_posted(posted)   # 글마다 저장: 중간에 실패해도 진행상황 유지
            time.sleep(3)

        except Exception as e:
            print(f"  ❌ [{cat['name']}] Error: {e}")

    save_posted(posted)
    print(f"\n🎉 Done! {success}/{len(selected)} posts published")

if __name__ == "__main__":
    main()
