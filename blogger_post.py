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

# ─────────────────────────────────────────────
# 투자 카테고리 전용: 고정 커리큘럼(1~100일차) + 안전 규칙
# 101일차부터는 AI가 스스로 개념/자산을 생성함 (별도 리스트 없음)
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
- Always include a line near the end of the post noting that investing carries risk of loss of principal.
- Explain everything in plain language a beginner can follow.
"""

CATEGORIES = [
    {
        "name": "Passive Income Investing",
        "label": "Passive Income Investing",
        "direction": "Beginner-friendly guides on FIRE movement, ETF investing, dividend stocks, and automated wealth building. Include real ticker names and ETF names.",
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
        "direction": "Global economic, political and social issues explained in plain English that anyone can understand in 3 minutes. Reflect recent news trends.",
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
        "direction": "Latest wellness trends and research explained simply with practical guides readers can apply immediately. Covers the FULL range of wellness — physical health, mental health, sleep, nutrition, fitness, relationships, productivity, longevity, hormones, skin, gut health, stress, habits, and anything genuinely new and useful.",
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
        "direction": "Travel destinations, hidden gems, cafes and weekend getaways popular among millennials and Gen Z. Focus on trending and Instagram-worthy spots.",
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

Extract the key specific topics/stories/angles covered — be as specific as possible.
Not just "economy" but "mortgage rates affecting home sales", not just "ETF investing" but "broad market ETF + dividend aristocrats basics for beginners".
The goal is to give a future writer a precise list of exactly what NOT to repeat, including angles that LOOK different on the surface but cover the same underlying concept or lesson.

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
    """Gemini가 HTML 안에 마크다운 **bold** 같은걸 섞어 쓰는 경우 제거, em dash도 정리"""
    if not text:
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(?!\*)(.+?)(?<!\*)\*(?!\w)", r"\1", text)
    text = text.replace("—", ", ").replace("–", "-")
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text

def generate_post(category, posted_titles, covered_topics, trends, investing_progress=0, recent_tickers=None):
    today = datetime.now().strftime("%B %d, %Y")
    posted_text  = "\n".join(f"- {t}" for t in posted_titles[-20:]) if posted_titles else "None"
    covered_text = ", ".join(covered_topics) if covered_topics else "None"
    recent_tickers = recent_tickers or []
    tickers_text = ", ".join(recent_tickers) if recent_tickers else "None"

    if trends:
        lines = []
        for i, c in enumerate(trends):
            d = f" (published: {c['date']})" if c.get("date") else ""
            lines.append(f"[{i}] {c['title']}{d}")
        trend_text = "\n".join(lines)
    else:
        trend_text = "None available today"

    is_philosophy = category["name"] == "Philosophy for Modern Life"
    is_investing  = category["name"] == "Passive Income Investing"

    common_rules = """
[FORMATTING RULES — MANDATORY]
- Write ONLY valid HTML. NEVER use markdown syntax like **bold** or *italic* or # headers.
- For emphasis, use <strong>word</strong> or <em>word</em> instead of asterisks. Use this sparingly.
- Do NOT wrap words in double asterisks under any circumstance.
- NEVER use the em dash (—) or en dash (–) anywhere in the writing. Use a period, comma, or rewrite the sentence instead. This applies to every single sentence in the post.

[DATE MENTION RULES — MANDATORY]
- Do NOT state today's date as if announcing it (e.g., "It's June 30, 2026" or "Today is June 29, 2026, and..."). This sounds robotic and is often wrong if written ahead of schedule.
- It's fine to cite an article's published date when referencing that specific article (e.g., "a report published on June 29 noted...").
- Open the post naturally without a date-announcement framing.
"""

    if is_philosophy:
        topic_block = f"""
[PHILOSOPHER SELECTION — MANDATORY FIRST STEP]
Before writing, select ONE philosopher or school of thought to write about.
- Choose from ALL of human history and ALL cultures (Western, Eastern, African, Islamic, Latin American, Indigenous, etc.)
- DO NOT choose anyone already covered: {covered_text}
- DO NOT repeat themes from these titles: {posted_text}
- Prioritize lesser-known thinkers when well-known ones are already covered
- Must be someone whose ideas apply to modern everyday life
Then write the entire post about THAT chosen thinker only.
Include the chosen thinker's name in the title naturally.
"""
        structure_block = """
