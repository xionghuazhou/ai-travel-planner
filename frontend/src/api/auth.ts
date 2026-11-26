import { request } from './index'

export interface User {
  id: string
  username: string
  email: string
  avatar?: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: User
}

export const authApi = {
  register: (data: { username: string; email: string; password: string }) => {
    return request.post<never, LoginResult>('/api/v1/auth/register', data)
  },
  login: (data: { username: string; password: string }) => {
    return request.post<never, LoginResult>('/api/v1/auth/login', data)
  },
  me: () => {
    return request.get<never, User>('/api/v1/auth/me')
  },
}
