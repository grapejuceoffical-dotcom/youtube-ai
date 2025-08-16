import streamlit as st
import asyncio
import aiohttp
import nest_asyncio
import os
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI

# Fix event loop issues
nest_asyncio.apply()

# Load API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# --------- Fetch YouTube Search Results ----------
async def fetch_youtube_results(query, max_results=5):
    search_url = (
        f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video"
        f"&q={query}&maxResults={max_results}&key={YOUTUBE_API_KEY}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"❌ YouTube API error {resp.status}: {text}")
            data = await resp.json()

    results = []
    for item in data.get("items", []):
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        thumbnail = item["snippet"]["thumbnails"]["medium"]["url"]
        results.append({
            "id": video_id,
            "title": title,
            "thumbnail": thumbnail,
            "views": int(100000 + (hash(title) % 1000000)),  # fake demo data
            "growth": round(5 + (hash(video_id) % 30), 2)   # fake demo % growth
        })
    return results

# --------- Summarize with AI ----------
async def summarize_video(title):
    prompt = f"Summarize why the YouTube video '{title}' could be trending."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()

# --------- Async Process ----------
async def process(query):
    videos = await fetch_youtube_results(query)
    summaries = await asyncio.gather(*[summarize_video(v["title"]) for v in videos])
    for v, s in zip(videos, summaries):
        v["summary"] = s
    return videos

# --------- Streamlit App ----------
st.set_page_config(page_title="YouTube AI Trends", layout="wide")

st.title("📊 YouTube AI Analytics Dashboard")
st.markdown("<small>AI-powered recommendations & analytics</small>", unsafe_allow_html=True)

query = st.text_input("🔎 Enter a topic to search:", "AI trends")

if st.button("Search"):
    with st.spinner("Fetching videos..."):
        videos = asyncio.run(process(query))

    # Show results side-by-side
    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("💬 AI Recommendations")
        for v in videos:
            st.markdown(f"<small>**{v['title']}**</small>", unsafe_allow_html=True)
            st.markdown(f"<small>{v['summary']}</small>", unsafe_allow_html=True)
            st.markdown(f"<small>Views: {v['views']} | Growth: {v['growth']}%</small>", unsafe_allow_html=True)
            st.image(v["thumbnail"], use_container_width=True)
            st.markdown("---")

    with col2:
        st.subheader("📈 Analytics (Demo Data)")

        # Create DataFrame for chart
        df = pd.DataFrame(videos)

        # Line chart: Growth %
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(df["title"], df["growth"], marker="o", label="Growth %")
        ax.set_title("Video Growth % (Like YouTube Analytics)", fontsize=12)
        ax.set_ylabel("Growth %")
        ax.set_xticklabels(df["title"], rotation=45, ha="right", fontsize=8)
        ax.legend()
        st.pyplot(fig)

        # Bar chart: Views
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        ax2.bar(df["title"], df["views"], color="red", alpha=0.7)
        ax2.set_title("Views Comparison", fontsize=12)
        ax2.set_ylabel("Views")
        ax2.set_xticklabels(df["title"], rotation=45, ha="right", fontsize=8)
        st.pyplot(fig2)
