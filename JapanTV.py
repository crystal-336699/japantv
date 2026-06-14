import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error
import re
import os
import subprocess
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
M3U_URL   = "https://raw.githubusercontent.com/TvJapan/iptv-jp/main/jp_relay.m3u"
CACHE_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "일본TV", "live_cache.json")
# GitHub Pages에서 최신 채널 목록 가져오기 (Actions로 매일 업데이트)
GITHUB_CHANNELS_URL = "https://crystal-336699.github.io/japantv/channels.json"
VLC_PATHS  = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]

GENRE_KEYWORDS = {
    "📰 뉴스": ["news", "nhk", "news24", "ann", "jnn", "fnn"],
    "🎬 지상파": ["ntv", "nippon tv", "tbs", "fuji", "tv asahi", "tv tokyo", "テレビ", "日テレ", "フジ", "朝日", "東京"],
    "📡 BS/CS": ["bs", "cs", "wowow", "sky", "at-x"],
    "🛒 쇼핑": ["shop", "qvc", "japanet", "ショップ"],
    "🎌 기타": [],
}

def guess_genre(name):
    nl = name.lower()
    for genre, keys in GENRE_KEYWORDS.items():
        if genre == "🎌 기타":
            continue
        for k in keys:
            if k in nl:
                return genre
    return "🎌 기타"

def find_vlc():
    for p in VLC_PATHS:
        if os.path.exists(p):
            return p
    return None

# ─────────────────────────────────────────
# 채널 파싱
# ─────────────────────────────────────────
EXCLUDE_KEYWORDS = ["nsfw", "paradise", "donate", "relay playlist", "paypal"]

def parse_m3u(text):
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            name_m  = re.search(r',(.+)$', line)
            logo_m  = re.search(r'tvg-logo="([^"]*)"', line)
            group_m = re.search(r'group-title="([^"]*)"', line)
            name  = name_m.group(1).strip()  if name_m  else "알 수 없음"
            logo  = logo_m.group(1).strip()  if logo_m  else ""
            group = group_m.group(1).strip() if group_m else ""
            nl = name.lower()
            if any(k in nl for k in EXCLUDE_KEYWORDS) or group == "Information":
                i += 1
                continue
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                if url.startswith("http"):
                    channels.append({"name": name, "url": url, "logo": logo, "group": group})
                    i = j + 1
                    continue
        i += 1
    return channels