[STRUCTURE]
- Length: 600~900 words
- HTML: <h2> subheadings, <p> paragraphs, <ul><li> lists where appropriate
"""

    elif is_investing:
        if investing_progress < len(INVESTING_CURRICULUM):
            concept = INVESTING_CURRICULUM[investing_progress]
            concept_block = f"""Today's assigned concept (day {investing_progress + 1} of the curriculum): "{concept}"
Explain ONLY this concept, building on nothing except basic prior knowledge from earlier curriculum days."""
        else:
            concept_block = f"""Pick ONE new, specific investing concept not covered before (angles already covered, avoid repeating even with a different title: {covered_text}).
Go beyond basics now, intermediate to advanced concepts are welcome since the reader has completed the beginner curriculum."""

        topic_block = f"""
[MANDATORY 4-PART TOPIC STRUCTURE]
PART 1 - Market News: Summarize what's happening in global markets today using the trend articles below.
PART 2 - Investing Concept: {concept_block}
PART 3 - New Asset/Method Spotlight: Introduce ONE legitimate investment asset, product, or method the reader likely hasn't seen explained here before (examples: gold, silver, oil, REIT subtypes, municipal bonds, TIPS, DRIP, covered call ETFs, P2P lending, international markets, tax-advantaged accounts, annuities, etc). Must be genuinely different from anything already covered: {covered_text}. Explain clearly what it is and how someone could realistically start.
PART 4 - ETF Picks: Recommend exactly 3 ETF tickers based on TODAY's actual market conditions reflected in the trend articles. Do NOT repeat these recently recommended tickers unless there's a strong current-market reason to: {tickers_text}. For each ticker, explain in 1-2 sentences why it fits current conditions.

IMPORTANT: Even if the title sounds different from previous posts, the actual lesson/content in Part 2 and Part 3 must not overlap in substance with anything in the covered topics list. A new angle on the same underlying concept still counts as a repeat.
{INVESTING_SAFETY_RULES}
"""
        structure_block = """
[STRUCTURE]
Use a clear <h2> heading for each of the 4 parts (natural/catchy wording is fine, but must follow this order: Market News, Investing Concept, New Asset Spotlight, ETF Picks).
Length: 900~1300 words (needs room for 4 parts).
End with a short note that investing carries risk of loss of principal.
"""

    elif category["name"] == "World News Simplified":
        topic_block = f"""
[TOPIC SELECTION — MANDATORY]
Cover 3-5 of today's most significant stories from the trend articles above, explained simply for a general reader.
- Select stories that are genuinely DIFFERENT from what's already been covered: {covered_text}
- Do NOT reuse the same individual stories/events as in already published titles, even if they're still in the news cycle: {posted_text}
- If a story has appeared in a recent post, pick a different story from today's trends instead, even if it seems less major.
"""
        structure_block = """
[MANDATORY STRUCTURE]
1. Opening: Start directly with the numbered headline list — NO introductory sentence before it (do not write things like "Some days the news feels scattered, today a few threads run through it"). Just the title, then immediately the numbered list — one short punchy line per story (e.g. "1. South Korea bets $880 billion on the AI race" / "2. Trump's Iran strikes keep markets on edge" / "3. Japan's surprise rate hike"). This gives readers the at-a-glance overview before the deep dive.
2. Main body: cover each of the 3-5 stories with its own <h2> subheading, in the same order as the headline list. For each story, explain what happened, why it matters, and how it connects to the bigger global picture — not just a headline summary.
3. Closing section (<h2>, e.g. "The Big Picture"): in 2-4 SHORT, clear sentences, state plainly what connects today's stories — avoid abstract or flowery language. Write it the way you'd explain it to a smart friend in one breath, not like a philosophical essay. End with a clear, concrete takeaway, not a vague summary.

