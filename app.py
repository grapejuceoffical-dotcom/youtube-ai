import streamlit as st
import requests
import os

# --- API KEYS ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# --- Helper to fetch YouTube videos ---
def fetch_youtube_results(query, max_results=6):
    url = f"https://youtube.googleapis.com/youtube/v3/search?q={query}&part=snippet&type=video&maxResults={max_results}&key={YOUTUBE_API_KEY}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    data = resp.json()
    videos = []
    for item in data.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append({
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "thumbnail": snippet["thumbnails"]["medium"]["url"],
            "link": f"https://www.youtube.com/watch?v={video_id}"
        })
    return videos

# --- Streamlit Layout ---
st.set_page_config(page_title="AI YouTube Explorer", layout="wide")

st.title("🎬 AI YouTube Explorer")

# 3 columns: Chat (left), Recommended (center), Search results (right)
col1, col2, col3 = st.columns([2, 5, 2])

# --- Chatbot Section ---
with col1:
    st.subheader("💬 AI Chat")
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    
    for msg in st.session_state["messages"]:
        st.markdown(f"**{msg['role'].capitalize()}:** {msg['content']}")
    
    user_input = st.text_input("Type your message...")
    if st.button("Send"):
        if user_input:
            st.session_state["messages"].append({"role": "user", "content": user_input})
            # (Here you could connect OpenAI to generate a response)
            st.session_state["messages"].append({"role": "assistant", "content": "🤖 This is a placeholder AI response."})

# --- Recommended Videos (Homepage in middle) ---
with col2:
    st.subheader("🔥 Recommended Videos")
    recommended = fetch_youtube_results("trending", max_results=6)
    if recommended:
        for video in recommended:
            st.markdown(f"**[{video['title']}]({video['link']})**")
            st.image(video["thumbnail"], use_container_width=True)
            st.caption(f"📺 {video['channel']}")
    else:
        st.warning("Could not fetch recommended videos.")

# --- Video Search (right side) ---
with col3:
    st.subheader("🔎 Search Videos")
    search_query = st.text_input("Search YouTube")
    if st.button("Search"):
        results = fetch_youtube_results(search_query, max_results=6)
        if results:
            for video in results:
                st.markdown(f"**[{video['title']}]({video['link']})**")
                st.image(video["thumbnail"], use_container_width=True)
                st.caption(f"📺 {video['channel']}")
        else:
            st.warning("No results found.")
