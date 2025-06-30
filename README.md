# Timeline Generator - Full Stack Application

A full-stack mobile-friendly application that generates clean, organized timelines from news events. The app uses AI-powered clustering and summarization to create structured timelines grouped by time windows and semantic substories.

## Features

- **FastAPI Backend**: RESTful API with timeline generation endpoint
- **React Frontend**: Mobile-first, responsive UI with Tailwind CSS
- **AI-Powered Clustering**: KMeans temporal clustering + HDBSCAN semantic clustering
- **GPT Summarization**: Intelligent summarization of event clusters
- **Collapsible Timeline**: Clean, organized display with expandable event details
- **Mobile-Friendly**: Responsive design that works on all devices

## Project Structure

```
incontext/
├── timeline_generator.py      # Core timeline generation logic
├── requirements.txt           # Python dependencies
├── backend/
│   └── main.py               # FastAPI server
├── frontend/
│   ├── package.json          # Node.js dependencies
│   ├── public/
│   │   └── index.html        # HTML template
│   ├── src/
│   │   ├── App.js            # Main React component
│   │   ├── App.css           # Custom styles
│   │   ├── index.js          # React entry point
│   │   └── index.css         # Tailwind CSS imports
│   ├── tailwind.config.js    # Tailwind configuration
│   └── postcss.config.js     # PostCSS configuration
└── README.md                 # This file
```

## Setup Instructions

### Prerequisites

- Python 3.8+
- Node.js 16+
- OpenAI API key
- NewsAPI key (optional, for real news data)

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file in the root directory:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   NEWSAPI_KEY=your_newsapi_key_here  # Optional
   ```

3. **Start the FastAPI server:**
   ```bash
   cd backend
   python main.py
   ```
   
   The backend will be available at `http://localhost:8000`

### Frontend Setup

1. **Install Node.js dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the React development server:**
   ```bash
   npm start
   ```
   
   The frontend will be available at `http://localhost:3000`

## Usage

1. Open your browser and navigate to `http://localhost:3000`
2. Enter a query in the search box (e.g., "Israel Iran war")
3. Click "Generate Timeline" to create a timeline
4. View the organized timeline with time windows and substories
5. Click "Show Events" to expand and see individual events
6. Click on external link icons to view source articles

## API Endpoints

### POST /timeline

Generates a timeline for the given query.

**Request:**
```json
{
  "query": "Israel Iran war"
}
```

**Response:**
```json
{
  "query": "Israel Iran war",
  "timeline": [
    {
      "time_window": "2023/10/07 – 2023/12/31",
      "substories": [
        {
          "summary": "Summary of events in this time period...",
          "events": [
            {
              "date": "2023/10/07",
              "event": "Hamas attacks Israel...",
              "source_url": "https://example.com/article"
            }
          ]
        }
      ]
    }
  ]
}
```

## How It Works

1. **Event Extraction**: The system fetches news articles and extracts structured events using GPT
2. **Temporal Clustering**: Events are grouped into 4 time windows using KMeans clustering
3. **Semantic Clustering**: Within each time window, events are further clustered by semantic similarity using HDBSCAN
4. **Summarization**: Each cluster (or time window if too few events) is summarized using GPT
5. **Display**: The frontend presents the results in a clean, collapsible timeline format

## Technologies Used

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **OpenAI GPT-4**: AI-powered event extraction and summarization
- **scikit-learn**: KMeans clustering for temporal grouping
- **HDBSCAN**: Density-based clustering for semantic grouping
- **Sentence Transformers**: Text embeddings for semantic similarity

### Frontend
- **React**: Modern JavaScript library for building user interfaces
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Axios**: HTTP client for API communication
- **Lucide React**: Beautiful, customizable icons

## Development

### Backend Development
- The main logic is in `timeline_generator.py`
- The FastAPI server is in `backend/main.py`
- API documentation is available at `http://localhost:8000/docs`

### Frontend Development
- Main component is `frontend/src/App.js`
- Styling uses Tailwind CSS classes
- Icons from Lucide React library

## Environment Variables

- `OPENAI_API_KEY`: Required for GPT event extraction and summarization
- `NEWSAPI_KEY`: Optional for fetching real news articles (currently uses placeholder data)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License. 