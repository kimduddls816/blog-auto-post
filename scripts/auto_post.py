import os
import json
import time
import random
import requests
import base64
from datetime import datetime, timezone
from urllib.parse import urlencode

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
GEMINI_API_KEY   = os.environ["GEMINI_API_KEY"]
WP_CLIENT_ID     = os.environ["WP_CLIENT_ID"]
WP_CLIENT_SECRET = os.environ["WP_CLIENT_SECRET"]
WP_USERNAME      = os.environ["WP_USERNAME"]
WP_PASSWORD      = os.environ["WP_PASSWORD"]
WP_SITE          = os.environ.get("WP_SITE", "wellnesslifeguide.wordpress.com")

POSTED_TOPICS_FILE = "posted_topics.json"
TARGET_POST_COUNT  = 5

# ──────────────────────────────────────────────
# 웰니스 주제 풀 (크롤링 실패 시 폴백용)
# ──────────────────────────────────────────────
FALLBACK_TOPICS = [
    "매일 아침 5분 명상으로 하루를 바꾸는 법",
    "숙면을 위한 저녁 루틴 7가지",
    "디지털 디톡스: 스마트폰 없이 하루 보내기",
    "번아웃 없이 일하는 에너지 관리 전략",
    "마음챙김 식사법으로 폭식 없애기",
    "자연광 산책이 멘탈 건강에 미치는 효과",
    "감사 일기 쓰기: 뇌과학이 증명한 긍정 효과",
    "스트레스 호르몬을 낮추는 호흡법",
    "저녁 스마트폰 사용을 줄이면 생기는 변화",
    "하루 10분 스트레칭으로 만성 피로 줄이기",
    "사회적 연결이 면역력에 미치는 영향",
    "수분 보충의 과학: 물 마시는 올바른 방법",
    "숲 목욕(산림욕)의 스트레스 해소 효과",
    "질 좋은 수면을 위한 침실 환경 만들기",
    "장 건강과 정신 건강의 연결 고리",
    "명상 앱 없이도 할 수 있는 마음챙김 연습",
    "사무실에서 할 수 있는 1분 스트레칭",
    "주말 루틴: 완전한 회복을 위한 하루 설계",
    "직관적 식사란 무엇인가: 다이어트 없이 건강 먹기",
    "소셜미디어와 자존감: 건강한 사용법",
    "저강도 운동이 고강도보다 더 효과적인 이유",
    "냉온 샤워의 건강 효능과 시작하는 방법",
    "독서가 스트레스를 68% 줄이는 이유",
    "인간관계 스트레스를 다루는 경계 설정법",
    "아침형 인간이 되지 않아도 되는 이유",
    "계절성 우울감을 극복하는 생활 습관",
    "창의적 취미가 정신 건강에 미치는 영향",
    "일-생활 균형보다 중요한 '에너지 관리'",
    "불안감을 줄이는 단계별 인지행동 기법",
    "음악 치료: 듣는 것만으로도 치유가 되는 이유",
    "자기 연민(self-compassion) 연습하는 법",
    "미루는 습관 뒤에 숨겨진 감정적 원인",
    "웰빙 여행: 일상에서 벗어나 재충전하는 법",
    "반려동물이 심리적 안정에 미치는 과학적 효과",
    "공황 발작 시 즉시 쓸 수 있는 5가지 기법",
]

# ──────────────────────────────────────────────
# 최신 웰니스 트렌드 크롤링
# ──────────────────────────────────────────────
def crawl_trending_wellness_topics():
    """구글 트렌드 RSS와 웰니스 미디어에서 최신 주제 수집"""
    topics = []

    # 1) Google Trends RSS (웰니스 관련)
    rss_urls = [
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR",
        "https://feeds.feedburner.com/MindBodyGreen",
        "https://www.healthline.com/rss/news",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; WellnessBot/1.0)"}

    for url in rss_urls:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                # title 태그 추출
                import re
                titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", r.text)
                if not titles:
                    titles = re.findall(r"<title>([^<]{10,80})</title>", r.text)
                for t in titles[:10]:
                    t = t.strip()
                    if any(kw in t.lower() for kw in [
                        "wellness", "health", "stress", "sleep", "mental",
                        "건강", "스트레스", "수면", "명상", "다이어트", "운동", "웰니스"
                    ]):
                        topics.append(t)
        except Exception:
            pass

    print(f"[크롤링] 수집된 트렌드 주제: {len(topics)}개")
    return topics[:20]


