import os
import streamlit as st
import asyncio
import aiohttp
from openai import OpenAI
from trend_detector import detect_trends  # new trend detector

# Load API keys from Streamlit secrets
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------------
# YouTube Search + Summarization
# -------------------------------
async def fetch_youtube_results(query, max_results=5):
    search_url = (
        f"https://youtube.googleapis.com/youtube/v3/search?q={query}"
        f"&part=snippet&type=video&maxResults={max_results}&key={YOUTUBE_API_KEY}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"❌ YouTube API error {resp.status}: {text}")
            data = await resp.json()
            return data.get("items", [])

async def summarize_video(title, description):
    prompt = f"""
    Summarize this YouTube video briefly in 1-2 sentences:
    Title: {title}
    Description: {description}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()

async def process_query(query):
    videos = await fetch_youtube_results(query)
    results = []
    tasks = []
    for v in videos:
        title = v["snippet"]["title"]
        description = v["snippet"].get("description", "")
        video_id = v["id"]["videoId"]
        channel = v["snippet"]["channelTitle"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        thumbnail = v["snippet"]["thumbnails"]["medium"]["url"]

        tasks.append(summarize_video(title, description))
        results.append({
            "title": title,
            "channel": channel,
            "url": url,
            "thumbnail": thumbnail
        })

    summaries = await asyncio.gather(*tasks)
    for i, s in enumerate(summaries):
        results[i]["summary"] = s
    return results

# -------------------------------
# Streamlit App UI
# -------------------------------
st.set_page_config(page_title="YouTube AI Recommender", layout="wide")

st.title("📺 YouTube AI Explorer")

# 🔥 Trend Detector Section
st.subheader("🔥 Current Trending Videos")
if st.button("Detect Trends"):
    with st.spinner("Fetching trending topics..."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        trends = loop.run_until_complete(detect_trends())
    for t in trends:
        st.markdown(f"**{t['title']}** — {t['views']} views ({t['growth']}% growth)")
        st.image(t["thumbnail"], width=300)
        st.write(f"[Watch here]({t['url']})")

st.divider()

# 🤖 Chat + Recommendations
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

query = st.text_input("💬 Ask for videos (e.g., 'AI news', 'new music', 'funny shorts')")

if st.button("Search"):
    if query:
        st.session_state.chat_log.append({"role": "user", "content": query})
        with st.spinner("Finding videos..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(process_query(query))
        st.session_state.chat_log.append({"role": "assistant", "videos": results})

# Display chat log with videos
for entry in st.session_state.chat_log:
    if entry["role"] == "user":
        st.markdown(f"🧑 **You:** {entry['content']}")
    else:
        st.markdown("🤖 **AI Recommender:**")
        for v in entry["videos"]:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.image(v["thumbnail"], width=120)
            with col2:
                st.markdown(f"🎥 **{v['title']}**  \n👤 {v['channel']}  \n🔗 [Watch]({v['url']})")
                st.markdown(f"📝 {v['summary']}")
        st.markdown("---")
