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
import './App.css'

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

    async checkConnection() {
      try {
        const res = await fetch('http://localhost:8000/health')
        this.isConnected = res.ok
      } catch {
        this.isConnected = false
      }
    },

    askSuggestion(text) {
      this.inputText = text.replace(/^[^\w]+/, '').trim()
      this.sendMessage()
    },

    async sendMessage() {
      const question = this.inputText.trim()
      if (!question || this.isTyping) return

      this.messages.push({ role: 'user', content: question })
      this.inputText = ''
      this.isTyping = true
      this.scrollToBottom()

      try {
        const response = await fetch(this.apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: question, session_id: this.sessionId })
        })

        const data = await response.json()

        if (data.answer) {
          this.messages.push({ role: 'assistant', content: data.answer })
        } else if (data.detail) {
          this.messages.push({ role: 'assistant', content: `Error: ${data.detail}` })
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

    formatMessage(text) {
      return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>')
        .replace(/#{1,3} (.*?)(<br>|$)/g, '<strong>$1</strong><br>')
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const body = this.$refs.chatBody
        if (body) body.scrollTop = body.scrollHeight
      })
    }
  }
}
</script>