import os
import asyncio
import aiohttp
import nest_asyncio
import streamlit as st
from openai import OpenAI

# Allow asyncio to run inside Streamlit
nest_asyncio.apply()

# Load API keys from Streamlit secrets
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

# Function to fetch YouTube search results
async def fetch_youtube_results(query, max_results=5):
    search_url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?q={query}&part=snippet&type=video&maxResults={max_results}&key={YOUTUBE_API_KEY}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as resp:
            text = await resp.text()
            if resp.status != 200:
                st.error(f"❌ YouTube API error {resp.status}: {text}")
                raise Exception(f"❌ YouTube API error {resp.status}: {text}")
            data = await resp.json()
            return [
                {
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "videoId": item["id"]["videoId"],
                }
                for item in data.get("items", [])
            ]

# Function to summarize a video with OpenAI
async def summarize_video(video):
    prompt = f"""
    Analyze the following YouTube video:

    Title: {video['title']}
    Channel: {video['channel']}

    Provide:
    - A short description
    - Estimated fit to the search query (0–100%)
    - Why it’s a good match
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# Process query and show results
async def process(query):
    st.write("🔎 Searching YouTube...")
    videos = await fetch_youtube_results(query)

    st.subheader("✨ AI’s Best Pick")
    tasks = [summarize_video(video) for video in videos]
    summaries = await asyncio.gather(*tasks)

    for video, summary in zip(videos, summaries):
        st.markdown(
            f"""
            🎥 **{video['title']}**  
            👤 {video['channel']}  
            🔗 [Watch here](https://www.youtube.com/watch?v={video['videoId']})  

            {summary}
            """
        )

# Streamlit UI
st.title("📺 YouTube AI Search")
query = st.text_input("Enter your YouTube search:")
if st.button("Search") and query:
    asyncio.run(process(query))