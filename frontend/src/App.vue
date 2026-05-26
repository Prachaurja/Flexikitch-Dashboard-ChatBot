<template>
  <div class="chat-wrapper">

    <!-- Header -->
    <div class="header">
      <div class="header-left">
        <img src="/flexikitch-logo-round.svg" class="header-logo" alt="FlexiKitch" />
        <div>
          <div class="header-title">FLEXIKITCH DASHBOARD ASSISTANT</div>
          <div class="header-sub">AI-Powered Dashboard Intelligence</div>
        </div>
      </div>
      <div class="header-right">
        <div class="status-dot" :class="{ connected: isConnected }"></div>
        <span class="status-text">{{ isConnected ? 'Connected' : 'Offline' }}</span>
      </div>
    </div>

    <!-- Chat Messages -->
    <div class="chat-body" ref="chatBody">

      <!-- Welcome message -->
      <div class="message-row bot">
        <div class="avatar bot-av">FK</div>
        <div class="message-content">
          <div class="bubble bot-bubble">
            Hi! I'm your FlexiKitch Dashboard Assistant.<br><br>
            I have full access to your sales, pipeline, SEO and performance data.
            Ask me anything!
          </div>
          <!-- Suggestion pills -->
          <div class="suggestions">
            <button
              v-for="s in suggestions"
              :key="s"
              class="suggestion-btn"
              @click="askSuggestion(s)"
            >{{ s }}</button>
          </div>
        </div>
      </div>

      <!-- Dynamic messages -->
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="message-row"
        :class="msg.role === 'user' ? 'user' : 'bot'"
      >
        <div class="avatar" :class="msg.role === 'user' ? 'user-av' : 'bot-av'">
          {{ msg.role === 'user' ? '👤' : 'FK' }}
        </div>
        <div class="bubble" :class="msg.role === 'user' ? 'user-bubble' : 'bot-bubble'">
          <span v-html="formatMessage(msg.content)"></span>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="isTyping" class="message-row bot">
        <div class="avatar bot-av">FK</div>
        <div class="bubble bot-bubble typing-bubble">
          <span></span><span></span><span></span>
        </div>
      </div>

    </div>

    <!-- Input Area -->
    <div class="input-area">
      <div class="input-glow-wrapper" :class="{ active: inputFocused }">
        <input
          v-model="inputText"
          ref="inputRef"
          type="text"
          placeholder="Ask about your dashboard data..."
          @keypress.enter="sendMessage"
          @focus="inputFocused = true"
          @blur="inputFocused = false"
          :disabled="isTyping"
        />
      </div>
      <button
        class="send-btn"
        @click="sendMessage"
        :disabled="isTyping || !inputText.trim()"
      >
        <span v-if="!isTyping">➤</span>
        <span v-else class="loading-spinner"></span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FlexiKitchChatbot',

  data() {
    return {
      messages: [],
      inputText: '',
      isTyping: false,
      isConnected: false,
      inputFocused: false,
      sessionId: 'session_' + Date.now(),
      apiUrl: 'http://localhost:8000/chat',

      suggestions: [
        'Won revenue?',
        'Top lost reasons?',
        'SEO performance?',
        'Top sales owner?',
        'Active pipeline?',
        '2026 target status?',
        'Traffic by device?',
        'Top countries?'
      ]
    }
  },

  async mounted() {
    await this.checkConnection()
    this.$nextTick(() => {
      this.$refs.inputRef?.focus()
    })
  },

  methods: {

    // Check if API is running
    async checkConnection() {
      try {
        const res = await fetch('http://localhost:8000/health')
        this.isConnected = res.ok
      } catch {
        this.isConnected = false
      }
    },

    // Handle suggestion pill click
    askSuggestion(text) {
      // Strip emoji from suggestion
      this.inputText = text.replace(/^[^\w]+/, '').trim()
      this.sendMessage()
    },

    // Send message to API
    async sendMessage() {
      const question = this.inputText.trim()
      if (!question || this.isTyping) return

      // Add user message
      this.messages.push({
        role: 'user',
        content: question
      })

      this.inputText = ''
      this.isTyping = true
      this.scrollToBottom()

      try {
        const response = await fetch(this.apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: question,
            session_id: this.sessionId
          })
        })

        const data = await response.json()

        if (data.answer) {
          this.messages.push({
            role: 'assistant',
            content: data.answer
          })
        } else if (data.detail) {
          this.messages.push({
            role: 'assistant',
            content: `Error: ${data.detail}`
          })
        }

      } catch (error) {
        this.messages.push({
          role: 'assistant',
          content: 'Cannot connect to the API server. Make sure it is running on localhost:8000'
        })
        this.isConnected = false
      }

      this.isTyping = false
      this.$nextTick(() => {
        this.scrollToBottom()
        this.$refs.inputRef?.focus()
      })
    },

    // Format message — convert markdown bold/newlines to HTML
    formatMessage(text) {
      return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>')
        .replace(/#{1,3} (.*?)(<br>|$)/g, '<strong>$1</strong><br>')
    },

    // Scroll chat to bottom
    scrollToBottom() {
      this.$nextTick(() => {
        const body = this.$refs.chatBody
        if (body) body.scrollTop = body.scrollHeight
      })
    }
  }
}
</script>

