import requests
import json
from sentence_transformers import SentenceTransformer
import hdbscan
from sklearn.cluster import KMeans
from openai import OpenAI
import os
from typing import List, Dict, Any
import trafilatura
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Load your OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Sentence Transformer model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Article retriever using NewsAPI
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"

def get_articles(query: str) -> List[Dict[str, Any]]:
    params = {
        "q": query,
        "pageSize": 10,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": NEWSAPI_KEY
    }
    response = requests.get(NEWSAPI_ENDPOINT, params=params)
    articles = response.json().get("articles", [])

    result = []
    for article in articles:
        result.append({
            'title': article['title'],
            'url': article['url'],
            'text': article['description'] or article['content'] or "",
            'published_at': article['publishedAt'][:10]  # format: YYYY-MM-DD
        })

    print(f"Got {len(result)} articles.")

    return result

def extract_text(url: str):
    try:
        downloaded = trafilatura.fetch_url(url)
        return trafilatura.extract(downloaded)
    except:
        print(f"Failed to extract text from {url}")
        return None

def gpt_event_exraction(article: Dict[str, Any]) -> List[Dict[str, str]]:
    system_prompt = {
        "role": "system",
        "content": (
            "You are an assistant specialized in extracting structured data from text. "
            "When given an input news article or snippet, output a JSON array of objects, "
            "each with event and date fields. "
            "You must include an accurate year, the month and day may be estimated."
            "Dates must be in YYYY/MM/DD format. "
            # "Include only events with clearly specified dates. "
            "Do not output any other text."
        )
    }
    
    article_text = extract_text(article['url'])

    if not article_text:
        return []

    user_prompt = f"""
    Publish Date: 
    
    {article['published_at']}

    Title: 
    
    {article['title']}

    Text: 
    
    {article_text}
    """

    # print(user_prompt)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[system_prompt, {"role": "user", "content": user_prompt}],
        temperature=0.2
    )

    raw = response.choices[0].message.content.strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("\nFailed to parse JSON from GPT. Raw output:")
        print(raw)
        return []


def extract_events(article: Dict[str, Any]) -> List[Dict[str, str]]:
    raw_events = gpt_event_exraction(article)

    for e in raw_events:
        # e['date'] = article['published_at']
        e['source_url'] = article['url']

    return raw_events


