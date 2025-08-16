# app.py
import asyncio
import nest_asyncio
import aiohttp
import streamlit as st
from openai import OpenAI
from html import escape

# ======== Page setup ========
st.set_page_config(page_title="YouTube AI Chat Finder", layout="wide", page_icon="🎬")
nest_asyncio.apply()

# ======== Secrets / Clients ========
OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", "")
YOUTUBE_KEY = st.secrets.get("YOUTUBE_API_KEY", "")

if not OPENAI_KEY or not YOUTUBE_KEY:
    st.error("Missing API keys. Go to Streamlit Cloud → Settings → Secrets and add OPENAI_API_KEY and YOUTUBE_API_KEY.")
    st.stop()

client = OpenAI(api_key=OPENAI_KEY)

# ======== Helpers ========
def iso8601_to_seconds(duration: str) -> int:
    """
    Minimal ISO-8601 duration parser for YouTube-like strings, e.g. 'PT1H2M3S', 'PT45S', 'PT12M'
    """
    if not duration or not duration.startswith("PT"):
        return 0
    total = 0
    num = ""
    for ch in duration[2:]:
        if ch.isdigit():
            num += ch
        else:
            if ch == "H":
                total += int(num) * 3600
            elif ch == "M":
                total += int(num) * 60
            elif ch == "S":
                total += int(num)
            num = ""
    return total

def human_views(n: str | int | None) -> str:
    try:
        v = int(n)
    except:
        return "—"
    for unit in ["", "K", "M", "B"]:
        if abs(v) < 1000:
            return f"{v}{unit}"
        v //= 1000
    return f"{v}T"

