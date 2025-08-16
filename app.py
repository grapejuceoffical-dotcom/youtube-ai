import os
import asyncio
import aiohttp
import nest_asyncio
import streamlit as st
from openai import OpenAI

# Needed for Streamlit + asyncio
nest_asyncio.apply()

# Initialize OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ----------------------------
# Fetch YouTube videos
# ----------------------------
async def fetch_youtube_results(query, max_results=5):
    YOUTUBE_KEY = os.environ.get("YOUTUBE_API_KEY")
    if not YOUTUBE_KEY:
        raise Exception("❌ Missing YOUTUBE_API_KEY in Streamlit secrets!")

    search_url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?q={query}&part=snippet&type=video&maxResults={max_results}&key={YOUTUBE_KEY}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"❌ YouTube API error {resp.status}: {text}")
            data = await resp.json()

    videos = []
    for item in data.get("items", []):
        videos.append({
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "description": item["snippet"]["description"],
            "link": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
        })
    return videos

# ----------------------------
# Summarize with OpenAI
# ----------------------------
async def summarize_video(video, query):
    prompt = f"""
    User searched for: {query}
    Video title: {video['title']}
    Description: {video['description']}
    Channel: {video['channel']}

    Summarize this video in 2 sentences and say how well it fits the search.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# ----------------------------
# Main async process
# ----------------------------
async def process(query):
    st.info("🔎 Finding videos...")
    videos = await fetch_youtube_results(query)

    tasks = [summarize_video(v, query) for v in videos]
    summaries = await asyncio.gather(*tasks)

    for video, summary in zip(videos, summaries):
        st.write("—" * 40)
        st.markdown(f"🎥 **{video['title']}**")
        st.markdown(f"👤 {video['channel']}")
        st.markdown(f"🔗 [Watch Here]({video['link']})")
        st.markdown(f"📝 {summary}")

# ----------------------------
# Streamlit UI
# ----------------------------
st.title("🎬 YouTube AI Searcher")
query = st.text_input("Enter your search:")

if st.button("Search"):
    if query.strip():
        asyncio.run(process(query))
    else:
        st.warning("Please enter a search term.")