# ──────────────────────────────────────────────
# 발행된 주제 관리 (중복 방지)
# ──────────────────────────────────────────────
def load_posted_topics():
    if os.path.exists(POSTED_TOPICS_FILE):
        with open(POSTED_TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_posted_topics(topics):
    with open(POSTED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

def is_duplicate(candidate, posted):
    """간단한 유사도 체크 (키워드 2개 이상 겹치면 중복으로 판단)"""
    candidate_words = set(candidate.replace(" ", ""))
    for p in posted:
        p_words = set(p.replace(" ", ""))
        overlap = len(candidate_words & p_words)
        if overlap >= 6:  # 6글자 이상 겹침
            return True
    return False

def pick_topics(count):
    """중복 없는 주제 count개 선택"""
    posted = load_posted_topics()

    # 크롤링 주제 우선, 부족하면 폴백 사용
    crawled = crawl_trending_wellness_topics()
    all_candidates = crawled + FALLBACK_TOPICS
    random.shuffle(all_candidates)

    selected = []
    for topic in all_candidates:
        if len(selected) >= count:
            break
        if not is_duplicate(topic, posted + selected):
            selected.append(topic)

    # 그래도 부족하면 강제로 채움 (타임스탬프 붙여서 유니크하게)
    if len(selected) < count:
        ts = datetime.now().strftime("%m%d")
        extras = [
            f"웰니스 트렌드 {ts}: 마음 건강 지키는 법",
            f"웰니스 트렌드 {ts}: 수면 최적화 가이드",
            f"웰니스 트렌드 {ts}: 번아웃 회복 전략",
            f"웰니스 트렌드 {ts}: 스트레스 해소 루틴",
            f"웰니스 트렌드 {ts}: 자기 돌봄 실천법",
        ]
        for e in extras:
            if len(selected) >= count:
                break
            selected.append(e)

    return selected


# ──────────────────────────────────────────────
# Gemini API 글 생성
# ──────────────────────────────────────────────
def generate_post(topic):
    """Gemini 1.5 Flash로 웰니스 블로그 글 생성"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""웰니스 블로그에 올릴 글을 작성해 주세요.
주제: {topic}

### 글쓰기 방식
- 블로그 운영자가 직접 쓰는 것처럼 자연스럽게 작성
- 특정 직업·나이·성별 언급 없이 누구나 공감할 수 있는 내용
- 독자를 "우리", "여러분"으로 지칭
- 딱딱하지 않고 읽히는 문어체, 문단은 3~4문장으로 짧게 끊기
- 과장 없이 실질적으로 도움되는 정보 위주

### 글 구조 (HTML)
<p>도입: 누구나 공감할 만한 상황이나 질문으로 시작 (2~3문장)</p>

<h2>소제목 1</h2>
<p>핵심 내용 (3~4문장)</p>

<h2>소제목 2</h2>
<p>실천 방법 (3~4문장)</p>
<ul><li>방법 1</li><li>방법 2</li><li>방법 3</li></ul>

<h2>소제목 3</h2>
<p>효과 또는 근거 (3~4문장)</p>

<p>마무리: 부담 없이 시작할 수 있도록 독려 (2문장)</p>

### 응답 형식 (JSON만 출력, 마크다운 없이)
{{
  "title": "읽고 싶어지는 제목 (40자 이내, 주제어 포함)",
  "content": "위 구조의 HTML 본문",
  "excerpt": "글 요약 2문장 (100자 이내)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}"""

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 2000,
        }
    }

    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=60)
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            # JSON 펜스 제거
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            return json.loads(raw.strip())
        except json.JSONDecodeError as e:
            print(f"[Gemini] JSON 파싱 오류 (시도 {attempt+1}/3): {e}")
            time.sleep(3)
        except Exception as e:
            print(f"[Gemini] 요청 오류 (시도 {attempt+1}/3): {e}")
            time.sleep(5)

    return None


