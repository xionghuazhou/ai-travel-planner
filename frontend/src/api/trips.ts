import { request } from './index'

export interface Trip {
  id: string
  title: string
  destination: string
  start_date: string
  end_date: string
  budget: number
  travelers: number
  status: string
  created_at: string
}

export interface TripSpot {
  id: string
  name: string
  start_time?: string
  end_time?: string
  duration_minutes?: number
  transport_to_next?: string
  estimated_cost?: number
  category?: string
  notes?: string
}

export interface TripDay {
  id: string
  day_number: number
  date: string
  theme?: string
  summary?: string
  weather_info?: { weather: string; icon?: string; temp_low?: number; temp_high?: number }
  spots: TripSpot[]
}

export interface TripDetail extends Trip {
  requirements: Record<string, any>
  days: TripDay[]
}

export interface TripSavePayload {
  title?: string
  destination: string
  start_date: string
  end_date: string
  budget?: number
  travelers?: number
  requirements?: Record<string, any>
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
  markdown?: string
}

export interface Spot {
  id: string
  name: string
  city: string
  category: string
  latitude: number | null
  longitude: number | null
  address?: string
  description?: string
  rating: number
  ticket_info?: Record<string, any>
  recommend_duration: number
  tags: string[]
}

export const tripApi = {
  create: (data: TripSavePayload) => {
    return request.post<never, Trip>('/api/v1/trips', data)
  },
  list: () => {
    return request.get<never, Trip[]>('/api/v1/trips')
  },
  detail: (id: string) => {
    return request.get<never, TripDetail>(`/api/v1/trips/${id}`)
  },
  remove: (id: string) => {
    return request.delete<never, { message: string }>(`/api/v1/trips/${id}`)
  },
}

export const spotApi = {
  list: (params?: { city?: string; q?: string; limit?: number }) => {
    return request.get<never, Spot[]>('/api/v1/spots', { params })
  },
  cities: () => {
    return request.get<never, string[]>('/api/v1/spots/cities')
  },
}
