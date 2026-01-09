/**
 * API client for ISROBOT Dashboard
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';
const API_KEY = process.env.API_SECRET || '';

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options;
  
  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams(params);
    url += `?${searchParams.toString()}`;
  }

  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

// Types
export interface GuildStats {
  guild_id: string;
  period: string;
  totals: {
    total_users: number;
    total_xp: number;
    total_messages: number;
  };
  growth: Array<{
    date: string;
    member_count: number;
    joins_today: number;
    leaves_today: number;
  }>;
  top_members: Array<{
    userId: string;
    xp: number;
    level: number;
    messages: number;
  }>;
  top_channels: Array<{
    channel_id: string;
    total_messages: number;
  }>;
  hourly_activity: number[];
}

export interface GuildConfig {
  guild_id: string;
  engagement: {
    xp_per_message?: number;
    welcome_bonus_xp?: number;
    welcome_detection_enabled?: number;
    announcements_channel_id?: string;
    ambassador_role_id?: string;
    new_member_role_id?: string;
    new_member_role_duration_days?: number;
    welcome_dm_enabled?: number;
    welcome_dm_text?: string;
    welcome_public_text?: string;
  };
  moderation: {
    ai_enabled?: number;
    ai_confidence_threshold?: number;
    ai_model?: string;
    mute_duration_warn_2?: number;
    mute_duration_warn_3?: number;
  };
  xp_thresholds: Array<{
    threshold_points: number;
    role_id: string;
    role_name: string;
  }>;
}

export interface Challenge {
  id: number;
  name: string;
  description: string;
  reward_xp: number;
  reward_role_id?: string;
  is_active: number;
  created_at: string;
}

export interface Leaderboard {
  guild_id: string;
  leaderboard: Array<{
    userId: string;
    xp: number;
    level: number;
    messages: number;
  }>;
}

// API functions
export const api = {
  // Stats
  getGuildStats: (guildId: string, period = '7d') =>
    fetchApi<GuildStats>(`/api/guilds/${guildId}/stats`, { params: { period } }),

  getLeaderboard: (guildId: string, limit = 10) =>
    fetchApi<Leaderboard>(`/api/guilds/${guildId}/leaderboard`, { 
      params: { limit: limit.toString() } 
    }),

  // Config
  getGuildConfig: (guildId: string) =>
    fetchApi<GuildConfig>(`/api/guilds/${guildId}/config`),

  updateGuildConfig: (guildId: string, config: Partial<GuildConfig>) =>
    fetchApi<{ success: boolean; message: string }>(`/api/guilds/${guildId}/config`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  // Challenges
  getChallenges: (guildId: string) =>
    fetchApi<{ guild_id: string; challenges: Challenge[] }>(`/api/guilds/${guildId}/challenges`),

  createChallenge: (guildId: string, challenge: Omit<Challenge, 'id' | 'is_active' | 'created_at'>) =>
    fetchApi<{ success: boolean; challenge_id: number }>(`/api/guilds/${guildId}/challenges`, {
      method: 'POST',
      body: JSON.stringify(challenge),
    }),

  updateChallenge: (guildId: string, challengeId: number, data: Partial<Challenge>) =>
    fetchApi<{ success: boolean }>(`/api/guilds/${guildId}/challenges/${challengeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteChallenge: (guildId: string, challengeId: number) =>
    fetchApi<{ success: boolean }>(`/api/guilds/${guildId}/challenges/${challengeId}`, {
      method: 'DELETE',
    }),

  // Health
  healthCheck: () =>
    fetchApi<{ status: string; timestamp: string }>('/api/health'),
};

export default api;
