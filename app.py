import os
import asyncio
import streamlit as st
from openai import OpenAI
import matplotlib.pyplot as plt
from trend_detector import detect_trends  # your custom script

# Initialize OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# App layout
st.set_page_config(page_title="YouTube AI Recommender", layout="wide")
st.title("🎬 YouTube AI Recommender")

# Sidebar chat log
st.sidebar.title("💬 Chat with AI")
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

user_input = st.sidebar.text_input("Ask about videos or trends:")

if st.sidebar.button("Send"):
    if user_input:
        st.session_state.chat_log.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful AI YouTube video assistant."},
                {"role": "user", "content": user_input},
            ],
        )

        ai_reply = response.choices[0].message.content
        st.session_state.chat_log.append({"role": "assistant", "content": ai_reply})

# Display chat history
for msg in st.session_state.chat_log:
    role = "🧑" if msg["role"] == "user" else "🤖"
    st.sidebar.markdown(f"**{role}**: {msg['content']}")

# Middle section – recommended videos / trends
st.subheader("🔥 Current Trending Videos")

if st.button("Detect Trends"):
    with st.spinner("Fetching trending topics..."):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        trends = loop.run_until_complete(detect_trends())

    for t in trends:
        title = t.get("title", "Untitled")
        url = t.get("url", "#")
        thumbnail = t.get("thumbnail", None)
        views_history = t.get("views_history", [100, 300, 800, 2000])  # fallback test data

        # Show video info
        st.markdown(f"🎥 **{title}**")
        if thumbnail:
            st.image(thumbnail, width=250)
        st.write(f"[Watch here]({url})")

        # Plot growth chart
        if views_history and len(views_history) > 1:
            fig, ax = plt.subplots()
            ax.plot(range(len(views_history)), views_history, marker="o")
            ax.set_title(f"📈 Growth of {title[:20]}...")
            ax.set_xlabel("Time")
            ax.set_ylabel("Views")
            st.pyplot(fig)

        st.markdown("---")