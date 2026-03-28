import urllib.request
import re
import json

# 여러 소스에서 채널을 합쳐서 최대한 살아있는 채널 확보
M3U_SOURCES = [
    "https://iptv-org.github.io/iptv/countries/jp.m3u",
    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/Japan.m3u8",
]

HTML_FILE = "index.html"
PLACEHOLDER_RE = re.compile(r'(?:null|\[.*?\]); // EMBEDDED_DATA_PLACEHOLDER', re.DOTALL)

GENRE_MAP = {
    "📰 뉴스":  ["news","nhk","news24","ann","jnn","fnn","nnn","japaness24","japa"],
    "🎬 지상파": ["ntv","nippon tv","tbs","fuji","tv asahi","tv tokyo","ytv","mbs","abc","関西","joak","joax","joay","joaz"],
    "📡 BS·CS": ["bs","cs","wowow","sky","at-x","dlife"],
    "🛒 쇼핑":  ["shop","qvc","japanet","gstv"],
}

def guess_genre(name):
    nl = name.lower()
    for genre, keys in GENRE_MAP.items():
        if any(k in nl for k in keys):
            return genre
    return "🎌 기타"

def parse_m3u(text):
    channels = []
    seen_urls = set()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            name_m = re.search(r',(.+)$', line)
            name = name_m.group(1).strip() if name_m else "알 수 없음"
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                if url.startswith("http") and url not in seen_urls:
                    seen_urls.add(url)
                    channels.append({"name": name, "url": url, "genre": guess_genre(name)})
                    i = j + 1
                    continue
        i += 1
    return channels

def fetch_m3u(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [경고] {url} 다운로드 실패: {e}")
        return ""

def main():
    all_channels = []
    seen_urls = set()

    for i, source in enumerate(M3U_SOURCES, 1):
        print(f"[{i}/{len(M3U_SOURCES)}] 다운로드 중: {source}")
        text = fetch_m3u(source)
        if text:
            channels = parse_m3u(text)
            # 중복 URL 제거하며 합치기
            for ch in channels:
                if ch["url"] not in seen_urls:
                    seen_urls.add(ch["url"])
                    all_channels.append(ch)
            print(f"  → {len(channels)}개 채널 파싱, 누적: {len(all_channels)}개")

    all_channels.sort(key=lambda c: (c["genre"], c["name"]))
    print(f"\n총 {len(all_channels)}개 채널")

    print("index.html 업데이트 중...")
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    json_data = json.dumps(all_channels, ensure_ascii=False)
    new_data = f"{json_data}; // EMBEDDED_DATA_PLACEHOLDER"
    html = PLACEHOLDER_RE.sub(new_data, html)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"완료! {len(all_channels)}개 채널 내장됨")

if __name__ == "__main__":
    main()