- Length: 800~1100 words
- HTML: <h2> subheadings, <p> paragraphs (each paragraph should be short — 2-4 sentences max — and properly broken up for readability), <ol><li> for the headline list, <ul><li> for other lists where appropriate
"""

    elif category["name"] == "Travel & Hidden Gems":
        topic_block = f"""
[TOPIC SELECTION — MANDATORY FIRST STEP]
This post must cover 3 SEPARATE, DISTINCT destinations (different cities/towns/regions, not 3 spots within the same city). Pick 3 destinations from the trend articles above if possible (or fresh ones if trends don't apply).
- Cover destinations from ANYWHERE in the world, and the 3 destinations should ideally be from different regions/continents to keep the post globally diverse (e.g., one in Asia, one in Europe, one in the Americas) rather than 3 cities in the same country.
- DO NOT recommend destinations in active conflict zones, war zones, or places under official government travel advisories warning against travel. If a trending article is about such a place, skip it and pick a different one.
- All 3 destinations and the overall angle must be genuinely different from everything already covered: {covered_text}
"""
        structure_block = """
[MANDATORY STRUCTURE]
- Opening: a brief intro framing the post (e.g., a shared theme connecting the 3 picks, like "hidden gems for slow travel" or "places trending right now").
- Main content: cover each of the 3 destinations under its own <h2> subheading with the destination's name in the heading. For each destination, give real, specific detail: what makes it special, a specific neighborhood or landmark worth visiting (with a real address/location where possible), how to get there, and a practical tip.
- For EACH of the 3 destinations, include its own "Know Before You Go" mini-section (can be a short paragraph or small list right within that destination's section, not necessarily a separate <h2>) covering: (a) general safety/security level for travelers there, and (b) approximate cost level with one or two concrete price reference points (e.g., average meal cost, hotel price range in local currency or USD).
- Length: 900~1300 words (need enough room to cover 3 destinations properly)
- HTML: <h2> subheadings, <p> paragraphs, <ul><li> lists where appropriate
"""

    else:
        topic_block = f"""
[TOPIC SELECTION — MANDATORY FIRST STEP]
Look at the trend articles crawled today above. Pick ONE of them as the main subject of this post, and build the entire post around that specific article/topic — go deep on it rather than writing something generic.
- If no trends were collected today, pick any fresh, specific, narrow wellness topic you know to be currently relevant or research-backed — wellness is a huge field (sleep, nutrition, fitness, mental health, longevity, hormones, gut health, skin, relationships, productivity, recovery, supplements, etc.) so feel free to explore any corner of it.
- Do NOT write a broad overview covering multiple generic wellness pillars in one post (like "5 tips for sleep, diet, mindfulness, routines, and burnout") — pick ONE specific thing and go deep.
- The topic must be genuinely different from everything already covered: {covered_text}
"""
        structure_block = """
[STRUCTURE]
- Length: 600~900 words
- HTML: <h2> subheadings, <p> paragraphs, <ul><li> lists where appropriate
"""

    prompt = f"""Write an English blog post for the '{category['name']}' category.
Direction: {category['direction']}
{common_rules}
{topic_block}
[Latest Trend Articles — crawled today]
{trend_text}

[Already Covered Topics — DO NOT repeat these angles, even with a different title or framing]
{covered_text}

[Already Published Titles — avoid similar angles/structure]
{posted_text}

[Writing Style]
- Friendly, conversational — like talking to a friend
- Second person ("you") encouraged
- No cliché endings like "In conclusion" or "Start today!"
- Specific, concrete, and actionable — not vague or generic
- For Passive Income Investing specifically: keep the same friendly, adult conversational tone — do NOT write in a childish or oversimplified voice. Instead, make sure every financial concept is fully explained in plain terms before you use it, with zero assumed prior knowledge. Never use a financial term (yield, expense ratio, compounding, diversification, etc.) without immediately unpacking what it actually means in everyday language, ideally with a concrete example or comparison. The reader should never feel lost or need to look anything up — every idea should click on first read, while the writing still sounds like it's written for a thoughtful adult.
{structure_block}
- Do NOT repeat the title inside the body

[Source Reference]
- For Philosophy and Wellness/Travel/Investing: source_index = index of the ONE trend article used as main source. -1 if none used.
- For World News Simplified ONLY: source_indices = an ARRAY of index numbers for ALL trend articles you referenced in this post (one per story covered). Use source_indices instead of source_index for this category.
- For Passive Income Investing ONLY: also include "tickers" = an ARRAY of the ETF ticker symbols you recommended in Part 4 (e.g. ["VOO", "SCHD", "BND"]).

Respond with ONLY this JSON (no other text):
{{"title": "Title", "content": "HTML body", "tags": ["tag1","tag2","tag3"], "source_index": 0, "source_indices": [], "tickers": []}}"""

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
                    data = json.loads(text)
                    data["title"]   = clean_markdown_artifacts(data.get("title", ""))
                    data["content"] = clean_markdown_artifacts(data.get("content", ""))
                    return data
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
    indices = post_data.get("source_indices")
    if isinstance(indices, list) and indices:
        items = []
        seen = set()
        for idx in indices:
            if not isinstance(idx, int) or idx < 0 or idx >= len(trends):
                continue
            if idx in seen:
                continue
            seen.add(idx)
            article = trends[idx]
            link  = article.get("link", "").strip()
            title = article.get("title", "").strip()
            if not link or not link.startswith("http"):
                continue
            date = f" ({article['date']})" if article.get("date") else ""
            items.append(f'  <li><a href="{link}" target="_blank" rel="noopener">{title}</a>{date}</li>\n')
        if items:
            return '\n<hr/>\n<p><strong>Sources</strong></p>\n<ul>\n' + "".join(items) + '</ul>\n'
        return ""

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

    meta = posted.get("_meta", {})
    investing_progress = meta.get("investing_progress", 0)
    recent_tickers = meta.get("recent_tickers", [])

    for cat in CATEGORIES:
        try:
            name = cat["name"]
            print(f"\n  🔍 [{name}] Collecting trends...")
            trends = crawl_trends(cat["feeds"], cat["feed_kw"])
            print(f"     {len(trends)} trends collected")
            if trends:
                for i, t in enumerate(trends[:5]):
                    print(f"       [{i}] {t['title'][:50]} | {t['link'][:55] if t['link'] else 'no link'}")

            posted_titles = posted.get(name, [])
            print(f"  🧠 [{name}] Analyzing covered topics...")
            covered = extract_covered_topics(name, posted_titles)
            if covered:
                print(f"     Topics to avoid: {', '.join(covered[:8])}")

            print(f"  ✍️  [{name}] Generating post...")
            if name == "Passive Income Investing":
                print(f"     Investing curriculum progress: day {investing_progress + 1}")
                post = generate_post(cat, posted_titles, covered, trends, investing_progress, recent_tickers)
            else:
                post = generate_post(cat, posted_titles, covered, trends)

            sources_html = build_sources_html(post, trends)
            if sources_html:
                print(f"     Source(s) attached")
            else:
                print(f"     No source attached")

            post_url = publish_post(access_token, cat, post, sources_html)
            print(f"  ✅ Published: {post['title']}")
            print(f"     {post_url}")

            posted.setdefault(name, []).append(post["title"])
            posted[name] = posted[name][-50:]

            if name == "Passive Income Investing":
                posted.setdefault("_meta", {})
                posted["_meta"]["investing_progress"] = investing_progress + 1
                new_tickers = post.get("tickers", [])
                if isinstance(new_tickers, list):
                    combined = recent_tickers + [t for t in new_tickers if isinstance(t, str)]
                    posted["_meta"]["recent_tickers"] = combined[-15:]

            success += 1
            time.sleep(3)

        except Exception as e:
            print(f"  ❌ [{cat['name']}] Error: {e}")

    save_posted(posted)
    print(f"\n🎉 Done! {success}/{len(CATEGORIES)} posts published")

if __name__ == "__main__":
    main()
