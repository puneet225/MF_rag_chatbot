"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Plus, MessageSquare, Send, Bot, User, BarChart2, Sun, Moon, AlertTriangle } from 'lucide-react';
import { useTheme } from 'next-themes';

const formatMessage = (text: string) => {
  // Regex matches `[text](url)` or standalone `http(s)://...`
  const urlRegex = /(\[.*?\]\(https?:\/\/[^\s\)]+\)|https?:\/\/[^\s\)]+)/g;
  
  return text.split(urlRegex).map((part, index) => {
    // 1. Is it a Markdown link? [Title](URL)
    const markdownMatch = part.match(/^\[(.*?)\]\((https?:\/\/[^\s\)]+)\)$/);
    if (markdownMatch) {
      return (
        <a key={index} href={markdownMatch[2]} target="_blank" rel="noopener noreferrer" className="text-groww hover:underline font-medium">
          {markdownMatch[1]}
        </a>
      );
    }
    
    // 2. Is it a raw URL?
    const urlMatch = part.match(/^(https?:\/\/[^\s\)]+)$/);
    if (urlMatch) {
      return (
        <a key={index} href={urlMatch[1]} target="_blank" rel="noopener noreferrer" className="text-groww hover:underline">
          {urlMatch[1]}
        </a>
      );
    }
    
    // 3. Otherwise, check for bold text parsing (**bold**)
    const boldRegex = /(\*\*.*?\*\*)/g;
    return <span key={index}>{
      part.split(boldRegex).map((subPart, subIndex) => {
        const boldMatch = subPart.match(/^\*\*(.*?)\*\*$/);
        if (boldMatch) {
          return <strong key={subIndex} className="font-semibold text-gray-900 dark:text-white">{boldMatch[1]}</strong>;
        }
        return subPart;
      })
    }</span>;
  });
};

const GrowwFactorLogo = () => (
  <svg viewBox="0 0 100 100" className="w-8 h-8 rounded-full shadow-md drop-shadow-sm flex-shrink-0" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <clipPath id="circleClip">
        <circle cx="50" cy="50" r="50" />
      </clipPath>
    </defs>
    <g clipPath="url(#circleClip)">
      <rect width="100" height="100" fill="#00E6B8"/>
      {/* Blue top layer with soft-rounded peaks */}
      <path d="M 0,72 Q 25,48 40,52 T 65,62 Q 85,45 100,35 L 100,0 L 0,0 Z" fill="#5A6DF2"/>
    </g>
  </svg>
);

