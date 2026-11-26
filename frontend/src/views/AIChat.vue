<template>
  <div class="page-container chat-page">
    <!-- 快速模板 -->
    <div v-if="messages.length === 0" class="templates-card">
      <h3>🚀 试试这些</h3>
      <div class="template-list">
        <a-card
          v-for="tpl in templates"
          :key="tpl.title"
          hoverable
          class="template-card"
          @click="useTemplate(tpl)"
        >
          <div class="template-icon">{{ tpl.icon }}</div>
          <div class="template-title">{{ tpl.title }}</div>
          <div class="template-desc">{{ tpl.desc }}</div>
        </a-card>
      </div>
    </div>

    <!-- 聊天区域 -->
    <div ref="chatContainer" class="chat-container">
      <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">
        <div class="msg-avatar">
          <a-avatar v-if="msg.role === 'user'" :size="36">{{ userInitial }}</a-avatar>
          <a-avatar v-else :size="36" :style="{ background: '#165dff' }">AI</a-avatar>
        </div>
        <div class="msg-content">
          <div class="msg-header">
            <b>{{ msg.role === 'user' ? user?.username || '你' : 'TravelAI' }}</b>
            <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
            <a-tag v-if="msg.role === 'assistant' && msg.mode === 'rule_based'" size="small" color="orangered">
              规则引擎模式
            </a-tag>
          </div>

          <!-- 思考过程 -->
          <a-collapse
            v-if="msg.role === 'assistant' && msg.thinkingSteps?.length"
            class="thinking-collapse"
            :bordered="false"
          >
            <a-collapse-item header="🧠 查看 AI 思考过程" key="think">
              <div class="thinking-steps">
                <div v-for="(s, i) in msg.thinkingSteps" :key="i" class="step">
                  <small style="color:#165dff">{{ s.node }}</small> — {{ s.message }}
                </div>
              </div>
            </a-collapse-item>
          </a-collapse>

          <div class="msg-body">
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="bubble user-bubble">{{ msg.content }}</div>

            <!-- AI 消息 -->
            <div v-else class="bubble ai-bubble">
              <!-- 天气卡片 -->
              <div v-if="msg.weatherInfo" class="weather-card">
                <div class="weather-header">🌤️ {{ msg.weatherInfo.city }} 天气预报</div>
                <div class="weather-days">
                  <div v-for="day in msg.weatherInfo.forecasts.slice(0, 5)" :key="day.date" class="weather-day">
                    <div class="day-name">{{ day.weekday || day.date?.slice(5) }}</div>
                    <div class="day-icon">{{ day.icon }}</div>
                    <div class="day-weather">{{ day.weather }}</div>
                    <div class="day-temp">{{ day.temp_low }}° ~ {{ day.temp_high }}°</div>
                  </div>
                </div>
                <div v-if="msg.weatherInfo.tips" class="weather-tips">💡 {{ msg.weatherInfo.tips }}</div>
              </div>

              <!-- 行程预览 -->
              <div v-if="msg.itinerary?.days?.length" class="itinerary-preview">
                <div class="itinerary-header">🗺️ 为你生成了 {{ msg.itinerary.days.length }} 天的旅行规划</div>
                <a-space style="margin-top: 10px">
                  <a-button type="primary" size="small" :loading="saving" @click="saveTrip(msg)">
                    <template #icon><icon-save /></template>
                    保存并查看完整行程
                  </a-button>
                </a-space>
              </div>

              <div class="markdown-content" v-html="renderMarkdown(msg.content)"></div>

              <!-- 联网来源 -->
              <div v-if="msg.webSources?.length" class="web-sources">
                <a-divider style="margin: 12px 0" />
                <div style="font-size: 12px; color: #86909c; margin-bottom: 4px">🌐 联网搜索来源：</div>
                <a-tag v-for="(s, i) in msg.webSources.slice(0, 5)" :key="i" size="small" color="arcoblue">
                  {{ s.title?.slice(0, 26) || s.url?.slice(0, 30) }}
                </a-tag>
              </div>
            </div>

            <!-- 建议操作 -->
            <div
              v-if="msg.role === 'assistant' && msg.actions?.length"
              class="suggested-actions"
            >
              <span style="font-size: 13px; color: #86909c">你可以：</span>
              <a-tag
                v-for="action in msg.actions"
                :key="action"
                color="cyan"
                style="cursor: pointer"
                @click="inputMessage = action"
              >
                {{ action }}
              </a-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="message assistant">
        <div class="msg-avatar">
          <a-avatar :size="36" :style="{ background: '#165dff' }">AI</a-avatar>
        </div>
        <div class="msg-content">
          <div class="msg-body">
            <div class="bubble ai-bubble">
              <a-spin size="small" /> TravelAI 正在联网搜索并思考中，请稍候…
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <a-textarea
        v-model="inputMessage"
        placeholder="描述你的旅行计划… 例如：我想去日本东京，4月初，5天2人，预算2万，喜欢文化"
        :auto-size="{ minRows: 2, maxRows: 5 }"
        @keydown.enter.exact.prevent="handleSend"
      />
      <div class="input-actions">
        <a-button :loading="clearing" @click="doClear">
          <template #icon><icon-delete /></template>
          清空记录
        </a-button>
        <a-button type="primary" :disabled="!inputMessage.trim()" :loading="loading" @click="handleSend">
          <template #icon><icon-send /></template>
          发送
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { agentApi, type ChatMessage, type AgentMessageResponse } from '../api/agent'
import { tripApi } from '../api/trips'
import { useAuthStore } from '../stores/auth'