<style>
/* Reset */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #f0f2f5;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

#app {
  width: 100%;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Main wrapper */
.chat-wrapper {
  width: 480px;
  height: 680px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.header {
  background: linear-gradient(135deg, #F26449, #F26449);
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-icon { font-size: 22px; }
.header-title {
  color: white;
  font-size: 14px;
  font-weight: 700;
}
.header-sub {
  color: rgba(255,255,255,0.75);
  font-size: 10px;
  margin-top: 1px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #F26449;
  transition: background 0.3s;
}
.status-dot.connected {
  background: #2ecc71;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.status-text {
  color: rgba(255,255,255,0.8);
  font-size: 10px;
}

/* Chat body */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #f8f9fa;
}
.chat-body::-webkit-scrollbar { width: 4px; }
.chat-body::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 4px;
}

/* Message rows */
.message-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.message-row.user { flex-direction: row-reverse; }

/* Message content wrapper (for bot — includes suggestions) */
.message-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 82%;
}

/* Avatars */
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.bot-av { background: #F26449; color: white; }
.user-av { background: #2C3E50; color: white; }

/* Bubbles */
.bubble {
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.55;
  word-wrap: break-word;
}
.bot-bubble {
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 2px 12px 12px 12px;
  color: #2c3e50;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  max-width: 100%;
}
.user-bubble {
  background: linear-gradient(135deg, #F26449, #F26449);
  color: white;
  border-radius: 12px 2px 12px 12px;
  max-width: 82%;
}

/* Suggestions */
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.suggestion-btn {
  background: white;
  border: 1px solid #F26449;
  color: #F26449;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.suggestion-btn:hover {
  background: #F26449;
  color: white;
  transform: translateY(-1px);
}

/* Typing indicator */
.typing-bubble {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 12px 16px;
}
.typing-bubble span {
  width: 6px;
  height: 6px;
  background: #F26449;
  border-radius: 50%;
  animation: bounce 1.2s infinite;
}
.typing-bubble span:nth-child(2) { animation-delay: 0.2s; }
.typing-bubble span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-5px); }
}

/* Input area */
.input-area {
  padding: 12px 16px;
  background: white;
  border-top: 1px solid #eee;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.input-glow-wrapper {
  flex: 1;
  position: relative;
  border-radius: 24px;
  padding: 1.5px;
  background: #e0e0e0;
}

.input-glow-wrapper.active {
  background: conic-gradient(
    from var(--angle, 0deg),
    transparent 0deg,
    transparent 300deg,
    #F26449 340deg,
    #FF9A85 360deg
  );
  animation: rotate-border 1.8s linear infinite;
}

@property --angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

@keyframes rotate-border {
  to { --angle: 360deg; }
}

.input-glow-wrapper input {
  width: 100%;
  padding: 10px 16px;
  border: none;
  border-radius: 22px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
  background: white;
  display: block;
}

.input-glow-wrapper input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}


.input-area input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.send-btn {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #F26449, #F26449);
  color: white;
  font-size: 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.2s, opacity 0.2s;
}
.send-btn:hover:not(:disabled) { transform: scale(1.08); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Loading spinner */
.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>