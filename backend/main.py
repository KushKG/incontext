from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import sys
import os

# Add the parent directory to the path to import timeline_generator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timeline_generator import run_incontext

app = FastAPI(title="Timeline Generator API", version="1.0.0")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TimelineRequest(BaseModel):
    query: str

class TimelineResponse(BaseModel):
    query: str
    timeline: List[Dict[str, Any]]

@app.get("/")
async def root():
    return {"message": "Timeline Generator API is running"}

@app.post("/timeline", response_model=TimelineResponse)
async def generate_timeline(request: TimelineRequest):
    try:
        # Use the existing timeline generator function
        result = run_incontext(request.query)
        return TimelineResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating timeline: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 