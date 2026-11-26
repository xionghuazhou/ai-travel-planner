/**
 * Agent 对话 API
 */
import { request } from './index'

export interface AgentMessageRequest {
  message: string
  context?: Record<string, any>
}

export interface WeatherForecast {
  date: string
  weekday?: string
  weather: string
  icon: string
  temp_high: number
  temp_low: number
  wind?: string
}

export interface AgentMessageResponse {
  message: string
  intent?: string
  destination?: string
  suggested_actions: string[]
  itinerary?: {
    content: string
    days: Array<{
      day_number: number
      date?: string
      theme?: string
      summary?: string
      weather_info?: any
      spots: Array<{
        name: string
        start_time?: string
        end_time?: string
        duration_minutes?: number
        category?: string
        notes?: string
        estimated_cost?: number
      }>
    }>
    spots_used: string[]
    generated_by?: string
  }
  weather_info?: {
    city: string
    forecasts: WeatherForecast[]
    tips?: string
  }
  web_sources?: Array<{ title?: string; url?: string; source?: string }>
  thinking_steps?: Array<{ node: string; message: string }>
  mode?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

export const agentApi = {
  chat: (data: AgentMessageRequest) => {
    return request.post<never, AgentMessageResponse>('/api/v1/agent/chat', data)
  },

  getHistory: (params?: { limit?: number }) => {
    return request.get<never, { messages: ChatMessage[]; total: number; has_more: boolean }>(
      '/api/v1/agent/history',
      { params }
    )
  },

  clearHistory: () => {
    return request.delete<never, { message: string }>('/api/v1/agent/history')
  },
}
