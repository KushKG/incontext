import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Search, Clock, ChevronDown, ChevronUp, ExternalLink, ArrowLeft, ArrowRight, Calendar, ChevronRight } from 'lucide-react';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedSubstories, setExpandedSubstories] = useState(new Set());
  const [activeCluster, setActiveCluster] = useState(0);
  const timelineRef = useRef(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setTimeline(null);
    setExpandedSubstories(new Set());
    setActiveCluster(0);

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

  const scrollToCluster = (index) => {
    if (timelineRef.current) {
      const clusterElement = timelineRef.current.children[index];
      if (clusterElement) {
        clusterElement.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
          inline: 'start'
        });
      }
    }
    setActiveCluster(index);
  };

  const handleScroll = () => {
    if (timelineRef.current) {
      const container = timelineRef.current;
      const scrollLeft = container.scrollLeft;
      const containerWidth = container.clientWidth;
      
      // Find which cluster is most visible
      const clusterWidth = containerWidth * 0.8; // Assuming each cluster takes 80% of viewport
      const newActiveCluster = Math.round(scrollLeft / clusterWidth);
      setActiveCluster(Math.max(0, Math.min(newActiveCluster, timeline?.timeline?.length - 1 || 0)));
    }
  };

  useEffect(() => {
    const container = timelineRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll);
      return () => container.removeEventListener('scroll', handleScroll);
    }
  }, [timeline]);

  // Reverse timeline to show most recent first
  const reversedTimeline = timeline?.timeline ? [...timeline.timeline].reverse() : [];

  // Calculate total events and substories for each time window
  const getTimeWindowStats = (timeWindow) => {
    const totalEvents = timeWindow.substories.reduce((sum, substory) => sum + substory.events.length, 0);
    const totalSubstories = timeWindow.substories.length;
    return { totalEvents, totalSubstories };
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm shadow-sm border-b sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900 text-center bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
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
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm"
                disabled={loading}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-8 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-medium rounded-xl hover:from-blue-700 hover:to-purple-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl"
            >
              {loading ? 'Generating...' : 'Generate Timeline'}
            </button>
          </div>
        </form>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600 text-lg">Generating your timeline...</p>
          </div>
        )}
      </div>

      {/* Timeline Results */}
      {timeline && (
        <div className="max-w-7xl mx-auto px-4 pb-12">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">
              Timeline for "{timeline.query}"
            </h2>
            <p className="text-gray-600">Scroll horizontally to explore different time periods</p>
          </div>

          {/* Cluster Navigation */}
          {reversedTimeline.length > 1 && (
            <div className="flex justify-center mb-6">
              <div className="flex items-center gap-2 bg-white rounded-full p-2 shadow-lg">
                <button
                  onClick={() => scrollToCluster(Math.max(0, activeCluster - 1))}
                  disabled={activeCluster === 0}
                  className="p-2 rounded-full hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                
                <div className="flex gap-1 px-2">
                  {reversedTimeline.map((_, index) => (
                    <button
                      key={index}
                      onClick={() => scrollToCluster(index)}
                      className={`w-2 h-2 rounded-full transition-all ${
                        index === activeCluster 
                          ? 'bg-blue-600 w-6' 
                          : 'bg-gray-300 hover:bg-gray-400'
                      }`}
                    />
                  ))}
                </div>
                
                <button
                  onClick={() => scrollToCluster(Math.min(reversedTimeline.length - 1, activeCluster + 1))}
                  disabled={activeCluster === reversedTimeline.length - 1}
                  className="p-2 rounded-full hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {/* Horizontal Timeline */}
          <div 
            ref={timelineRef}
            className="flex gap-8 overflow-x-auto scrollbar-hide pb-8 snap-x snap-mandatory"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            {reversedTimeline.map((timeWindow, timeWindowIndex) => {
              const stats = getTimeWindowStats(timeWindow);
              const isActive = timeWindowIndex === activeCluster;
              
              return (
                <div 
                  key={timeWindowIndex} 
                  className="flex-shrink-0 w-full max-w-4xl snap-start"
                >
                  <div className={`bg-white rounded-2xl shadow-xl border-2 overflow-hidden transition-all duration-300 ${
                    isActive 
                      ? 'border-blue-500 shadow-2xl scale-105' 
                      : 'border-gray-100 hover:border-gray-200'
                  }`}>
                    {/* Time Window Header */}
                    <div className={`px-8 py-6 transition-all duration-300 ${
                      isActive 
                        ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white' 
                        : 'bg-gradient-to-r from-gray-600 to-gray-700 text-white'
                    }`}>
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg transition-all duration-300 ${
                          isActive ? 'bg-white/20' : 'bg-white/10'
                        }`}>
                          <Calendar className="h-6 w-6" />
                        </div>
                        <div>
                          <h3 className="text-2xl font-bold">
                            {timeWindow.time_window}
                          </h3>
                          <p className={`text-sm mt-1 transition-all duration-300 ${
                            isActive ? 'text-blue-100' : 'text-gray-300'
                          }`}>
                            {stats.totalEvents} events, {stats.totalSubstories} substory{stats.totalSubstories !== 1 ? 'ies' : 'y'}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Substories Grid */}
                    <div className="p-8">
                      <div className="grid gap-6">
                        {timeWindow.substories.map((substory, substoryIndex) => {
                          const isExpanded = expandedSubstories.has(`${timeWindowIndex}-${substoryIndex}`);
                          const summaryPreview = substory.summary.length > 150 
                            ? substory.summary.substring(0, 150) + '...' 
                            : substory.summary;
                          
                          return (
                            <div 
                              key={substoryIndex} 
                              className="bg-gradient-to-br from-gray-50 to-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-lg transition-all duration-200"
                            >
                              {/* Substory Header */}
                              <div className="px-6 py-4 bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-200">
                                <div className="flex items-center justify-between">
                                  <h4 className="font-semibold text-gray-900">
                                    {console.log(substory)}
                                    {substory.title || `Substory ${substoryIndex + 1}`}
                                  </h4>
                                  <span className="text-sm text-gray-500">
                                    {substory.events.length} event{substory.events.length !== 1 ? 's' : ''}
                                  </span>
                                </div>
                              </div>

                              {/* Substory Content */}
                              <div className="p-6">
                                {/* Summary Preview */}
                                <div className="mb-4">
                                  <p className="text-gray-700 leading-relaxed text-lg">
                                    {isExpanded ? substory.summary : summaryPreview}
                                  </p>
                                </div>

                                {/* Read More / Show Events Button */}
                                <button
                                  onClick={() => toggleSubstory(timeWindowIndex, substoryIndex)}
                                  className="flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium text-sm transition-colors mb-4 group"
                                >
                                  {isExpanded ? (
                                    <>
                                      <ChevronUp className="h-4 w-4 transition-transform group-hover:scale-110" />
                                      Hide Details
                                    </>
                                  ) : (
                                    <>
                                      <ChevronRight className="h-4 w-4 transition-transform group-hover:scale-110" />
                                      Read More & Show Events
                                    </>
                                  )}
                                </button>

                                {/* Events Timeline */}
                                {isExpanded && (
                                  <div className="space-y-4 border-t border-gray-200 pt-4">
                                    <h5 className="font-semibold text-gray-900 mb-3">Timeline of Events:</h5>
                                    <div className="relative">
                                      {/* Timeline line */}
                                      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-500 to-purple-500"></div>
                                      
                                      {substory.events.map((event, eventIndex) => (
                                        <div key={eventIndex} className="relative pl-12 pb-4">
                                          {/* Timeline dot */}
                                          <div className="absolute left-2 top-2 w-4 h-4 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full border-2 border-white shadow-md"></div>
                                          
                                          {/* Event content */}
                                          <div className="bg-white rounded-lg p-4 border border-gray-200 hover:border-blue-300 transition-colors shadow-sm">
                                            <div className="flex items-start justify-between mb-2">
                                              <span className="text-sm font-semibold text-gray-900 bg-blue-50 px-3 py-1 rounded-full">
                                                {formatDate(event.date)}
                                              </span>
                                              {event.source_url && (
                                                <a
                                                  href={event.source_url}
                                                  target="_blank"
                                                  rel="noopener noreferrer"
                                                  className="text-blue-600 hover:text-blue-700 p-1 hover:bg-blue-50 rounded transition-colors group"
                                                  title="View source article"
                                                >
                                                  <ExternalLink className="h-4 w-4 group-hover:scale-110 transition-transform" />
                                                </a>
                                              )}
                                            </div>
                                            <p className="text-gray-700 text-sm leading-relaxed">
                                              {event.event}
                                            </p>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default App; 