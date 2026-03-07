/**
 * CoachChat Component
 * 
 * AI-powered fitness coach chat interface with:
 * - Message history display
 * - Markdown rendering for responses
 * - Auto-scroll to latest message
 * - Enter/Shift+Enter handling
 * - Session management
 * 
 * Requirements: 13.1, 13.5, 13.6, 13.7
 */

class CoachChat {
    constructor() {
        this.currentSessionId = null;
        this.messages = [];
        this.sessions = [];
        this.isLoading = false;
        
        // DOM elements
        this.messagesContainer = document.getElementById('messages-container');
        this.messageInput = document.getElementById('message-input');
        this.chatForm = document.getElementById('chat-form');
        this.sendBtn = document.getElementById('send-btn');
        this.welcomeMessage = document.getElementById('welcome-message');
        this.sessionsListContainer = document.getElementById('sessions-list');
        this.newSessionBtn = document.getElementById('new-session-btn');
        
        // Configure marked.js for markdown rendering
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
        }
    }
    
    async init() {
        await this.loadSessions();
        this.setupEventListeners();
        this.renderSessions();
        
        // Load most recent session if exists
        if (this.sessions.length > 0) {
            await this.loadSession(this.sessions[0].id);
        }
    }
    
    setupEventListeners() {
        // Chat form submission
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Message input - handle Enter vs Shift+Enter
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });
        
        // New session button
        this.newSessionBtn.addEventListener('click', () => {
            this.createNewSession();
        });
    }
    
    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 200) + 'px';
    }
    
    async loadSessions() {
        try {
            // Load sessions from API
            const response = await fetch(`${api.baseUrl}/chat/sessions`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            this.sessions = await response.json();
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.sessions = [];
        }
    }
    
    async saveSessions() {
        // No longer needed - sessions are saved via API
        // Kept for compatibility
    }
    
    async loadSession(sessionId) {
        try {
            // Load session from API with message limit of 50
            const response = await fetch(`${api.baseUrl}/chat/sessions/${sessionId}/messages?limit=50`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const messages = await response.json();
            this.currentSessionId = sessionId;
            this.messages = messages || [];
            this.renderMessages();
            this.renderSessions(); // Update active session highlight
        } catch (error) {
            console.error('Error loading session:', error);
        }
    }
    
    async createNewSession() {
        try {
            // Create session via API
            const response = await fetch(`${api.baseUrl}/chat/sessions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: 'New Chat'
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const newSession = await response.json();
            
            // Reload sessions list
            await this.loadSessions();
            
            // Set as current session
            this.currentSessionId = newSession.id;
            this.messages = [];
            this.renderMessages();
            this.renderSessions();
            
            // Show welcome message
            if (this.welcomeMessage) {
                this.welcomeMessage.style.display = 'flex';
            }
        } catch (error) {
            console.error('Error creating session:', error);
        }
    }
    
    renderSessions() {
        if (!this.sessionsListContainer) return;
        
        if (this.sessions.length === 0) {
            this.sessionsListContainer.innerHTML = `
                <div class="text-center text-base-content/50 p-4">
                    No chat history yet
                </div>
            `;
            return;
        }
        
        const sessionsHTML = this.sessions.map(session => {
            const isActive = session.id === this.currentSessionId;
            const date = new Date(session.created_at);
            const dateStr = date.toLocaleDateString();
            
            // Get preview from title (which is set from first message)
            const preview = session.title && session.title !== 'New Chat'
                ? session.title.substring(0, 50) + (session.title.length > 50 ? '...' : '')
                : 'New chat';
            
            return `
                <button 
                    class="btn btn-ghost w-full justify-start text-left ${isActive ? 'btn-active' : ''}"
                    onclick="coachChat.loadSession('${session.id}')"
                >
                    <div class="flex-1 overflow-hidden">
                        <div class="font-semibold truncate">${session.title || 'New Chat'}</div>
                        <div class="text-xs text-base-content/50 truncate">${preview}</div>
                        <div class="text-xs text-base-content/40">${dateStr} • ${session.message_count || 0} messages</div>
                    </div>
                </button>
            `;
        }).join('');
        
        this.sessionsListContainer.innerHTML = sessionsHTML;
    }
    
    renderMessages() {
        // Hide welcome message if there are messages
        if (this.welcomeMessage) {
            this.welcomeMessage.style.display = this.messages.length === 0 ? 'flex' : 'none';
        }
        
        if (this.messages.length === 0) {
            return;
        }
        
        const messagesHTML = this.messages.map(msg => this.renderMessage(msg)).join('');
        
        // Find or create messages wrapper
        let messagesWrapper = this.messagesContainer.querySelector('#messages-wrapper');
        if (!messagesWrapper) {
            messagesWrapper = document.createElement('div');
            messagesWrapper.id = 'messages-wrapper';
            messagesWrapper.className = 'space-y-4';
            this.messagesContainer.appendChild(messagesWrapper);
        }
        
        messagesWrapper.innerHTML = messagesHTML;
        this.scrollToBottom();
    }
    
    renderMessage(message) {
        const isUser = message.role === 'user';
        const isSystem = message.role === 'system';
        
        if (isSystem) {
            return `
                <div class="flex justify-center">
                    <div class="alert alert-info max-w-2xl">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-current shrink-0 w-6 h-6">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <span>${this.escapeHtml(message.content)}</span>
                    </div>
                </div>
            `;
        }
        
        const alignment = isUser ? 'justify-end' : 'justify-start';
        const bgColor = isUser ? 'bg-primary text-primary-content' : 'bg-base-100 border border-base-300';
        const avatar = isUser ? '👤' : '🤖';
        const name = isUser ? 'You' : 'Coach';
        
        // Render markdown for assistant messages
        const content = isUser 
            ? this.escapeHtml(message.content)
            : this.renderMarkdown(message.content);
        
        return `
            <div class="flex ${alignment}">
                <div class="flex gap-3 max-w-3xl">
                    ${!isUser ? `<div class="avatar placeholder flex-shrink-0">
                        <div class="bg-base-300 text-base-content rounded-full w-10 h-10 flex items-center justify-center">
                            <span class="text-xl">${avatar}</span>
                        </div>
                    </div>` : ''}
                    <div class="flex flex-col ${isUser ? 'items-end' : 'items-start'}">
                        <div class="text-xs text-base-content/50 mb-1">${name}</div>
                        <div class="chat-bubble ${bgColor} p-4 rounded-lg shadow">
                            <div class="prose prose-sm max-w-none ${isUser ? 'text-primary-content' : 'text-base-content'}">
                                ${content}
                            </div>
                        </div>
                    </div>
                    ${isUser ? `<div class="avatar placeholder flex-shrink-0">
                        <div class="bg-primary text-primary-content rounded-full w-10 h-10 flex items-center justify-center">
                            <span class="text-xl">${avatar}</span>
                        </div>
                    </div>` : ''}
                </div>
            </div>
        `;
    }
    
    renderMarkdown(text) {
        if (typeof marked === 'undefined') {
            return this.escapeHtml(text);
        }
        
        try {
            return marked.parse(text);
        } catch (error) {
            console.error('Error rendering markdown:', error);
            return this.escapeHtml(text);
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    }
    
    async sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content || this.isLoading) return;
        
        // Create session if needed
        if (!this.currentSessionId) {
            await this.createNewSession();
        }
        
        // Add user message to UI immediately
        const userMessage = {
            role: 'user',
            content: content,
            created_at: new Date().toISOString()
        };
        
        this.messages.push(userMessage);
        this.renderMessages();
        
        // Clear input
        this.messageInput.value = '';
        this.autoResizeTextarea();
        
        // Send to API and get response
        await this.getAssistantResponse(content);
        
        // Reload sessions to update title and message count
        await this.loadSessions();
        this.renderSessions();
    }
    
    async sendSuggestion(suggestion) {
        this.messageInput.value = suggestion;
        await this.sendMessage();
    }
    
    async getAssistantResponse(userMessage) {
        this.isLoading = true;
        this.setLoadingState(true);
        
        try {
            // Use streaming endpoint
            await this.streamAssistantResponse(userMessage);
            
        } catch (error) {
            console.error('Error getting assistant response:', error);
            
            const errorMessage = {
                role: 'system',
                content: 'Sorry, I encountered an error. Please try again.',
                timestamp: new Date().toISOString()
            };
            
            this.messages.push(errorMessage);
            this.updateSessionMessages();
            this.renderMessages();
        } finally {
            this.isLoading = false;
            this.setLoadingState(false);
        }
    }
    
    async streamAssistantResponse(userMessage) {
        // Create a placeholder message for streaming
        const assistantMessage = {
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            isStreaming: true
        };
        
        this.messages.push(assistantMessage);
        this.renderMessages();
        
        try {
            // Call streaming endpoint
            const response = await fetch(`${api.baseUrl}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: userMessage,
                    session_id: parseInt(this.currentSessionId)
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                // Decode the chunk
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.substring(6));
                        
                        if (data.type === 'chunk') {
                            // Append chunk to message content
                            assistantMessage.content += data.content;
                            this.updateStreamingMessage(assistantMessage);
                        } else if (data.type === 'done') {
                            // Streaming complete
                            assistantMessage.isStreaming = false;
                            // Reload session to get the saved message
                            await this.loadSession(this.currentSessionId);
                        } else if (data.type === 'error') {
                            throw new Error(data.message);
                        }
                    }
                }
            }
            
        } catch (error) {
            console.error('Streaming error:', error);
            // Remove streaming message and show error
            this.messages.pop();
            throw error;
        }
    }
    
    updateStreamingMessage(message) {
        // Find the streaming message element and update it
        const messagesWrapper = this.messagesContainer.querySelector('#messages-wrapper');
        if (messagesWrapper) {
            const lastMessage = messagesWrapper.lastElementChild;
            if (lastMessage) {
                // Update the content
                const contentDiv = lastMessage.querySelector('.prose');
                if (contentDiv) {
                    contentDiv.innerHTML = this.renderMarkdown(message.content);
                }
            }
        }
        this.scrollToBottom();
    }
    
    setLoadingState(loading) {
        if (loading) {
            this.sendBtn.disabled = true;
            this.sendBtn.innerHTML = `
                <span class="loading loading-spinner loading-sm"></span>
                Thinking...
            `;
            this.messageInput.disabled = true;
        } else {
            this.sendBtn.disabled = false;
            this.sendBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                </svg>
                Send
            `;
            this.messageInput.disabled = false;
            this.messageInput.focus();
        }
    }
    
    updateSessionMessages() {
        // No longer needed - messages are saved via API
        // Kept for compatibility
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CoachChat;
}
