import os
import aiohttp
import asyncio
import datetime

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # make sure this is set in Streamlit secrets

# 🔹 Fetch recent videos for a keyword/topic
async def fetch_recent_videos(query="trending", max_results=10):
    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&order=date&maxResults={max_results}"
        f"&q={query}&key={YOUTUBE_API_KEY}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"❌ YouTube API error {resp.status}: {text}")
            return await resp.json()

# 🔹 Get video stats (views, likes, etc.)
async def fetch_video_stats(video_id):
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=statistics&id={video_id}&key={YOUTUBE_API_KEY}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            stats = data["items"][0]["statistics"]
            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }

# 🔹 Simple trend score = views ÷ (1 + hours since published)
def calculate_trend_score(views, published_at):
    published_time = datetime.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    hours_since = max((datetime.datetime.now(datetime.timezone.utc) - published_time).total_seconds() / 3600, 1)
    return round(views / hours_since, 2)

# 🔹 Main trend detection
async def detect_trends(query="trending", max_results=10):
    results = await fetch_recent_videos(query, max_results)
    tasks = []
    videos = []

    for item in results["items"]:
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        published_at = item["snippet"]["publishedAt"]
        thumbnail = item["snippet"]["thumbnails"]["medium"]["url"]

        tasks.append(fetch_video_stats(video_id))
        videos.append({"id": video_id, "title": title, "published_at": published_at, "thumbnail": thumbnail})

    stats_list = await asyncio.gather(*tasks)

    # Attach stats + trend score
    for i, stats in enumerate(stats_list):
        videos[i].update(stats)
        videos[i]["trend_score"] = calculate_trend_score(stats["views"], videos[i]["published_at"])

    # Sort by trend score (highest first)
    return sorted(videos, key=lambda x: x["trend_score"], reverse=True)

# 🔹 Test it
if __name__ == "__main__":
    async def main():
        trending = await detect_trends("shorts", 5)
        for vid in trending:
            print(f"🔥 {vid['title']} | Trend Score: {vid['trend_score']} | Views: {vid['views']}")
    asyncio.run(main())