def human_duration(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"

async def http_json(session, url, params):
    async with session.get(url, params=params) as resp:
        text = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {text}")
        return await resp.json()

# ======== YouTube API ========
Y_SEARCH = "https://www.googleapis.com/youtube/v3/search"
Y_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

async def yt_search(query: str, max_results: int = 8, shorts_only: bool = False):
    """
    Search YouTube. If shorts_only=True, use videoDuration=short (<= 4 minutes by API),
    then we’ll further filter by <= 60 seconds using the videos details call.
    """
    params = {
        "key": YOUTUBE_KEY,
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": max_results,
        "safeSearch": "moderate",
    }
    if shorts_only:
        params["videoDuration"] = "short"

    async with aiohttp.ClientSession() as session:
        data = await http_json(session, Y_SEARCH, params)
        items = data.get("items", [])
        ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
        if not ids:
            return []

        stats_params = {
            "key": YOUTUBE_KEY,
            "id": ",".join(ids),
            "part": "snippet,statistics,contentDetails",
            "maxResults": len(ids),
        }
        details = await http_json(session, Y_VIDEOS, stats_params)
        vids = []
        for it in details.get("items", []):
            dur_sec = iso8601_to_seconds(it.get("contentDetails", {}).get("duration", ""))
            if shorts_only and dur_sec > 60:
                continue  # enforce ≤ 60s for true “Shorts”-like clips
            snippet = it.get("snippet", {})
            stats = it.get("statistics", {})
            thumbs = snippet.get("thumbnails", {})
            thumb_url = (
                (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url")
            )
            vids.append({
                "id": it.get("id"),
                "title": snippet.get("title", "Untitled"),
                "channel": snippet.get("channelTitle", "Unknown"),
                "description": snippet.get("description", ""),
                "thumb": thumb_url,
                "views": stats.get("viewCount"),
                "likes": stats.get("likeCount"),
                "duration": dur_sec,
                "link": f"https://www.youtube.com/watch?v={it.get('id')}",
            })
        return vids

async def yt_trending(region: str = "US", max_results: int = 10, shorts_only: bool = False):
    params = {
        "key": YOUTUBE_KEY,
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": max_results,
    }
    async with aiohttp.ClientSession() as session:
        data = await http_json(session, Y_VIDEOS, params)
        vids = []
        for it in data.get("items", []):
            dur_sec = iso8601_to_seconds(it.get("contentDetails", {}).get("duration", ""))
            if shorts_only and dur_sec > 60:
                continue
            sn = it.get("snippet", {})
            stt = it.get("statistics", {})
            thumbs = sn.get("thumbnails", {})
            thumb_url = (
                (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url")
            )
            vids.append({
                "id": it.get("id"),
                "title": sn.get("title", "Untitled"),
                "channel": sn.get("channelTitle", "Unknown"),
                "description": sn.get("description", ""),
                "thumb": thumb_url,
                "views": stt.get("viewCount"),
                "likes": stt.get("likeCount"),
                "duration": dur_sec,
                "link": f"https://www.youtube.com/watch?v={it.get('id')}",
            })
        return vids

# ======== OpenAI Summarization (parallel) ========
async def summarize_video(video: dict, user_query: str) -> dict:
    """
    Ask the model for a compact summary + a 0–100 relevance score and why.
    Return structured dict so we can render consistently.
    """
    title = video["title"]
    desc = (video.get("description") or "")[:1000]  # keep prompt short
    chan = video["channel"]

    prompt = f"""
You are ranking YouTube results for a user query.

User query: {user_query}

Video:
- Title: {title}
- Channel: {chan}
- Description (truncated): {desc}

Return a short result in **STRICT JSON** with keys:
- "summary": one crisp sentence describing the video (max 28 words).
- "relevance": integer 0-100 for how well this matches the query.
- "why": a short clause on why it matches (max 18 words).
"""

    # Synchronous call inside async flow (fast enough, and we parallelize at task level)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    content = resp.choices[0].message.content

    # Very basic JSON extraction (model already instructed to reply as JSON)
    import json
    parsed = {"summary": "", "relevance": 0, "why": ""}
    try:
        parsed = json.loads(content.strip())
    except Exception:
        # Fallback: just stuff the raw content into summary
        parsed["summary"] = content.strip()

    # clamp relevance
    try:
        r = int(parsed.get("relevance", 0))
        parsed["relevance"] = max(0, min(100, r))
    except:
        parsed["relevance"] = 0

    parsed["summary"] = parsed.get("summary", "")[:220]
    parsed["why"] = parsed.get("why", "")[:120]
    return parsed

# ======== UI Layout ========
left, right = st.columns([0.42, 0.58])

with left:
    st.markdown("## 💬 Chat")
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Hey! Ask me for videos, Shorts, or trending topics. For Shorts, say “include shorts”. To see trends, say “trending”."}
        ]
    # show history
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_input = st.chat_input("Type your request (e.g., 'best RTX 4070 build include shorts' or 'trending AI tools')")

def wants_shorts(text: str) -> bool:
    t = text.lower()
    return "shorts" in t or "short" in t

def wants_trending(text: str) -> bool:
    t = text.lower()
    return "trend" in t or "trending" in t or "new trends" in t

async def run_query_flow(query_text: str):
    shorts_flag = wants_shorts(query_text)
    trending_flag = wants_trending(query_text)

    with right:
        st.markdown("## 📺 Results")
        status = st.status("⏳ Finding videos and generating AI summaries...", expanded=True)

    # Decide data source
    if trending_flag:
        videos = await yt_trending(region="US", max_results=12, shorts_only=shorts_flag)
        header = "🔥 Trending" + (" Shorts" if shorts_flag else "")
    else:
        videos = await yt_search(query_text, max_results=12, shorts_only=shorts_flag)
        header = "🔎 Search results" + (" (Shorts)" if shorts_flag else "")

    if not videos:
        with right:
            st.warning("No videos found. Try another query.")
        return

    # Parallel summarize
    tasks = [summarize_video(v, query_text) for v in videos]
    summaries = await asyncio.gather(*tasks, return_exceptions=True)

    # Combine + rank by relevance
    enriched = []
    for v, s in zip(videos, summaries):
        if isinstance(s, Exception):
            s = {"summary": "Summary unavailable.", "relevance": 0, "why": ""}
        enriched.append({**v, **s})

    enriched.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    with right:
        status.update(label="✅ Done!", state="complete")
        st.markdown(f"### {header}")
        # Best pick card
        best = enriched[0]
        with st.container(border=True):
            st.markdown("🏆 **AI Best Pick**")
            c1, c2 = st.columns([0.36, 0.64])
            with c1:
                if best["thumb"]:
                    st.image(best["thumb"], use_container_width=True)
            with c2:
                st.markdown(f"**[{escape(best['title'])}]({best['link']})**")
                st.markdown(f"👤 {escape(best['channel'])}")
                st.markdown(
                    f"👁️ {human_views(best['views'])} 👍 {human_views(best['likes'])} ⏱️ {human_duration(best['duration'])} 🎯 {best.get('relevance',0)}%"
                )
                st.markdown(f"📝 {escape(best.get('summary',''))}")
                if best.get("why"):
                    st.caption(f"Why: {escape(best['why'])}")

        st.divider()
        st.markdown("#### 📋 All Results")
        for v in enriched:
            with st.container(border=True):
                c1, c2 = st.columns([0.28, 0.72])
                with c1:
                    if v["thumb"]:
                        st.image(v["thumb"], use_container_width=True)
                with c2:
                    st.markdown(f"**[{escape(v['title'])}]({v['link']})**")
                    st.markdown(f"👤 {escape(v['channel'])}")
                    st.markdown(
                        f"👁️ {human_views(v['views'])} 👍 {human_views(v['likes'])} ⏱️ {human_duration(v['duration'])} 🎯 {v.get('relevance',0)}%"
                    )
                    if v.get("summary"):
                        st.caption(escape(v["summary"]))

# ======== Handle chat input ========
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with left:
        with st.chat_message("user"):
            st.markdown(user_input)

    # Generate an assistant acknowledgement immediately
    ack = "Got it — I’m pulling videos" + (" (Shorts)" if wants_shorts(user_input) else "") + (" and trends" if wants_trending(user_input) else "") + "…"
    st.session_state.messages.append({"role": "assistant", "content": ack})
    with left:
        with st.chat_message("assistant"):
            st.markdown(ack)

    # Run the query flow and render results on the right
    asyncio.run(run_query_flow(user_input))
