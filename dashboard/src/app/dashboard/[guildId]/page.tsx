'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState, useEffect } from 'react';

// Mock data - replace with API calls
const mockStats = {
  memberCount: 150,
  onlineCount: 45,
  messagesDay: 234,
  messagesWeek: 1567,
  topMembers: [
    { userId: '1', name: 'Alice', xp: 2500, level: 15, avatar: null },
    { userId: '2', name: 'Bob', xp: 2100, level: 13, avatar: null },
    { userId: '3', name: 'Charlie', xp: 1800, level: 11, avatar: null },
    { userId: '4', name: 'Diana', xp: 1500, level: 9, avatar: null },
    { userId: '5', name: 'Eve', xp: 1200, level: 8, avatar: null },
  ],
  activityData: [
    { day: 'Lun', messages: 200 },
    { day: 'Mar', messages: 300 },
    { day: 'Mer', messages: 250 },
    { day: 'Jeu', messages: 400 },
    { day: 'Ven', messages: 350 },
    { day: 'Sam', messages: 500 },
    { day: 'Dim', messages: 280 },
  ],
};

export default function GuildDashboard() {
  const params = useParams();
  const guildId = params.guildId as string;
  const [stats, setStats] = useState(mockStats);
  const [loading, setLoading] = useState(false);

  // In production, fetch from API
  useEffect(() => {
    // api.getGuildStats(guildId).then(setStats);
  }, [guildId]);

  return (
    <div className="min-h-screen bg-discord-darker">
      {/* Header */}
      <header className="bg-discord-dark border-b border-discord-gray/20">
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-discord-gray hover:text-white">
              ← Retour
            </Link>
            <div className="flex items-center gap-2">
              <span className="text-2xl">🤖</span>
              <span className="text-xl font-bold">ISROBOT</span>
            </div>
          </div>
          <nav className="flex items-center gap-6">
            <Link 
              href={`/dashboard/${guildId}`}
              className="text-white font-medium"
            >
              Vue d&apos;ensemble
            </Link>
            <Link 
              href={`/dashboard/${guildId}/config`}
              className="text-discord-gray hover:text-white transition-colors"
            >
              Configuration
            </Link>
            <Link 
              href={`/dashboard/${guildId}/analytics`}
              className="text-discord-gray hover:text-white transition-colors"
            >
              Analytics
            </Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-8 py-8">
        <h1 className="text-2xl font-bold mb-8">Vue d&apos;ensemble du serveur</h1>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-discord-dark rounded-xl p-6">
            <div className="text-discord-gray text-sm mb-1">Membres Total</div>
            <div className="text-3xl font-bold">{stats.memberCount}</div>
          </div>
          <div className="bg-discord-dark rounded-xl p-6">
            <div className="text-discord-gray text-sm mb-1">En Ligne</div>
            <div className="text-3xl font-bold text-discord-green">{stats.onlineCount}</div>
          </div>
          <div className="bg-discord-dark rounded-xl p-6">
            <div className="text-discord-gray text-sm mb-1">Messages (Jour)</div>
            <div className="text-3xl font-bold">{stats.messagesDay}</div>
          </div>
          <div className="bg-discord-dark rounded-xl p-6">
            <div className="text-discord-gray text-sm mb-1">Messages (Semaine)</div>
            <div className="text-3xl font-bold">{stats.messagesWeek}</div>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Activity Chart */}
          <div className="bg-discord-dark rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-6">Activité des Messages (7 jours)</h2>
            <div className="flex items-end justify-between h-48 gap-2">
              {stats.activityData.map((day) => {
                const maxMessages = Math.max(...stats.activityData.map(d => d.messages));
                const height = (day.messages / maxMessages) * 100;
                return (
                  <div key={day.day} className="flex-1 flex flex-col items-center gap-2">
                    <div 
                      className="w-full bg-discord-accent rounded-t transition-all duration-300 hover:bg-discord-accent-hover"
                      style={{ height: `${height}%`, minHeight: '4px' }}
                      title={`${day.messages} messages`}
                    />
                    <span className="text-xs text-discord-gray">{day.day}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Leaderboard */}
          <div className="bg-discord-dark rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-6">🏆 Top 10 Membres XP</h2>
            <div className="space-y-4">
              {stats.topMembers.map((member, index) => (
                <div key={member.userId} className="flex items-center gap-4">
                  <div className="w-8 text-center font-semibold text-discord-gray">
                    {index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`}
                  </div>
                  <div className="w-10 h-10 bg-discord-accent/20 rounded-full flex items-center justify-center">
                    {member.avatar ? (
                      <img src={member.avatar} alt="" className="w-full h-full rounded-full" />
                    ) : (
                      member.name.charAt(0)
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{member.name}</div>
                    <div className="text-sm text-discord-gray">Niveau {member.level}</div>
                  </div>
                  <div className="text-discord-accent font-semibold">
                    {member.xp.toLocaleString()} XP
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Heatmap placeholder */}
        <div className="mt-8 bg-discord-dark rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-6">Heures de Pointe</h2>
          <div className="grid grid-cols-24 gap-1">
            {Array.from({ length: 24 }, (_, hour) => {
              const intensity = Math.random();
              return (
                <div key={hour} className="text-center">
                  <div 
                    className="h-8 rounded"
                    style={{ 
                      backgroundColor: `rgba(88, 101, 242, ${0.1 + intensity * 0.9})` 
                    }}
                    title={`${hour}:00 - ${hour + 1}:00`}
                  />
                  <span className="text-xs text-discord-gray">{hour}h</span>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
