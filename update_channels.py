import urllib.request
import re
import json

M3U_URL = "https://iptv-org.github.io/iptv/countries/jp.m3u"
HTML_FILE = "index.html"
PLACEHOLDER_RE = re.compile(r'(?:null|\[.*?\]); // EMBEDDED_DATA_PLACEHOLDER', re.DOTALL)

GENRE_MAP = {
    "📰 뉴스":  ["news","nhk","news24","ann","jnn","fnn","nnn"],
    "🎬 지상파": ["ntv","nippon tv","tbs","fuji","tv asahi","tv tokyo","ytv","mbs","abc","関西"],
    "📡 BS·CS": ["bs","cs","wowow","sky","at-x","dlife"],
    "🛒 쇼핑":  ["shop","qvc","japanet"],
}

def guess_genre(name):
    nl = name.lower()
    for genre, keys in GENRE_MAP.items():
        if any(k in nl for k in keys):
            return genre
    return "🎌 기타"

def parse_m3u(text):
    channels = []
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
                if url.startswith("http"):
                    channels.append({"name": name, "url": url, "genre": guess_genre(name)})
                    i = j + 1
                    continue
        i += 1
    return channels

def main():
    print("[1/3] 채널 목록 다운로드 중...")
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8", errors="ignore")

    channels = parse_m3u(text)
    channels.sort(key=lambda c: (c["genre"], c["name"]))
    print(f"  총 {len(channels)}개 채널")

    print("[2/3] index.html 업데이트 중...")
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    json_data = json.dumps(channels, ensure_ascii=False)
    new_data = f"{json_data}; // EMBEDDED_DATA_PLACEHOLDER"
    html = PLACEHOLDER_RE.sub(new_data, html)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[3/3] 완료! {len(channels)}개 채널 내장됨")

if __name__ == "__main__":
    main()
