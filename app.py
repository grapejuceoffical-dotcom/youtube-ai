import streamlit as st
import requests
import os

# --- API KEYS ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# --- Helper to fetch YouTube videos ---
def fetch_youtube_results(query, max_results=4):
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

# --- Streamlit App ---
st.set_page_config(page_title="AI Video Recommender", layout="wide")
st.title("🎬 AI Video Recommender")

# Chat history (persistent across reruns)
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

# Display chat log
for entry in st.session_state.chat_log:
    if entry["role"] == "user":
        st.markdown(f"**🧑 You:** {entry['content']}")
    elif entry["role"] == "assistant":
        st.markdown(f"**🤖 AI:** {entry['content']}")
    elif entry["role"] == "videos":
        st.markdown("**📺 Recommended Videos:**")
        for v in entry["content"]:
            st.markdown(f"[{v['title']}]({v['link']})")
            st.image(v["thumbnail"], use_container_width=True)
            st.caption(f"Channel: {v['channel']}")

# User input box
user_input = st.text_input("Ask for video recommendations (e.g. 'show me trending shorts')")

if st.button("Send"):
    if user_input.strip():
        # Save user message
        st.session_state.chat_log.append({"role": "user", "content": user_input})

        # AI placeholder reply
        st.session_state.chat_log.append({"role": "assistant", "content": f"Looking up videos for: {user_input}"})

        # Fetch YouTube results
        videos = fetch_youtube_results(user_input, max_results=4)
        if videos:
            st.session_state.chat_log.append({"role": "videos", "content": videos})
        else:
            st.session_state.chat_log.append({"role": "assistant", "content": "❌ No videos found."})

        st.experimental_rerun()