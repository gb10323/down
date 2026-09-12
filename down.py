GB Media Downloader — Streamlit starter application

Important:
- Downloads only public media or media the user is authorized to access.
- Does not bypass private accounts, login walls, DRM, paywalls, or platform restrictions.
- Uses yt-dlp for supported public URLs and FFmpeg for merging/conversion.
- For production deployment, add authentication, rate limits, malware scanning,
  job queues, storage quotas, and a terms-of-use/privacy policy.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

APP_TITLE = "GB Media Downloader"
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = Path(os.getenv("GB_DOWNLOAD_DIR", BASE_DIR / "gb_downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = DOWNLOAD_DIR / "history.json"

QUALITY_MAP = {
    "4K / highest available": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "2K": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "Audio only": "bestaudio/best",
}

SUPPORTED_HINTS = [
    "YouTube", "TikTok", "Instagram public posts/reels",
    "Facebook public videos/reels", "X/Twitter public posts",
    "Threads public posts", "Other sites supported by yt-dlp",
]

def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history(items):
    HISTORY_FILE.write_text(json.dumps(items[-200:], indent=2), encoding="utf-8")

def valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False

def check_dependencies():
    yt_dlp_path = shutil.which("yt-dlp")
    ffmpeg_path = shutil.which("ffmpeg")
    return yt_dlp_path, ffmpeg_path

def run_metadata(url: str):
    """Return public metadata without downloading the media."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--no-playlist",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1200:] or "Could not read public media metadata.")
    return json.loads(result.stdout)

def download_media(url: str, quality_label: str, audio_only: bool, progress_cb=None):
    output_template = str(DOWNLOAD_DIR / "%(uploader|unknown)s_%(title).80s_%(id)s.%(ext)s")
    format_selector = "bestaudio/best" if audio_only else QUALITY_MAP[quality_label]
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--newline",
        "--restrict-filenames",
        "-f", format_selector,
        "--merge-output-format", "mp4",
        "-o", output_template,
        url,
    ]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    lines = []
    for line in process.stdout:
        lines.append(line.rstrip())
        if progress_cb:
            progress_cb(line.rstrip())
    code = process.wait()
    if code != 0:
        raise RuntimeError("\n".join(lines[-15:]) or "Download failed.")
    return lines

def safe_display(value, fallback="Unknown"):
    if value is None or str(value).strip() == "":
        return fallback
    return str(value)

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⬇️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root { --gb-accent: #6c5ce7; }
.block-container { padding-top: 1.3rem; max-width: 1500px; }
.gb-title { font-size: 2.4rem; font-weight: 800; letter-spacing: -1px; }
.gb-subtitle { color: #8a8a8a; margin-top: -12px; }
.gb-card { padding: 1rem; border: 1px solid rgba(128,128,128,.22);
           border-radius: 18px; background: rgba(128,128,128,.045); }
.small-muted { color: #888; font-size: .88rem; }
</style>
""", unsafe_allow_html=True)

if "metadata" not in st.session_state:
    st.session_state.metadata = None
if "last_logs" not in st.session_state:
    st.session_state.last_logs = []

with st.sidebar:
    st.markdown("## GB Control Center")
    page = st.radio("Workspace", ["Downloader", "Library", "System", "About"])
    st.divider()
    st.markdown("### Supported public sources")
    for item in SUPPORTED_HINTS:
        st.caption("• " + item)
    st.divider()
    st.caption("GB stores files on this device/server.")
    st.caption(f"Storage folder: `{DOWNLOAD_DIR}`")

st.markdown('<div class="gb-title">GB Media Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="gb-subtitle">Fast public-media downloading • local storage • metadata • quality control</div>', unsafe_allow_html=True)

if page == "Downloader":
    st.markdown("### Add a media link")
    url = st.text_input(
        "Paste a public media URL",
        placeholder="https://www.youtube.com/watch?v=... or another supported public URL",
    )
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        quality = st.selectbox("Video quality", list(QUALITY_MAP.keys()), index=0)
    with c2:
        audio_only = st.checkbox("Audio only", value=False)
    with c3:
        inspect = st.button("Inspect account/media", use_container_width=True)

    if inspect:
        if not valid_url(url):
            st.error("Enter a valid http/https URL.")
        else:
            with st.spinner("Reading public metadata..."):
                try:
                    st.session_state.metadata = run_metadata(url)
                    st.success("Metadata loaded.")
                except Exception as exc:
                    st.error(str(exc))

    metadata = st.session_state.metadata
    if metadata:
        st.markdown("### Public account/media preview")
        p1, p2 = st.columns([1, 2])
        with p1:
            thumb = metadata.get("thumbnail")
            if thumb:
                st.image(thumb, use_container_width=True)
        with p2:
            st.markdown(f"**Title:** {safe_display(metadata.get('title'))}")
            st.write(f"**Account/uploader:** {safe_display(metadata.get('uploader') or metadata.get('channel'))}")
            st.write(f"**Platform:** {safe_display(metadata.get('extractor_key') or metadata.get('extractor'))}")
            st.write(f"**Duration:** {safe_display(metadata.get('duration'))} seconds")
            st.write(f"**Visibility:** Public metadata only")
            st.caption("Account information is read from the URL's publicly available metadata.")

    st.divider()
    st.markdown("### Download")
    if st.button("⬇️ Start download", type="primary", use_container_width=True):
        if not valid_url(url):
            st.error("Enter a valid http/https URL first.")
        else:
            status = st.empty()
            log_box = st.empty()
            logs = []

            def progress(line):
                logs.append(line)
                status.info(line[-180:])
                log_box.code("\n".join(logs[-12:]))

            try:
                with st.spinner("Downloading and processing media..."):
                    lines = download_media(url, quality, audio_only, progress)
                st.success("Download completed. Open Library to view local files.")
                history = load_history()
                history.append({
                    "url": url,
                    "quality": "audio" if audio_only else quality,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "logs": lines[-5:],
                })
                save_history(history)
            except Exception as exc:
                st.error(f"Download failed: {exc}")
                st.info("Check that the URL is public, supported, and that FFmpeg is installed.")

elif page == "Library":
    st.markdown("### Local media library")
    files = sorted(
        [p for p in DOWNLOAD_DIR.iterdir() if p.is_file() and p.name != HISTORY_FILE.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        st.info("No downloaded files yet.")
    else:
        st.write(f"{len(files)} local file(s)")
        for path in files:
            with st.container(border=True):
                a, b, c = st.columns([3, 1, 1])
                with a:
                    st.write(path.name)
                    st.caption(f"{path.stat().st_size / (1024*1024):.2f} MB")
                with b:
                    with open(path, "rb") as handle:
                        st.download_button(
                            "Export",
                            data=handle.read(),
                            file_name=path.name,
                            key=str(path),
                        )
                with c:
                    if st.button("Delete", key="delete_" + path.name):
                        path.unlink(missing_ok=True)
                        st.rerun()

    st.divider()
    st.markdown("### Download history")
    history = load_history()
    if history:
        st.dataframe(history, use_container_width=True, hide_index=True)
    else:
        st.caption("No history yet.")

elif page == "System":
    st.markdown("### System engine")
    yt, ffmpeg = check_dependencies()
    a, b = st.columns(2)
    with a:
        st.metric("yt-dlp", "Installed" if yt else "Missing")
        st.caption(yt or "Install with: pip install yt-dlp")
    with b:
        st.metric("FFmpeg", "Installed" if ffmpeg else "Missing")
        st.caption(ffmpeg or "Install FFmpeg and add it to PATH")
    st.markdown("### Storage")
    total = sum(p.stat().st_size for p in DOWNLOAD_DIR.glob("**/*") if p.is_file())
    st.metric("GB storage used", f"{total / (1024**3):.3f} GB")
    st.code(str(DOWNLOAD_DIR))
    st.markdown("### Reliability checklist")
    st.write("- Public URL validation")
    st.write("- No-playlist default to avoid accidental bulk downloads")
    st.write("- Local history and library")
    st.write("- Separate metadata inspection")
    st.write("- Explicit dependency checks")
    st.write("- Safe filename restrictions")

elif page == "About":
    st.markdown("### About GB")
    st.write(
        "GB is a Streamlit-based public-media downloader interface. "
        "It can inspect public metadata, download supported public media, "
        "select quality, and store files locally on the computer running Streamlit."
    )
    st.warning(
        "Private Instagram, TikTok, Facebook, Telegram, Threads, X, or YouTube "
        "content cannot be downloaded by this starter unless the user has "
        "legitimate access and the platform/API explicitly permits it. "
        "Do not attempt to bypass authentication, DRM, privacy controls, or rate limits."
    )
    st.markdown("### Production upgrades")
    st.write("- User accounts and encrypted settings")
    st.write("- Background job queue with retry support")
    st.write("- Per-user quotas and cleanup policies")
    st.write("- Cloud/object storage connector")
    st.write("- Virus scanning and file-type validation")
    st.write("- Platform-specific official API integrations")
    st.write("- AI-assisted title/tag/duplicate detection")