interface UIMessage extends ChatMessage {
  weatherInfo?: AgentMessageResponse['weather_info']
  itinerary?: AgentMessageResponse['itinerary']
  actions?: string[]
  thinkingSteps?: AgentMessageResponse['thinking_steps']
  webSources?: AgentMessageResponse['web_sources']
  mode?: string
  destination?: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const inputMessage = ref('')
const messages = ref<UIMessage[]>([])
const loading = ref(false)
const clearing = ref(false)
const saving = ref(false)
const chatContainer = ref<HTMLElement>()

const templates = [
  { icon: '🌸', title: '日本赏樱', desc: '4月初去日本东京，5天2人，赏樱+文化之旅，预算2万' },
  { icon: '🏖️', title: '海岛度假', desc: '想去三亚，3天，亲子游，预算1万' },
  { icon: '🐼', title: '成都慢生活', desc: '成都3天，2人，美食+大熊猫，休闲游' },
  { icon: '🏛️', title: '西安历史之旅', desc: '西安4天，2人，历史古迹+美食，预算6000' },
]

const user = computed(() => auth.user)
const userInitial = computed(() => (auth.user?.username || '你')[0].toUpperCase())

const formatTime = (ts: string) => {
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const renderMarkdown = (content: string) => {
  if (!content) return ''
  const safe = content.replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return safe
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>')
}

const scrollToBottom = () => {
  nextTick(() => {
    chatContainer.value?.scrollTo({ top: chatContainer.value.scrollHeight, behavior: 'smooth' })
  })
}

const useTemplate = (tpl: { desc: string }) => {
  inputMessage.value = tpl.desc
  handleSend()
}

const handleSend = async () => {
  const content = inputMessage.value.trim()
  if (!content || loading.value) return

  messages.value.push({
    id: Date.now().toString(),
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  })
  inputMessage.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res = await agentApi.chat({ message: content })
    messages.value.push({
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: res.message || '',
      timestamp: new Date().toISOString(),
      weatherInfo: res.weather_info,
      itinerary: res.itinerary,
      actions: res.suggested_actions,
      thinkingSteps: res.thinking_steps,
      webSources: res.web_sources,
      mode: res.mode,
      destination: res.destination,
    })
  } catch (e: any) {
    messages.value.push({
      id: (Date.now() + 2).toString(),
      role: 'assistant',
      content: e?.detail || '发送失败，请稍后重试。',
      timestamp: new Date().toISOString(),
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

const saveTrip = async (msg: UIMessage) => {
  if (!msg.itinerary?.days?.length) return
  saving.value = true
  try {
    const days = msg.itinerary.days
    const startDate = days[0]?.date || new Date().toISOString().slice(0, 10)
    const last = days[days.length - 1]
    const endDate = last?.date || startDate
    const destination =
      msg.destination ||
      msg.content.match(/^# (.+) 行程规划/m)?.[1] ||
      'AI 行程'
    const trip = await tripApi.create({
      title: `${destination} · AI 定制行程`,
      destination: destination,
      start_date: startDate,
      end_date: endDate,
      days: days as any,
      markdown: msg.itinerary.content,
    })
    Message.success('行程已保存')
    router.push(`/trips/${trip.id}`)
  } catch (e: any) {
    Message.error(e?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const doClear = async () => {
  clearing.value = true
  try {
    await agentApi.clearHistory()
    messages.value = []
    Message.success('对话已清空')
  } catch {
    Message.error('清空失败')
  } finally {
    clearing.value = false
  }
}

onMounted(async () => {
  // 首页带过来的城市直达提问
  const q = route.query.q as string
  if (q) {
    inputMessage.value = q
    await handleSend()
    return
  }
  // 加载历史对话
  if (!auth.token) return
  try {
    const history = await agentApi.getHistory({ limit: 20 })
    messages.value = history.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp,
      weatherInfo: m.metadata?.itinerary ? undefined : undefined,
      itinerary: m.metadata?.itinerary
        ? { content: m.metadata.itinerary.content || '', days: m.metadata.itinerary.days || [], spots_used: [] }
        : undefined,
      actions: [],
      mode: m.metadata?.mode,
    }))
  } catch {
    /* 忽略历史加载失败 */
  }
  scrollToBottom()
})
</script>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: calc(100vh - 60px); padding-bottom: 0; }
.templates-card { margin-bottom: 14px; }
.chat-container { flex: 1; overflow-y: auto; padding: 6px 4px; }
.message { display: flex; gap: 10px; margin-bottom: 16px; }
.message.user { flex-direction: row-reverse; }
.msg-content { max-width: 76%; }
.message.user .msg-content { text-align: right; }
.msg-header { font-size: 13px; color: #86909c; margin-bottom: 4px; display: flex; gap: 8px; align-items: center; }
.message.user .msg-header { justify-content: flex-end; }
.msg-time { font-size: 12px; }
.bubble { padding: 12px 14px; border-radius: 12px; text-align: left; line-height: 1.65; }
.user-bubble { background: #165dff; color: #fff; display: inline-block; }
.ai-bubble { background: #fff; border: 1px solid #e5e6eb; }
.weather-card { background: #f0f7ff; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.weather-header { font-weight: 600; margin-bottom: 4px; }
.weather-tips { font-size: 13px; color: #4e5969; margin-top: 6px; }
.itinerary-preview { background: #f7fffa; border: 1px dashed #00b42a; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.itinerary-header { font-weight: 600; color: #00b42a; }
.web-sources .arco-tag { margin: 2px 4px 2px 0; }
.input-area {
  background: #fff; border: 1px solid #e5e6eb; border-radius: 12px;
  padding: 12px; margin: 10px 0 16px;
}
.input-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.thinking-collapse { background: #f7f8fa; border-radius: 8px; margin-bottom: 6px; text-align: left; }
</style>
