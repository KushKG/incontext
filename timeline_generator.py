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
        e['source_url'] = article['url']

    return raw_events


def summarize_with_gpt(bullet_points: str):
    system_prompt = {
        "role": "system",
        "content": "You are an assistant specialized in understanding and summarizing news events."
    }

    user_prompt = f"""
    Given the following list of related news events, do two things:

    1. Write a short, informative **title** (max 7 words) that captures the main theme.
    2. Write a concise **summary paragraph** that connects the events.

    Format your response exactly like this:

    Title: <your title here>
    Summary: <your paragraph summary here>

    Events:
    {bullet_points}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[system_prompt, {"role": "user", "content": user_prompt}],
        temperature=0.3
    )
    output = response.choices[0].message.content.strip()

    # Split the response
    title = ""
    summary = ""
    for line in output.splitlines():
        if line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
        elif line.startswith("Summary:"):
            summary = line.replace("Summary:", "").strip()
        elif title and summary:
            break

    return title, summary


def cluster_events(events: List[Dict[str, str]]) -> Dict[int, List[Dict[str, str]]]:
    embeddings = model.encode([e['event'] for e in events])
    clusterer = hdbscan.HDBSCAN(min_cluster_size=2)
    labels = clusterer.fit_predict(embeddings)

    print(f"Found {len(set(labels))} total clusters (including noise).")

    clustered = {}
    for idx, label in enumerate(labels):
        # We no longer skip -1 (noise points)
        clustered.setdefault(label, []).append(events[idx])

    # # Print all clusters including noise
    # for label, items in clustered.items():
    #     label_str = f"Cluster {label}" if label != -1 else "Noise Cluster (-1)"
    #     print(f"\n{label_str}:")
    #     for event in items:
    #         print(f"- {event['date']}: {event['event']}")

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
            title, summary = summarize_with_gpt(bullet_points)

            full_timeline.append({
                "time_window": f"{time_group[0]['date']} – {time_group[-1]['date']}",
                "substories": [{
                    "title": title,
                    "summary": summary,
                    "events": time_group,
                }]
            })
        else:
            # Enough events → run semantic clustering
            semantic_clusters = cluster_events(time_group)
            substories = []

            for sublabel, cluster_events_list in semantic_clusters.items():
                cluster_events_list = sorted(cluster_events_list, key=lambda e: e['date'])
                bullet_points = "\n".join([f"- {e['date']}: {e['event']}" for e in cluster_events_list])
                title, summary = summarize_with_gpt(bullet_points)

                substories.append({
                    "title": title,
                    "summary": summary,
                    "events": cluster_events_list,
                })

            full_timeline.append({
                "time_window": f"{time_group[0]['date']} – {time_group[-1]['date']}",
                "substories": substories
            })

    return full_timeline

def run_incontext(query: str) -> Dict[str, Any]:
    articles = get_articles(query)
    events = sum([extract_events(article) for article in articles], [])
    # events = [{'event': 'Republican-led Senate advanced a sweeping domestic policy package for President Donald Trump’s agenda.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Thom Tillis announced he would not run for re-election.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Zohran Mamdani, presumptive Democratic nominee for NYC mayor, said billionaires should not exist.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': "Sen. Chris Murphy called Trump's military strikes on Iranian nuclear facilities 'illegal'.", 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Florida is constructing a $450 million-a-year immigration detention center in the Everglades.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Detroit Mayor Mike Duggan announced running for Michigan governor as an independent.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': "Average air quality index in Hanoi breached 'hazardous' threshold of 300.", 'date': '2025/01/15', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Israeli Defense Forces killed Hamas co-founder Hakham Muhammad Issa Al-Issa in Gaza City.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'At least 71 people were killed in an Israeli attack on Tehran’s Evin prison.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Former Minnesota House Speaker Melissa Hortman was laid to rest.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': "Beyoncé's concert in Houston was interrupted due to a flying-car prop malfunction.", 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Funeral held for Adriana Smith, kept on life support until her baby was born.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Democratic Republic of Congo and Rwanda signed a U.S.-mediated peace deal.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Budapest Pride defied a ban under Hungary’s new law.', 'date': '2025/06/28', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Explosion and fire in Philadelphia resulted in one death and two injuries.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'NBA cooperating with a federal investigation into Malik Beasley.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/news/us-news/weekend-rundown-june-29-rcna215664'}, {'event': 'Zohran Mamdani wins New York City mayoral primary election against Andrew Cuomo.', 'date': '2025/06/24', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-as-new-york-mayoral-candidate-for-democratic-party-only-helps-donald-trump-in-midterm-elections-feel-worried-democrats/articleshow/122147321.cms'}, {'event': 'Donald Trump returns to the White House and Republicans win control of Congress.', 'date': '2024/11/05', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-as-new-york-mayoral-candidate-for-democratic-party-only-helps-donald-trump-in-midterm-elections-feel-worried-democrats/articleshow/122147321.cms'}, {'event': 'Eric Adams runs as an independent in the upcoming New York mayoral election.', 'date': '2025/11/04', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-as-new-york-mayoral-candidate-for-democratic-party-only-helps-donald-trump-in-midterm-elections-feel-worried-democrats/articleshow/122147321.cms'}, {'event': "Zohran Mamdani criticized for his stance on Israel's war in Gaza.", 'date': '2025/06/01', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-as-new-york-mayoral-candidate-for-democratic-party-only-helps-donald-trump-in-midterm-elections-feel-worried-democrats/articleshow/122147321.cms'}, {'event': "Cuomo's election loss in Democratic primary reveals weakened NYC unions", 'date': '2025/06/29', 'source_url': 'https://nypost.com/2025/06/29/us-news/cuomos-election-loss-reveals-onetime-kingmaker-nyc-unions-now-toothless-paper-tigers/'}, {'event': 'Zohran Mamdani wins Democratic primary race for mayor', 'date': '2025/06/29', 'source_url': 'https://nypost.com/2025/06/29/us-news/cuomos-election-loss-reveals-onetime-kingmaker-nyc-unions-now-toothless-paper-tigers/'}, {'event': 'Union membership in New York City falls to about 20% in 2024', 'date': '2024/01/01', 'source_url': 'https://nypost.com/2025/06/29/us-news/cuomos-election-loss-reveals-onetime-kingmaker-nyc-unions-now-toothless-paper-tigers/'}, {'event': 'Many union households voted for Republican President Trump', 'date': '2024/01/01', 'source_url': 'https://nypost.com/2025/06/29/us-news/cuomos-election-loss-reveals-onetime-kingmaker-nyc-unions-now-toothless-paper-tigers/'}, {'event': "Zohran Mamdani wins New York City's mayoral primary", 'date': '2025/06/22', 'source_url': 'https://www.foxnews.com/media/democratic-socialist-candidate-nyc-mayor-gift-republican-party-gop-senator-says'}, {'event': 'Curtis Sliwa vows to stay in NYC mayoral race', 'date': '2025/06/29', 'source_url': 'https://www.foxnews.com/politics/sliwa-slams-exit-rumors-blames-adams-mamdani-rise-talks-possible-trump-endorsement'}, {'event': 'Curtis Sliwa survived a mob hit', 'date': '1992/01/01', 'source_url': 'https://www.foxnews.com/politics/sliwa-slams-exit-rumors-blames-adams-mamdani-rise-talks-possible-trump-endorsement'}, {'event': 'Curtis Sliwa ran against Eric Adams in NYC mayoral election', 'date': '2021/11/02', 'source_url': 'https://www.foxnews.com/politics/sliwa-slams-exit-rumors-blames-adams-mamdani-rise-talks-possible-trump-endorsement'}, {'event': 'Eric Adams faced federal corruption charges', 'date': '2023/01/01', 'source_url': 'https://www.foxnews.com/politics/sliwa-slams-exit-rumors-blames-adams-mamdani-rise-talks-possible-trump-endorsement'}, {'event': 'Charges against Eric Adams were dropped by Trump administration', 'date': '2023/01/01', 'source_url': 'https://www.foxnews.com/politics/sliwa-slams-exit-rumors-blames-adams-mamdani-rise-talks-possible-trump-endorsement'}, {'event': 'Andrew Cuomo lost Democratic primary to Zohran Mamdani', 'date': '2025/06/22', 'source_url': 'https://www.foxnews.com/politics/sliwa-slams-exit-rumors-blames-adams-mamdani-rise-talks-possible-trump-endorsement'}, {'event': "Trump threatened to cut New York City's federal funding if Zohran Mamdani wins the mayoral election.", 'date': '2025/06/29', 'source_url': 'https://www.salon.com/2025/06/29/not-getting-any-money-trump-says-hell-pull-nycs-federal-funding-if-mamdani-wins-mayorship/'}, {'event': "Zohran Mamdani discussed his campaign and platform on 'Meet the Press'.", 'date': '2025/06/29', 'source_url': 'https://www.salon.com/2025/06/29/not-getting-any-money-trump-says-hell-pull-nycs-federal-funding-if-mamdani-wins-mayorship/'}, {'event': "Zohran Mamdani wins the Democratic primary for NYC mayor's race.", 'date': '2025/06/24', 'source_url': 'https://fortune.com/2025/06/29/zohran-mamdani-new-york-city-mayoral-race-billionaires-communist-trump/'}, {'event': 'Zohran Mamdani interviewed on NBC’s Meet the Press.', 'date': '2025/06/29', 'source_url': 'https://fortune.com/2025/06/29/zohran-mamdani-new-york-city-mayoral-race-billionaires-communist-trump/'}, {'event': 'Bill Ackman pledges to bankroll any candidate capable of defeating Mamdani.', 'date': '2025/06/25', 'source_url': 'https://fortune.com/2025/06/29/zohran-mamdani-new-york-city-mayoral-race-billionaires-communist-trump/'}, {'event': 'NYC general election scheduled for November 4.', 'date': '2025/11/04', 'source_url': 'https://fortune.com/2025/06/29/zohran-mamdani-new-york-city-mayoral-race-billionaires-communist-trump/'}, {'event': 'Zohran Mamdani, presumptive Democratic nominee for NYC mayor, states billionaires should not exist.', 'date': '2025/06/29', 'source_url': 'https://www.nbcnews.com/politics/elections/zohran-mamdani-says-dont-think-billionaires-rcna215821'}, {'event': 'Bill Ackman pledges to fund a challenger to Zohran Mamdani in the general election.', 'date': '2025/06/26', 'source_url': 'https://www.nbcnews.com/politics/elections/zohran-mamdani-says-dont-think-billionaires-rcna215821'}, {'event': 'Donald Trump threatens to pull federal funding from NYC if Mamdani becomes mayor.', 'date': '2025/06/27', 'source_url': 'https://www.nbcnews.com/politics/elections/zohran-mamdani-says-dont-think-billionaires-rcna215821'}, {'event': 'Diamant Hysenaj announces challenge against Alexandria Ocasio-Cortez', 'date': '2025/06/29', 'source_url': 'https://nypost.com/2025/06/29/us-news/diamant-hysenaj-gop-businessman-and-immigrant-from-kosovo-to-challenge-aoc/'}, {'event': "Hysenaj's family leaves Kosovo due to war", 'date': '1991/01/01', 'source_url': 'https://nypost.com/2025/06/29/us-news/diamant-hysenaj-gop-businessman-and-immigrant-from-kosovo-to-challenge-aoc/'}, {'event': 'Alexandria Ocasio-Cortez first elected to Congress', 'date': '2018/11/06', 'source_url': 'https://nypost.com/2025/06/29/us-news/diamant-hysenaj-gop-businessman-and-immigrant-from-kosovo-to-challenge-aoc/'}, {'event': 'Zohran Mamdani wins Democratic primary for mayor', 'date': '2025/06/22', 'source_url': 'https://nypost.com/2025/06/29/us-news/diamant-hysenaj-gop-businessman-and-immigrant-from-kosovo-to-challenge-aoc/'}, {'event': 'Zohran Mamdani proposes a 2% Millionaire Tax on New Yorkers earning over $1 million annually.', 'date': '2025/06/29', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-pushes-2-millionaire-tax-on-nycs-richest-is-there-a-mayhem-ahead-for-the-rich/articleshow/122145795.cms'}, {'event': 'Zohran Mamdani enters politics.', 'date': '2021/01/01', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-pushes-2-millionaire-tax-on-nycs-richest-is-there-a-mayhem-ahead-for-the-rich/articleshow/122145795.cms'}, {'event': 'New York State collected $108.6 billion in tax revenue for the 2022–2023 fiscal year.', 'date': '2023/01/01', 'source_url': 'https://economictimes.indiatimes.com/news/international/us/zohran-mamdani-pushes-2-millionaire-tax-on-nycs-richest-is-there-a-mayhem-ahead-for-the-rich/articleshow/122145795.cms'}]
    print(events)

    timeline = cluster_temporal_then_semantic(events)

    return {
        "query": query,
        "timeline": timeline
    }