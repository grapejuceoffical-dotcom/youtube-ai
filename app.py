import streamlit as st
import aiohttp
import asyncio
from openai import OpenAI
import os
import nest_asyncio

# Allow asyncio to work inside Streamlit
nest_asyncio.apply()

# Initialize OpenAI client (API key comes from Streamlit Secrets)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Function to fetch YouTube search results
async def fetch_youtube_results(query, max_results=5):
    search_url = f"https://ytsearch.googleapis.com/youtube/v3/search?q={query}&part=snippet&type=video&maxResults={max_results}&key={os.environ['YOUTUBE_API_KEY']}"
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as resp:
            data = await resp.json()
            return [
                {
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    "description": item["snippet"]["description"]
                }
                for item in data.get("items", [])
            ]

# Function to summarize a video description
async def summarize_description(desc, url):
    prompt = f"Summarize this YouTube video description in 2 sentences:\n\n{desc}\n\nVideo link: {url}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# Main app
st.title("🎬 YouTube AI Searcher")
st.write("Search YouTube and get AI-generated summaries of videos!")

query = st.text_input("Enter a topic to search:")

if st.button("Search") and query:
    async def process():
        st.write(f"🔎 Searching YouTube for: **{query}** ...")
        videos = await fetch_youtube_results(query)

        if not videos:
            st.error("No videos found. Try another search term.")
            return

        st.subheader("📌 Results:")
        tasks = [summarize_description(v["description"], v["url"]) for v in videos]
        summaries = await asyncio.gather(*tasks)

        for video, summary in zip(videos, summaries):
            st.markdown(f"### [{video['title']}]({video['url']})")
            st.write(summary)

    asyncio.run(process())