const StarsBackground = () => {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {/* Dynamic Twinkling Stars generated via standard CSS gradient grid */}
      <div 
        className="absolute inset-0 opacity-40 dark:opacity-80"
        style={{
          backgroundImage: `
            radial-gradient(1px 1px at 15% 30%, #00D09C 100%, transparent),
            radial-gradient(1.5px 1.5px at 85% 15%, #00D09C 100%, transparent),
            radial-gradient(2px 2px at 45% 75%, #5A6DF2 100%, transparent),
            radial-gradient(1px 1px at 75% 80%, #00D09C 100%, transparent),
            radial-gradient(1px 1px at 25% 90%, #5A6DF2 100%, transparent),
            radial-gradient(1.5px 1.5px at 90% 40%, rgba(0, 208, 156, 0.7) 100%, transparent),
            radial-gradient(2px 2px at 5% 50%, rgba(90, 109, 242, 0.5) 100%, transparent),
            radial-gradient(1px 1px at 50% 10%, #00D09C 100%, transparent),
            radial-gradient(1.5px 1.5px at 60% 50%, #5A6DF2 100%, transparent)
          `,
          backgroundSize: '200px 200px',
          animation: 'twinkle 4s infinite alternate ease-in-out'
        }}
      />
      {/* Shooting Stars */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes twinkle { 0% { opacity: 0.3; } 100% { opacity: 1; transform: scale(1.02); } }
        @keyframes shooting-star { 
          0% { transform: translate(-10vw, 50vh) rotate(-45deg); opacity: 1; } 
          100% { transform: translate(110vw, -50vh) rotate(-45deg); opacity: 0; } 
        }
        .shooting-star-layer {
          position: absolute;
          width: 150px;
          height: 2px;
          background: linear-gradient(90deg, #00D09C, transparent);
          filter: drop-shadow(0 0 6px #00D09C);
          animation: shooting-star 6s infinite linear;
        }
      `}} />
      <div className="shooting-star-layer" style={{ animationDelay: '0s', top: '20%', left: '-10%' }}></div>
      <div className="shooting-star-layer" style={{ animationDelay: '3s', top: '70%', left: '-20%', background: 'linear-gradient(90deg, #5A6DF2, transparent)'}}></div>
    </div>
  );
};

export default function FundFactChat() {
  const [sessions, setSessions] = useState<{ [key: string]: { messages: any[], title: string } }>({});
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  
  const { theme, setTheme } = useTheme();

  // Handle hydration mismatch for theme toggle
  useEffect(() => {
    setMounted(true);
  }, []);

  // Initialize first session
  useEffect(() => {
    if (Object.keys(sessions).length === 0) {
      createNewChat();
    }
  }, []);

  const createNewChat = () => {
    const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(7);
    const chatNum = Object.keys(sessions).length + 1;
    setSessions(prev => ({
      ...prev,
      [newId]: { messages: [], title: `Chat ${chatNum}` }
    }));
    setActiveSessionId(newId);
  };

  const activeSession = sessions[activeSessionId];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeSession?.messages, isLoading]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || !activeSessionId) return;

    // Clean up URL: Remove trailing slash if present to avoid //chat issues
    let API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
    if (API_BASE_URL.endsWith('/')) {
      API_BASE_URL = API_BASE_URL.slice(0, -1);
    }

    const userMessage = { role: 'user', content: text };
    
    setSessions(prev => ({
      ...prev,
      [activeSessionId]: {
        ...prev[activeSessionId],
        messages: [...prev[activeSessionId].messages, userMessage]
      }
    }));
    
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          thread_id: activeSessionId
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const botMessage = { 
          role: 'assistant', 
          content: data.response,
          intent: data.intent 
        };
        
        setSessions(prev => ({
          ...prev,
          [activeSessionId]: {
            ...prev[activeSessionId],
            messages: [...prev[activeSessionId].messages, botMessage]
          }
        }));
      } else {
        throw new Error('API Error');
      }
    } catch (error) {
      const errorMessage = { 
        role: 'assistant', 
        content: `Connection Error: Could not reach the backend at ${API_BASE_URL}. Ensure your Vercel NEXT_PUBLIC_API_URL environment variable is correct and matches your Render URL.`,
        isError: true
      };
      setSessions(prev => ({
        ...prev,
        [activeSessionId]: {
          ...prev[activeSessionId],
          messages: [...prev[activeSessionId].messages, errorMessage]
        }
      }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputMessage);
    }
  };

  const quickActions = [
    "What is the latest NAV for HDFC Mid Cap?",
    "What is the expense ratio for HDFC Mid Cap?",
    "What are the exit load details for HDFC Flexi Cap?",
    "Who is the fund manager for HDFC Flexi Cap?"
  ];

  if (!activeSession) return <div className="h-screen flex items-center justify-center bg-white dark:bg-gray-950">Loading...</div>;

  return (
    <div className="flex h-screen bg-white dark:bg-[#05070a] text-gray-900 dark:text-gray-100 transition-colors duration-200 relative overflow-hidden">
      <StarsBackground />
      
      {/* Sidebar */}
      <div className="w-80 bg-gray-50/60 dark:bg-[#0a0c10]/60 border-r border-gray-200/50 dark:border-gray-800/50 flex flex-col transition-colors duration-200 backdrop-blur-xl z-10">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <GrowwFactorLogo />
            <h1 className="text-xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-400 bg-clip-text text-transparent tracking-tight">groww-factor</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 font-medium">
            Factual intelligence for HDFC Mutual Fund analysis.
          </p>
          <button 
            onClick={createNewChat}
            className="w-full bg-groww hover:bg-groww-hover text-white rounded-lg py-3 px-4 flex items-center justify-center gap-2 font-semibold shadow-md shadow-groww/20 transition-all hover:-translate-y-0.5"
          >
            <Plus size={20} />
            New Chat
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto px-4">
          <h2 className="text-xs font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3 px-2">History</h2>
          <div className="space-y-1">
            {Object.entries(sessions).map(([id, session]) => (
              <button
                key={id}
                onClick={() => setActiveSessionId(id)}
                className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-colors ${
                  activeSessionId === id 
                    ? 'bg-green-50 dark:bg-groww/10 text-groww font-medium' 
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                <MessageSquare size={18} className={activeSessionId === id ? "text-groww" : "text-gray-400 dark:text-gray-500"} />
                <span className="truncate">{session.title}</span>
              </button>
            ))}
          </div>
        </div>
        
        {/* Dark Mode Toggle */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-800">
          {mounted && (
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="flex items-center gap-3 w-full px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-transparent relative z-10">
        {/* Header */}
        <header className="h-16 border-b border-gray-100/50 dark:border-gray-800/30 flex items-center justify-between px-8 bg-white/40 dark:bg-[#05070a]/40 backdrop-blur-xl sticky top-0 z-20 transition-colors duration-200">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">{activeSession.title}</h2>
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 bg-gray-100 dark:bg-gray-900 text-gray-500 dark:text-gray-400 rounded-full border border-gray-200 dark:border-gray-800">
             <span className="w-2 h-2 rounded-full bg-groww animate-pulse"></span>
             Facts Verified
          </div>
        </header>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-3xl mx-auto space-y-6">
            
            {/* Empty State / Suggested Prompts */}
            {activeSession.messages.length === 0 && (
              <div className="pt-12 pb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="text-center mb-10">
                  <div className="mx-auto mb-8 transform hover:scale-110 transition-transform duration-300">
                    <GrowwFactorLogo />
                  </div>
                  <h3 className="text-4xl font-extrabold text-gray-900 dark:text-white mb-4 tracking-tight">How can I help you today?</h3>
                  <p className="text-gray-500 dark:text-gray-400 text-lg max-w-xl mx-auto font-medium">I provide strict, compliance-verified data sourced directly from official fund documents.</p>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {quickActions.map((action, idx) => (
                    <button
                      key={idx}
                      onClick={() => sendMessage(action)}
                      className="text-left p-5 border border-gray-200 dark:border-gray-800 rounded-xl hover:border-groww dark:hover:border-groww hover:bg-green-50/50 dark:hover:bg-groww/5 hover:shadow-sm dark:bg-gray-900/50 transition-all group flex items-start gap-4"
                    >
                      <div className="mt-0.5 opacity-60 group-hover:text-groww group-hover:opacity-100 transition-colors">
                        <MessageSquare size={18} />
                      </div>
                      <span className="text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white leading-relaxed font-medium">{action}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Message History */}
            {activeSession.messages.map((msg, idx) => (
              <div key={idx} className={`flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-gray-800 text-white dark:bg-gray-100 dark:text-gray-900' 
                    : 'bg-groww text-white'
                }`}>
                  {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                
                <div className={`max-w-[85%] rounded-2xl px-5 py-4 text-[15px] leading-relaxed shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-gray-100 dark:bg-gray-800 border border-transparent text-gray-800 dark:text-gray-100' 
                    : msg.isError 
                      ? 'bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 border border-red-100 dark:border-red-900/50'
                      : 'bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 text-gray-800 dark:text-gray-200'
                }`}>
                  <div className="whitespace-pre-wrap">{formatMessage(msg.content)}</div>
                  
                  {/* Premium Advisory Badge */}
                  {msg.intent === 'advisory' && (
                    <div className="mt-4 inline-flex items-center gap-2 text-xs font-medium bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-500 border border-amber-200/60 dark:border-amber-500/20 px-3 py-1.5 rounded-full">
                      <AlertTriangle size={14} />
                      Advisory Request Blocked
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="flex gap-4 animate-in fade-in">
                <div className="w-8 h-8 rounded-full bg-groww text-white shadow-sm flex items-center justify-center shrink-0">
                  <Bot size={16} />
                </div>
                <div className="bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm rounded-2xl px-5 py-4 flex items-center gap-2">
                  <div className="w-2 h-2 bg-groww/60 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-groww/60 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-groww/60 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} className="h-4" />
          </div>
        </div>

        {/* Input Area */}
        <div className="p-6 bg-white dark:bg-gray-950 border-t border-gray-100 dark:border-gray-800/80 transition-colors duration-200">
          <div className="max-w-3xl mx-auto relative group">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Ask a factual question about HDFC schemes..."
              className="w-full bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl pl-5 pr-14 py-4 text-[15px] text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-groww/30 focus:border-groww dark:focus:border-groww/80 shadow-sm transition-all resize-none"
              rows={1}
              style={{ minHeight: '60px', maxHeight: '120px' }}
            />
            <button
              onClick={() => sendMessage(inputMessage)}
              disabled={!inputMessage.trim() || isLoading}
              className="absolute right-3 top-3 bottom-0 w-10 h-10 bg-groww hover:bg-groww-hover disabled:bg-gray-200 dark:disabled:bg-gray-800 disabled:text-gray-400 dark:disabled:text-gray-600 text-white rounded-lg flex items-center justify-center transition-all disabled:shadow-none shadow-md shadow-groww/20"
            >
              <Send size={18} className="ml-1" />
            </button>
          </div>
          <div className="text-center mt-4">
            <span className="text-xs font-medium text-gray-400 dark:text-gray-500">
              Disclaimer: groww-factor provides data sourced from AMC portals. It is not an investment advisory platform.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
