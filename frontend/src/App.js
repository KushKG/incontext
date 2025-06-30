import React, { useState } from 'react';
import axios from 'axios';
import { Search, Clock, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedSubstories, setExpandedSubstories] = useState(new Set());

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setTimeline(null);
    setExpandedSubstories(new Set());

    try {
      const response = await axios.post('http://localhost:8000/timeline', {
        query: query.trim()
      });
      setTimeline(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate timeline');
    } finally {
      setLoading(false);
    }
  };

  const toggleSubstory = (timeWindowIndex, substoryIndex) => {
    const key = `${timeWindowIndex}-${substoryIndex}`;
    const newExpanded = new Set(expandedSubstories);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedSubstories(newExpanded);
  };

  const formatDate = (dateStr) => {
    try {
      const [year, month, day] = dateStr.split('/');
      return new Date(year, month - 1, day).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 text-center">
            Timeline Generator
          </h1>
          <p className="text-gray-600 text-center mt-2">
            Generate clean, organized timelines from news events
          </p>
        </div>
      </header>

      {/* Search Form */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter your query (e.g., 'Israel Iran war')"
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                disabled={loading}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Generating...' : 'Generate Timeline'}
            </button>
          </div>
        </form>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <p className="mt-4 text-gray-600">Generating your timeline...</p>
          </div>
        )}

        {/* Timeline Results */}
        {timeline && (
          <div className="space-y-6">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-semibold text-gray-900">
                Timeline for "{timeline.query}"
              </h2>
            </div>

            {timeline.timeline.map((timeWindow, timeWindowIndex) => (
              <div key={timeWindowIndex} className="bg-white rounded-lg shadow-sm border">
                {/* Time Window Header */}
                <div className="px-6 py-4 border-b bg-gray-50 rounded-t-lg">
                  <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-primary-600" />
                    <h3 className="text-lg font-semibold text-gray-900">
                      {timeWindow.time_window}
                    </h3>
                  </div>
                </div>

                {/* Substories */}
                <div className="divide-y">
                  {timeWindow.substories.map((substory, substoryIndex) => (
                    <div key={substoryIndex} className="p-6">
                      {/* Substory Summary */}
                      <div className="mb-4">
                        <p className="text-gray-700 leading-relaxed">
                          {substory.summary}
                        </p>
                      </div>

                      {/* Expand/Collapse Button */}
                      <button
                        onClick={() => toggleSubstory(timeWindowIndex, substoryIndex)}
                        className="flex items-center gap-2 text-primary-600 hover:text-primary-700 font-medium text-sm transition-colors"
                      >
                        {expandedSubstories.has(`${timeWindowIndex}-${substoryIndex}`) ? (
                          <>
                            <ChevronUp className="h-4 w-4" />
                            Hide Events
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-4 w-4" />
                            Show Events ({substory.events.length})
                          </>
                        )}
                      </button>

                      {/* Events List */}
                      {expandedSubstories.has(`${timeWindowIndex}-${substoryIndex}`) && (
                        <div className="mt-4 space-y-3">
                          {substory.events.map((event, eventIndex) => (
                            <div key={eventIndex} className="bg-gray-50 rounded-lg p-4">
                              <div className="flex items-start gap-3">
                                <div className="flex-shrink-0">
                                  <div className="w-2 h-2 bg-primary-600 rounded-full mt-2"></div>
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-sm font-medium text-gray-900">
                                      {formatDate(event.date)}
                                    </span>
                                    {event.source_url && (
                                      <a
                                        href={event.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-primary-600 hover:text-primary-700"
                                      >
                                        <ExternalLink className="h-3 w-3" />
                                      </a>
                                    )}
                                  </div>
                                  <p className="text-gray-700 text-sm leading-relaxed">
                                    {event.event}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App; 