def check_url(item, timeout=5):
    try:
        req = urllib.request.Request(
            item["url"],
            headers={"User-Agent": "Mozilla/5.0 VLC/3.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 400
    except:
        return False

# ─────────────────────────────────────────
# 메인 앱
# ─────────────────────────────────────────
class JapanTVApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🇯🇵 일본 TV 채널 선택기")
        self.root.geometry("820x620")
        self.root.configure(bg="#1e1e2e")
        self.root.resizable(True, True)

        self.all_channels = []
        self.live_channels = []
        self.filtered = []
        self.current_proc = None
        self.vlc = find_vlc()

        self._build_ui()
        self._auto_load()

    # ── UI 구성 ──────────────────────────
    def _build_ui(self):
        top = tk.Frame(self.root, bg="#1e1e2e")
        top.pack(fill="x", padx=12, pady=(12,4))

        tk.Label(top, text="🇯🇵 일본 TV", font=("Malgun Gothic", 16, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(side="left")

        self.btn_refresh = tk.Button(top, text="🔄 채널 새로고침",
            command=self._start_check,
            bg="#313244", fg="#cdd6f4", relief="flat",
            padx=10, pady=4, cursor="hand2",
            font=("Malgun Gothic", 9))
        self.btn_refresh.pack(side="right")

        self.lbl_status = tk.Label(top, text="", bg="#1e1e2e", fg="#a6e3a1",
                                   font=("Malgun Gothic", 9))
        self.lbl_status.pack(side="right", padx=10)

        # 진행바
        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=(0,6))

        # 필터 영역
        flt = tk.Frame(self.root, bg="#1e1e2e")
        flt.pack(fill="x", padx=12, pady=(0,6))

        tk.Label(flt, text="장르:", bg="#1e1e2e", fg="#a6adc8",
                 font=("Malgun Gothic", 9)).pack(side="left")

        self.genre_var = tk.StringVar(value="전체")
        genres = ["전체"] + list(GENRE_KEYWORDS.keys())
        self.genre_cb = ttk.Combobox(flt, textvariable=self.genre_var,
                                     values=genres, state="readonly", width=14)
        self.genre_cb.pack(side="left", padx=(4,12))
        self.genre_cb.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        tk.Label(flt, text="검색:", bg="#1e1e2e", fg="#a6adc8",
                 font=("Malgun Gothic", 9)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._apply_filter())
        tk.Entry(flt, textvariable=self.search_var,
                 bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                 relief="flat", font=("Malgun Gothic", 10), width=20).pack(side="left", padx=4)

        self.lbl_count = tk.Label(flt, text="", bg="#1e1e2e", fg="#6c7086",
                                  font=("Malgun Gothic", 9))
        self.lbl_count.pack(side="right")

        # 채널 목록
        frame = tk.Frame(self.root, bg="#1e1e2e")
        frame.pack(fill="both", expand=True, padx=12, pady=(0,8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
            background="#181825", foreground="#cdd6f4",
            fieldbackground="#181825", rowheight=28,
            font=("Malgun Gothic", 10))
        style.configure("Treeview.Heading",
            background="#313244", foreground="#cdd6f4",
            font=("Malgun Gothic", 10, "bold"))
        style.map("Treeview", background=[("selected", "#45475a")])

        cols = ("genre", "name")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                  selectmode="browse")
        self.tree.heading("genre", text="장르")
        self.tree.heading("name",  text="채널명")
        self.tree.column("genre", width=130, anchor="center")
        self.tree.column("name",  width=580)

        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._play_selected())
        self.tree.bind("<Return>",   lambda e: self._play_selected())

        # 하단 버튼
        bot = tk.Frame(self.root, bg="#1e1e2e")
        bot.pack(fill="x", padx=12, pady=(0,12))

        self.lbl_now = tk.Label(bot, text="선택된 채널 없음",
            bg="#1e1e2e", fg="#6c7086", font=("Malgun Gothic", 9))
        self.lbl_now.pack(side="left")

        tk.Button(bot, text="▶  재생",
            command=self._play_selected,
            bg="#89b4fa", fg="#1e1e2e", relief="flat",
            padx=16, pady=6, cursor="hand2",
            font=("Malgun Gothic", 10, "bold")).pack(side="right")

        tk.Button(bot, text="⏹  정지",
            command=self._stop,
            bg="#45475a", fg="#cdd6f4", relief="flat",
            padx=12, pady=6, cursor="hand2",
            font=("Malgun Gothic", 10)).pack(side="right", padx=(0,6))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    # ── 캐시 로드 or 자동 시작 ────────────
    def _auto_load(self):
        # 1. GitHub에서 최신 채널 목록 먼저 시도
        threading.Thread(target=self._load_from_github, daemon=True).start()

    def _load_from_github(self):
        try:
            req = urllib.request.Request(
                GITHUB_CHANNELS_URL,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            if data and len(data) > 0:
                # channels.json은 {name, url, genre} 형식
                self.live_channels = data
                # 로컬 캐시에도 저장
                os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                self.root.after(0, self._populate)
                self.root.after(0, lambda: self._set_status(f"✅ GitHub에서 {len(data)}개 채널 로드됨"))
                return
        except:
            pass
        # 2. GitHub 실패시 로컬 캐시
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, encoding="utf-8") as f:
                    self.live_channels = json.load(f)
                self.root.after(0, self._populate)
                self.root.after(0, lambda: self._set_status(f"캐시에서 {len(self.live_channels)}개 로드됨 (새로고침으로 업데이트)"))
                return
            except:
                pass
        # 3. 둘 다 실패시 직접 다운로드
        self.root.after(0, self._start_check)

    # ── 채널 체크 ─────────────────────────
    def _start_check(self):
        self.btn_refresh.config(state="disabled")
        self._set_status("채널 목록 다운로드 중...")
        self.progress["value"] = 0
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self):
        try:
            req = urllib.request.Request(M3U_URL,
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                text = r.read().decode("utf-8", errors="ignore")
        except Exception as e:
            self.root.after(0, lambda: self._set_status(f"다운로드 실패: {e}"))
            self.root.after(0, lambda: self.btn_refresh.config(state="normal"))
            return

        channels = parse_m3u(text)
        total = len(channels)
        self.root.after(0, lambda: self._set_status(f"총 {total}개 채널 접속 확인 중..."))
        self.root.after(0, lambda: self.progress.config(maximum=total, value=0))

        live = []
        done = [0]

        def on_done(fut, item):
            done[0] += 1
            if fut.result():
                live.append(item)
            self.root.after(0, lambda v=done[0]: self.progress.config(value=v))
            self.root.after(0, lambda: self._set_status(
                f"확인 중... {done[0]}/{total}  (살아있는 채널: {len(live)}개)"))

        with ThreadPoolExecutor(max_workers=30) as ex:
            futs = {ex.submit(check_url, ch): ch for ch in channels}
            for fut, item in futs.items():
                fut.add_done_callback(lambda f, i=item: on_done(f, i))

        # 정렬: 장르 → 이름
        live.sort(key=lambda c: (guess_genre(c["name"]), c["name"]))
        self.live_channels = live

        # 캐시 저장
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(live, f, ensure_ascii=False)

        self.root.after(0, self._populate)
        self.root.after(0, lambda: self._set_status(f"✅ 완료! 살아있는 채널 {len(live)}개"))
        self.root.after(0, lambda: self.btn_refresh.config(state="normal"))

    # ── 목록 표시 ─────────────────────────
    def _populate(self):
        self._apply_filter()

    def _apply_filter(self):
        genre_sel = self.genre_var.get()
        search    = self.search_var.get().lower()

        self.filtered = []
        for ch in self.live_channels:
            g = guess_genre(ch["name"])
            if genre_sel != "전체" and g != genre_sel:
                continue
            if search and search not in ch["name"].lower():
                continue
            self.filtered.append(ch)

        self.tree.delete(*self.tree.get_children())
        for ch in self.filtered:
            g = guess_genre(ch["name"])
            self.tree.insert("", "end", values=(g, ch["name"]))

        self.lbl_count.config(text=f"{len(self.filtered)}개")

    # ── 재생 ──────────────────────────────
    def _play_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("안내", "채널을 먼저 선택하세요.")
            return
        idx   = self.tree.index(sel[0])
        ch    = self.filtered[idx]
        self._launch_vlc(ch)

    def _launch_vlc(self, ch):
        self.lbl_now.config(text=f"▶ 재생 중: {ch['name']}", fg="#a6e3a1")
        if self.current_proc:
            try:
                self.current_proc.terminate()
            except:
                pass

        if self.vlc:
            self.current_proc = subprocess.Popen(
                [self.vlc, "--no-video-title-show", ch["url"]],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # VLC 없으면 기본 브라우저로 열기
            import webbrowser
            webbrowser.open(ch["url"])
            messagebox.showwarning("VLC 없음",
                "VLC가 설치되어 있지 않아 브라우저로 열었습니다.\n"
                "VLC 설치 후 다시 시도하시면 더 잘 됩니다.")

    def _stop(self):
        if self.current_proc:
            try:
                self.current_proc.terminate()
                self.current_proc = None
            except:
                pass
        self.lbl_now.config(text="선택된 채널 없음", fg="#6c7086")

    def _on_select(self, e):
        sel = self.tree.selection()
        if sel:
            idx = self.tree.index(sel[0])
            if idx < len(self.filtered):
                self.lbl_now.config(
                    text=f"선택: {self.filtered[idx]['name']}", fg="#89b4fa")

    def _set_status(self, msg):
        self.lbl_status.config(text=msg)


# ─────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = JapanTVApp(root)
    root.mainloop()