# ──────────────────────────────────────────────
# WordPress.com OAuth 토큰 발급
# ──────────────────────────────────────────────
def get_wp_token():
    r = requests.post(
        "https://public-api.wordpress.com/oauth2/token",
        data={
            "client_id":     WP_CLIENT_ID,
            "client_secret": WP_CLIENT_SECRET,
            "grant_type":    "password",
            "username":      WP_USERNAME,
            "password":      WP_PASSWORD,
        },
        timeout=30
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise ValueError(f"토큰 발급 실패: {r.text}")
    print("[WP] 토큰 발급 성공")
    return token


# ──────────────────────────────────────────────
# 이미지 업로드 (Unsplash → WordPress Media)
# ──────────────────────────────────────────────
UNSPLASH_KEYWORDS = [
    "wellness", "meditation", "yoga", "healthy food", "nature walk",
    "sleep", "mindfulness", "green tea", "sunrise", "calm"
]

def fetch_unsplash_image(keyword):
    """Unsplash source에서 이미지 바이너리 다운로드"""
    url = f"https://source.unsplash.com/800x450/?{keyword}"
    try:
        r = requests.get(url, timeout=15, allow_redirects=True)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            return r.content, r.headers.get("Content-Type", "image/jpeg")
    except Exception as e:
        print(f"[이미지] Unsplash 다운로드 실패: {e}")
    return None, None

def upload_image_to_wp(token, image_bytes, content_type, filename):
    """WordPress Media API로 이미지 업로드 후 media ID 반환"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  content_type,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    url = f"https://public-api.wordpress.com/rest/v1.1/sites/{WP_SITE}/media/new"
    try:
        r = requests.post(url, headers=headers, data=image_bytes, timeout=30)
        if r.status_code in (200, 201):
            media = r.json()
            # 응답에 media 배열 또는 직접 ID
            if "media" in media and media["media"]:
                return media["media"][0].get("ID"), media["media"][0].get("URL")
            elif "ID" in media:
                return media["ID"], media.get("URL")
        print(f"[이미지] 업로드 실패 {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[이미지] 업로드 예외: {e}")
    return None, None

def get_featured_image(token, topic):
    """주제에 맞는 키워드로 이미지 업로드 시도"""
    keyword = random.choice(UNSPLASH_KEYWORDS)
    # 주제 키워드 반영
    for kw in ["명상", "수면", "음식", "운동", "자연", "스트레스"]:
        if kw in topic:
            mapping = {"명상": "meditation", "수면": "sleep", "음식": "healthy food",
                       "운동": "yoga", "자연": "nature walk", "스트레스": "mindfulness"}
            keyword = mapping[kw]
            break

    img_bytes, content_type = fetch_unsplash_image(keyword)
    if img_bytes:
        filename = f"wellness-{keyword.replace(' ', '-')}-{int(time.time())}.jpg"
        media_id, media_url = upload_image_to_wp(token, img_bytes, content_type, filename)
        if media_id:
            print(f"[이미지] 업로드 성공: {media_url}")
            return media_id
    print("[이미지] 업로드 실패 — 이미지 없이 발행 진행")
    return None


# ──────────────────────────────────────────────
# 워드프레스 글 발행
# ──────────────────────────────────────────────
def publish_post(token, post_data, featured_media_id=None):
    """WordPress.com REST API로 글 발행"""
    url = f"https://public-api.wordpress.com/rest/v1.1/sites/{WP_SITE}/posts/new"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "title":   post_data["title"],
        "content": post_data["content"],
        "excerpt": post_data.get("excerpt", ""),
        "status":  "publish",
        "tags":    ",".join(post_data.get("tags", [])),
        "categories": "웰니스",
        "format":  "standard",
    }
    if featured_media_id:
        payload["featured_image"] = featured_media_id

    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, data=payload, timeout=30)
            if r.status_code in (200, 201):
                result = r.json()
                post_url = result.get("URL", "")
                post_id  = result.get("ID", "")
                print(f"[WP] 발행 성공: [{post_id}] {post_data['title']} → {post_url}")
                return True
            else:
                print(f"[WP] 발행 실패 {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"[WP] 발행 예외 (시도 {attempt+1}/3): {e}")
            time.sleep(5)

    return False


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
def main():
    print(f"\n{'='*50}")
    print(f"블로그 자동 발행 시작: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")

    # 1. 주제 선택
    topics = pick_topics(TARGET_POST_COUNT)
    print(f"[주제] 선택된 {len(topics)}개: {topics}\n")

    # 2. WP 토큰
    try:
        token = get_wp_token()
    except Exception as e:
        print(f"[오류] WP 토큰 발급 실패: {e}")
        raise

    # 3. 글 생성 + 발행
    posted_topics = load_posted_topics()
    success_count = 0

    for i, topic in enumerate(topics, 1):
        print(f"\n--- [{i}/{TARGET_POST_COUNT}] {topic} ---")

        # Gemini로 글 생성
        post_data = generate_post(topic)
        if not post_data:
            print(f"[스킵] 글 생성 실패: {topic}")
            continue

        # 이미지 업로드
        media_id = get_featured_image(token, topic)

        # 발행
        ok = publish_post(token, post_data, media_id)
        if ok:
            posted_topics.append(topic)
            success_count += 1
        else:
            print(f"[실패] 발행 실패: {topic}")

        # API 요청 간격 (과부하 방지)
        if i < len(topics):
            time.sleep(4)

    # 4. 발행 이력 저장
    save_posted_topics(posted_topics[-200:])  # 최근 200개만 유지

    print(f"\n{'='*50}")
    print(f"완료: {success_count}/{TARGET_POST_COUNT}개 발행 성공")
    print(f"{'='*50}\n")

    if success_count < TARGET_POST_COUNT:
        raise SystemExit(f"목표 미달: {success_count}/{TARGET_POST_COUNT}개만 발행됨")


if __name__ == "__main__":
    main()
