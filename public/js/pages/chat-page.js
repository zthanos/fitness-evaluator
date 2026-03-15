/**
 * ChatPage
 * Equivalent to chat.html + its inline <script>.
 */

class ChatPage {
    constructor() {
      this._chat = null;
    }
  
    async init(params, query) {
      window.renderPage(this._html());
      await this._tick();
  
      this._chat = new CoachChat();
      await this._chat.init();
    }
  
    destroy() {
      // CoachChat doesn't have a destroy method yet — extend if needed
    }
  
    _html() {
      return `
        <div class="flex flex-col h-screen overflow-hidden">
          <div class="flex-shrink-0 p-6 pb-4 border-b border-base-300">
            <div class="flex justify-between items-center">
              <div>
                <h1 class="text-4xl font-bold">💬 AI Coach</h1>
                <p class="text-base-content/70 mt-2">Your personal fitness and nutrition coach</p>
              </div>
              <button id="new-session-btn" class="btn btn-outline gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
                </svg>
                New Chat
              </button>
            </div>
          </div>
  
          <div class="flex-1 flex overflow-hidden">
            <div id="sessions-sidebar" class="hidden lg:flex flex-col w-64 border-r border-base-300 bg-base-100 overflow-hidden">
              <div class="p-4 border-b border-base-300"><h2 class="font-semibold">Chat History</h2></div>
              <div id="sessions-list" class="flex-1 overflow-y-auto p-2"></div>
            </div>
  
            <div class="flex-1 flex flex-col overflow-hidden">
              <div id="messages-container" class="flex-1 overflow-y-auto p-6 space-y-4">
                <div class="flex justify-center items-center h-full" id="welcome-message">
                  <div class="text-center max-w-2xl">
                    <div class="text-6xl mb-4">🏋️</div>
                    <h2 class="text-2xl font-bold mb-2">Welcome to Your AI Coach!</h2>
                    <p class="text-base-content/70 mb-6">I'm here to help you with fitness goals, nutrition advice, workout planning, and more.</p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
                      <button class="btn btn-outline justify-start" onclick="window._coachChat?.sendSuggestion('I want to set a new fitness goal')">🎯 Set a fitness goal</button>
                      <button class="btn btn-outline justify-start" onclick="window._coachChat?.sendSuggestion('How am I progressing with my training?')">📊 Check my progress</button>
                      <button class="btn btn-outline justify-start" onclick="window._coachChat?.sendSuggestion('Give me nutrition advice')">🥗 Get nutrition advice</button>
                      <button class="btn btn-outline justify-start" onclick="window._coachChat?.sendSuggestion('Suggest a workout plan')">💪 Plan a workout</button>
                    </div>
                  </div>
                </div>
              </div>
  
              <div class="flex-shrink-0 p-4 border-t border-base-300 bg-base-100">
                <form id="chat-form" class="flex gap-2">
                  <textarea id="message-input"
                    placeholder="Ask your coach anything... (Enter to send, Shift+Enter for new line)"
                    class="textarea textarea-bordered flex-1 resize-none" rows="1" maxlength="2000"></textarea>
                  <button type="submit" id="send-btn" class="btn btn-primary gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                      <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                    </svg>
                    Send
                  </button>
                </form>
                <div class="text-xs text-base-content/50 mt-2">Powered by AI • Responses may take a few seconds</div>
              </div>
            </div>
          </div>
        </div>`;
    }
  
    _tick() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
  }