def summarize_with_gpt(bullet_points: str) -> str:
    system_prompt = {
        "role": "system",
        "content": "You are an assistant specialized in understanding and summarizing news events."
    }

    user_prompt = f"""
    Summarize the following related news events into a paragraph:

    {bullet_points}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[system_prompt, {"role": "user", "content": user_prompt}],
        temperature=0.3
    )
    
    print(response.choices[0].message.content.strip())

    return response.choices[0].message.content.strip()


def cluster_events(events: List[Dict[str, str]]) -> Dict[int, List[Dict[str, str]]]:
    embeddings = model.encode([e['event'] for e in events])
    clusterer = hdbscan.HDBSCAN(min_cluster_size=2)
    labels = clusterer.fit_predict(embeddings)

    print(f"Found {len(set(labels))} total labels (including noise).")

    clustered = {}
    for idx, label in enumerate(labels):
        # We no longer skip -1 (noise points)
        clustered.setdefault(label, []).append(events[idx])

    # Print all clusters including noise
    for label, items in clustered.items():
        label_str = f"Cluster {label}" if label != -1 else "Noise Cluster (-1)"
        print(f"\n{label_str}:")
        for event in items:
            print(f"- {event['date']}: {event['event']}")

    return clustered


def cluster_by_time(events: List[Dict[str, str]], n_clusters: int = 4) -> Dict[int, List[Dict[str, str]]]:
    def date_to_days(date_str):
        return (datetime.strptime(date_str, "%Y/%m/%d") - datetime(2000, 1, 1)).days

    date_vals = np.array([date_to_days(e['date']) for e in events]).reshape(-1, 1)

    kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init='auto')
    labels = kmeans.fit_predict(date_vals)

    grouped = {}
    for idx, label in enumerate(labels):
        grouped.setdefault(label, []).append(events[idx])

    return grouped


def cluster_temporal_then_semantic(events: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    time_clusters = cluster_by_time(events)
    full_timeline = []

    for label, time_group in sorted(time_clusters.items(), key=lambda x: min(e['date'] for e in x[1])):
        time_group = sorted(time_group, key=lambda e: e['date'])

        # Not enough events → summarize the whole time group
        if len(time_group) < 5:
            bullet_points = "\n".join([f"- {e['date']}: {e['event']}" for e in time_group])
            summary = summarize_with_gpt(bullet_points)
            full_timeline.append({
                "time_window": f"{time_group[0]['date']} – {time_group[-1]['date']}",
                "substories": [{
                    "summary": summary,
                    "events": time_group
                }]
            })
        else:
            # Enough events → run semantic clustering
            semantic_clusters = cluster_events(time_group)
            substories = []

            for sublabel, cluster_events_list in semantic_clusters.items():
                cluster_events_list = sorted(cluster_events_list, key=lambda e: e['date'])
                bullet_points = "\n".join([f"- {e['date']}: {e['event']}" for e in cluster_events_list])
                summary = summarize_with_gpt(bullet_points)
                substories.append({
                    "summary": summary,
                    "events": cluster_events_list
                })

            full_timeline.append({
                "time_window": f"{time_group[0]['date']} – {time_group[-1]['date']}",
                "substories": substories
            })

    return full_timeline

def run_incontext(query: str) -> Dict[str, Any]:
    articles = get_articles(query)
    # events = sum([extract_events(article) for article in articles], [])
    events = [{'event': 'Iran arrests hundreds accused of spying for Israel and fast-tracks executions.', 'date': '2025/06/28', 'source_url': 'https://freerepublic.com/focus/f-news/4325853/posts'}, {'event': 'BBC Persian reports 35 Jewish citizens detained in Iran accused of spying.', 'date': '2025/06/28', 'source_url': 'https://freerepublic.com/focus/f-news/4325853/posts'}, {'event': 'Amnesty International calls on Iran to halt executions.', 'date': '2025/06/28', 'source_url': 'https://freerepublic.com/focus/f-news/4325853/posts'}, {'event': 'IDF Chief of Staff reveals commando forces acted in Iran.', 'date': '2025/06/25', 'source_url': 'https://freerepublic.com/focus/f-news/4325853/posts'}, {'event': 'IDF kills Hakham Muhammad Issa Al-Issa, a key Hamas founder, in an airstrike in Gaza City.', 'date': '2025/06/27', 'source_url': 'https://www.foxnews.com/world/idf-kills-key-hamas-founder-deemed-orchestrator-oct-7-terror-attack-israel'}, {'event': 'IDF kills Abbas Al-Hassan Wahbi, a Hezbollah terrorist, in southern Lebanon.', 'date': '2025/06/28', 'source_url': 'https://www.foxnews.com/world/idf-kills-key-hamas-founder-deemed-orchestrator-oct-7-terror-attack-israel'}, {'event': 'IDF kills Saeed Izadi, an Iranian commander involved in arming and funding Hamas.', 'date': '2025/06/28', 'source_url': 'https://www.foxnews.com/world/idf-kills-key-hamas-founder-deemed-orchestrator-oct-7-terror-attack-israel'}, {'event': 'Israeli strikes kill at least 72 people in Gaza', 'date': '2025/06/28', 'source_url': 'https://www.abc.net.au/news/2025-06-29/israel-strikes-gaza-displacement-tents-ceasefire-talks-improve/105473676'}, {'event': 'US President Donald Trump suggests ceasefire agreement could occur in the next week', 'date': '2025/06/27', 'source_url': 'https://www.abc.net.au/news/2025-06-29/israel-strikes-gaza-displacement-tents-ceasefire-talks-improve/105473676'}, {'event': 'Israeli Minister for Strategic Affairs Ron Dermer to arrive in Washington for talks', 'date': '2025/07/01', 'source_url': 'https://www.abc.net.au/news/2025-06-29/israel-strikes-gaza-displacement-tents-ceasefire-talks-improve/105473676'}, {'event': 'Palestinian Hamas militants attack Israel, taking hostages and killing 1,200 people', 'date': '2023/10/07', 'source_url': 'https://www.abc.net.au/news/2025-06-29/israel-strikes-gaza-displacement-tents-ceasefire-talks-improve/105473676'}, {'event': 'More than 6,000 killed since latest ceasefire ended', 'date': '2025/06/28', 'source_url': 'https://www.abc.net.au/news/2025-06-29/israel-strikes-gaza-displacement-tents-ceasefire-talks-improve/105473676'}, {'event': 'Hundreds killed while seeking food in Gaza', 'date': '2025/06/28', 'source_url': 'https://www.abc.net.au/news/2025-06-29/israel-strikes-gaza-displacement-tents-ceasefire-talks-improve/105473676'}, {'event': 'Israeli strikes killed at least 72 people across Gaza', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'Three children and their parents were killed in an Israeli strike on a tent camp in Muwasi', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': '12 people killed near the Palestine Stadium in Gaza City', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'Eight people killed in apartments in Gaza City', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'A midday strike killed 11 people on a street in eastern Gaza City', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'A strike on a gathering in eastern Gaza City killed eight including five children', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'A strike on a gathering at the entrance to the Bureij refugee camp killed two', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'Two people killed by Israeli gunfire while waiting to receive aid near the Netzarim corridor', 'date': '2025/06/28', 'source_url': 'https://japantoday.com/category/world/at-least-60-people-killed-in-israeli-strikes-in-gaza-as-ceasefire-prospects-inch-closer'}, {'event': 'Trump Administration targets Iranian Christians for deportation.', 'date': '2025/06/19', 'source_url': 'https://reason.com/volokh/2025/06/28/trump-administration-targets-iranian-christians-for-deportation/'}, {'event': 'Pastor Ara Torosian publishes a letter to his church.', 'date': '2025/06/19', 'source_url': 'https://reason.com/volokh/2025/06/28/trump-administration-targets-iranian-christians-for-deportation/'}, {'event': 'ICE agents arrest two Iranian church members in Los Angeles.', 'date': '2025/06/24', 'source_url': 'https://reason.com/volokh/2025/06/28/trump-administration-targets-iranian-christians-for-deportation/'}, {'event': 'Bombing of Iranian nuclear facilities in Fordow, Isfahan, and Natanz by the U.S.', 'date': '2025/06/01', 'source_url': 'https://www.dailysignal.com/2025/06/28/trump-learned-the-lessons-of-iraq/'}, {'event': 'Ceasefire between Israel and Iran', 'date': '2025/06/01', 'source_url': 'https://www.dailysignal.com/2025/06/28/trump-learned-the-lessons-of-iraq/'}, {'event': 'Naftali Bennett calls for a comprehensive hostage deal to end the war in Gaza.', 'date': '2025/06/28', 'source_url': 'https://www.haaretz.com/israel-news/2025-06-28/ty-article/ex-pm-bennett-calls-for-hostage-deal-says-only-a-post-netanyahu-govt-can-defeat-hamas/00000197-b7d6-df21-a1df-f7defefe0000'}, {'event': 'Naftali Bennett announces he will not join a future Netanyahu-led government.', 'date': '2025/06/28', 'source_url': 'https://www.haaretz.com/israel-news/2025-06-28/ty-article/ex-pm-bennett-calls-for-hostage-deal-says-only-a-post-netanyahu-govt-can-defeat-hamas/00000197-b7d6-df21-a1df-f7defefe0000'}, {'event': 'Naftali Bennett criticizes Netanyahu for not preparing for action against Iran.', 'date': '2025/06/28', 'source_url': 'https://www.haaretz.com/israel-news/2025-06-28/ty-article/ex-pm-bennett-calls-for-hostage-deal-says-only-a-post-netanyahu-govt-can-defeat-hamas/00000197-b7d6-df21-a1df-f7defefe0000'}, {'event': 'Naftali Bennett registers a new party for the upcoming Knesset elections.', 'date': '2025/04/01', 'source_url': 'https://www.haaretz.com/israel-news/2025-06-28/ty-article/ex-pm-bennett-calls-for-hostage-deal-says-only-a-post-netanyahu-govt-can-defeat-hamas/00000197-b7d6-df21-a1df-f7defefe0000'}, {'event': 'Naftali Bennett discovers lack of budget for a potential strike on Iran upon taking office.', 'date': '2021/01/01', 'source_url': 'https://www.haaretz.com/israel-news/2025-06-28/ty-article/ex-pm-bennett-calls-for-hostage-deal-says-only-a-post-netanyahu-govt-can-defeat-hamas/00000197-b7d6-df21-a1df-f7defefe0000'}, {'event': 'Israel launched air strikes on Iran', 'date': '2025/06/01', 'source_url': 'https://www.abc.net.au/news/2025-06-29/netanyahus-problems-not-going-away-after-iran-war/105473164'}, {'event': 'Operation Rising Lion officially named', 'date': '2025/06/01', 'source_url': 'https://www.abc.net.au/news/2025-06-29/netanyahus-problems-not-going-away-after-iran-war/105473164'}, {'event': 'Polling released during and after the war suggests no significant shift in voter base', 'date': '2025/06/15', 'source_url': 'https://www.abc.net.au/news/2025-06-29/netanyahus-problems-not-going-away-after-iran-war/105473164'}, {'event': 'Protesters gather in Tel Aviv over ongoing Israel-Gaza war', 'date': '2025/06/28', 'source_url': 'https://www.abc.net.au/news/2025-06-29/netanyahus-problems-not-going-away-after-iran-war/105473164'}, {'event': 'Polling released by Channel 12 on support for ending Gaza war', 'date': '2025/03/01', 'source_url': 'https://www.abc.net.au/news/2025-06-29/netanyahus-problems-not-going-away-after-iran-war/105473164'}, {'event': 'IDF and Mossad operation against Iran', 'date': '2025/06/14', 'source_url': 'https://www.israelnationalnews.com/news/410795'}, {'event': "Ongoing campaign against Iran's terror network", 'date': '2023/10/01', 'source_url': 'https://www.israelnationalnews.com/news/410795'}]
    print(events)

    timeline = cluster_temporal_then_semantic(events)
    return {
        "query": query,
        "timeline": timeline
    }