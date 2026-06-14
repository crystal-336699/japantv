import urllib.request
import re
import json

# 1순위 소스: TvJapan/iptv-jp (akariko.netgenx.site 릴레이) - 94개, 작동 확인됨
# 2순위: Free-TV/IPTV (백업용)
M3U_SOURCES = [
    "https://raw.githubusercontent.com/TvJapan/iptv-jp/main/jp_relay.m3u",
]

HTML_FILE = "index.html"
JSON_FILE = "channels.json"
PLACEHOLDER_RE = re.compile(r'(?:null|\[.*?\]); // EMBEDDED_DATA_PLACEHOLDER', re.DOTALL)

# 그룹명 → 한국어 장르 매핑
GROUP_TO_GENRE = {
    "Tokyo": "🎬 지상파 (도쿄)",
    "BS": "📡 BS",
    "CS": "📡 CS",
    "Information": None,  # 제외
}

# 이름에 이게 포함되면 제외 (성인/NSFW 등)
EXCLUDE_KEYWORDS = ["nsfw", "paradise", "donate", "relay playlist", "paypal"]

def guess_genre_by_name(name):
    """그룹 정보가 없을 때 이름으로 장르 추정 (백업 소스용)"""
    nl = name.lower()
    if any(k in nl for k in ["nhk", "ntv", "tbs", "fuji", "tv asahi", "tv tokyo", "tokyo mx", "テレビ"]):
        return "🎬 지상파 (도쿄)"
    if "bs" in nl:
        return "📡 BS"
    if any(k in nl for k in ["cs", "wowow", "sky", "animax", "at-x"]):
        return "📡 CS"
    return "🎌 기타"

def parse_m3u(text, source_index):
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            name_m = re.search(r',(.+)$', line)
            name = name_m.group(1).strip() if name_m else "알 수 없음"
            nl = name.lower()

            # 제외 키워드 체크
            if any(k in nl for k in EXCLUDE_KEYWORDS):
                i += 1
                continue

            # 그룹 추출
            group_m = re.search(r'group-title="([^"]*)"', line)
            group = group_m.group(1) if group_m else None

            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                if url.startswith("http"):
                    # 장르 결정
                    if group is not None and group in GROUP_TO_GENRE:
                        genre = GROUP_TO_GENRE[group]
                        if genre is None:  # Information 그룹은 제외
                            i = j + 1
                            continue
                    else:
                        genre = guess_genre_by_name(name)

                    channels.append({"name": name, "url": url, "genre": genre})
                    i = j + 1
                    continue
        i += 1
    return channels

def fetch_m3u(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [실패] {e}")
        return ""

def main():
    all_channels = []
    seen_names = set()

    for i, source in enumerate(M3U_SOURCES, 1):
        print(f"[소스 {i}/{len(M3U_SOURCES)}] {source}")
        text = fetch_m3u(source)
        if not text:
            continue
        channels = parse_m3u(text, i)
        added = 0
        for ch in channels:
            key = ch["name"].lower().strip()
            if key not in seen_names:
                seen_names.add(key)
                all_channels.append(ch)
                added += 1
        print(f"  → {added}개 추가 (누적 {len(all_channels)}개)")

    if not all_channels:
        print("[오류] 모든 소스 실패! 기존 데이터 유지")
        return

    # 정렬: 지상파 > BS > CS > 기타
    genre_order = {"🎬 지상파 (도쿄)": 0, "📡 BS": 1, "📡 CS": 2, "🎌 기타": 3}
    all_channels.sort(key=lambda c: (genre_order.get(c["genre"], 9), c["name"]))

    print(f"\n총 {len(all_channels)}개 채널")
    for g in genre_order:
        cnt = sum(1 for c in all_channels if c["genre"] == g)
        print(f"  {g}: {cnt}개")

    # channels.json (PC앱용)
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(all_channels, f, ensure_ascii=False)
    print(f"\n→ {JSON_FILE} 저장 완료")

    # index.html (웹앱용)
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    json_data = json.dumps(all_channels, ensure_ascii=False)
    html = PLACEHOLDER_RE.sub(f"{json_data}; // EMBEDDED_DATA_PLACEHOLDER", html)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"→ {HTML_FILE} 업데이트 완료")
    print(f"\n✅ 웹앱 + PC앱 동시 업데이트 완료!")

if __name__ == "__main__":
    main()
