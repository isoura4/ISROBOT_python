'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

export default function AnalyticsPage() {
  const params = useParams();
  const guildId = params.guildId as string;
  const [period, setPeriod] = useState('7d');

  // Mock data
  const stats = {
    retention: {
      joined: 45,
      stayed: 42,
      rate: 93.3,
    },
    channels: [
      { name: '#général', messages: 1250 },
      { name: '#gaming', messages: 890 },
      { name: '#aide', messages: 456 },
      { name: '#musique', messages: 234 },
      { name: '#annonces', messages: 120 },
    ],
    contributors: [
      { name: 'Alice', messages: 234, xp: 2500, level: 15 },
      { name: 'Bob', messages: 198, xp: 2100, level: 13 },
      { name: 'Charlie', messages: 156, xp: 1800, level: 11 },
      { name: 'Diana', messages: 134, xp: 1500, level: 9 },
      { name: 'Eve', messages: 112, xp: 1200, level: 8 },
    ],
    growthData: [
      { date: '01/01', members: 100, joins: 5, leaves: 2 },
      { date: '02/01', members: 103, joins: 8, leaves: 3 },
      { date: '03/01', members: 108, joins: 6, leaves: 1 },
      { date: '04/01', members: 113, joins: 10, leaves: 2 },
      { date: '05/01', members: 121, joins: 4, leaves: 3 },
      { date: '06/01', members: 122, joins: 12, leaves: 5 },
      { date: '07/01', members: 129, joins: 7, leaves: 0 },
    ],
  };

  const handleExportCSV = () => {
    // Generate CSV content
    const headers = ['Date', 'Membres', 'Entrées', 'Sorties'];
    const rows = stats.growthData.map(d => [d.date, d.members, d.joins, d.leaves]);
    const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n');
    
    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analytics-${guildId}-${period}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

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
              className="text-discord-gray hover:text-white transition-colors"
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
              className="text-white font-medium"
            >
              Analytics
            </Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Analytics Avancées</h1>
          <div className="flex items-center gap-4">
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="px-4 py-2 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
            >
              <option value="7d">7 derniers jours</option>
              <option value="30d">30 derniers jours</option>
              <option value="all">Tout le temps</option>
            </select>
            <button
              onClick={handleExportCSV}
              className="px-4 py-2 bg-discord-accent hover:bg-discord-accent-hover rounded-lg font-medium transition-colors"
            >
              📥 Export CSV
            </button>
          </div>
        </div>

        {/* Retention Card */}
        <div className="bg-discord-dark rounded-xl p-6 mb-8">
          <h2 className="text-lg font-semibold mb-6">📈 Rétention des Membres</h2>
          <div className="grid grid-cols-3 gap-8">
            <div className="text-center">
              <div className="text-3xl font-bold text-discord-green">{stats.retention.joined}</div>
              <div className="text-discord-gray mt-1">Nouveaux membres</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold">{stats.retention.stayed}</div>
              <div className="text-discord-gray mt-1">Restés</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-discord-accent">{stats.retention.rate}%</div>
              <div className="text-discord-gray mt-1">Taux de rétention</div>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          {/* Messages by Channel */}
          <div className="bg-discord-dark rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-6">💬 Messages par Canal</h2>
            <div className="space-y-4">
              {stats.channels.map((channel, index) => {
                const maxMessages = Math.max(...stats.channels.map(c => c.messages));
                const width = (channel.messages / maxMessages) * 100;
                return (
                  <div key={index}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">{channel.name}</span>
                      <span className="text-sm text-discord-gray">{channel.messages.toLocaleString()}</span>
                    </div>
                    <div className="h-2 bg-discord-darker rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-discord-accent rounded-full transition-all duration-500"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Top Contributors */}
          <div className="bg-discord-dark rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-6">🏆 Top Contributeurs</h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-discord-gray text-sm border-b border-discord-gray/20">
                    <th className="pb-3">#</th>
                    <th className="pb-3">Membre</th>
                    <th className="pb-3 text-right">Messages</th>
                    <th className="pb-3 text-right">XP</th>
                    <th className="pb-3 text-right">Niveau</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.contributors.map((user, index) => (
                    <tr key={index} className="border-b border-discord-gray/10 last:border-0">
                      <td className="py-3">
                        {index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : index + 1}
                      </td>
                      <td className="py-3 font-medium">{user.name}</td>
                      <td className="py-3 text-right">{user.messages}</td>
                      <td className="py-3 text-right text-discord-accent">{user.xp.toLocaleString()}</td>
                      <td className="py-3 text-right">{user.level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Growth Chart */}
        <div className="mt-8 bg-discord-dark rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-6">📊 Croissance des Membres</h2>
          <div className="h-64 flex items-end gap-2">
            {stats.growthData.map((day, index) => {
              const maxMembers = Math.max(...stats.growthData.map(d => d.members));
              const height = (day.members / maxMembers) * 100;
              return (
                <div key={index} className="flex-1 flex flex-col items-center">
                  <div 
                    className="w-full bg-gradient-to-t from-discord-accent to-discord-accent-hover rounded-t transition-all duration-300 hover:opacity-80 cursor-pointer group relative"
                    style={{ height: `${height}%`, minHeight: '20px' }}
                  >
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-discord-darker px-2 py-1 rounded text-xs whitespace-nowrap">
                      {day.members} membres<br/>
                      +{day.joins} / -{day.leaves}
                    </div>
                  </div>
                  <span className="text-xs text-discord-gray mt-2">{day.date}</span>
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-center gap-6 mt-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-discord-green rounded-full"></div>
              <span className="text-discord-gray">Entrées</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-discord-red rounded-full"></div>
              <span className="text-discord-gray">Sorties</span>
            </div>
          </div>
        </div>

        {/* Hourly Activity Heatmap */}
        <div className="mt-8 bg-discord-dark rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-6">🕐 Activité par Heure (Semaine)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="pb-2"></th>
                  {Array.from({ length: 24 }, (_, i) => (
                    <th key={i} className="pb-2 text-discord-gray font-normal">{i}h</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((day) => (
                  <tr key={day}>
                    <td className="pr-2 text-discord-gray">{day}</td>
                    {Array.from({ length: 24 }, (_, hour) => {
                      // Mock intensity based on typical Discord usage patterns
                      let intensity = Math.random();
                      // Higher activity in evening hours
                      if (hour >= 18 && hour <= 23) intensity *= 1.5;
                      if (hour >= 12 && hour <= 14) intensity *= 1.2;
                      // Lower activity at night
                      if (hour >= 1 && hour <= 7) intensity *= 0.3;
                      intensity = Math.min(intensity, 1);
                      
                      return (
                        <td key={hour} className="p-0.5">
                          <div 
                            className="w-full h-4 rounded-sm"
                            style={{ 
                              backgroundColor: `rgba(88, 101, 242, ${0.1 + intensity * 0.9})` 
                            }}
                            title={`${day} ${hour}:00 - ${hour + 1}:00`}
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-end gap-2 mt-4 text-xs text-discord-gray">
            <span>Moins</span>
            <div className="flex gap-0.5">
              {[0.1, 0.3, 0.5, 0.7, 0.9].map((opacity) => (
                <div 
                  key={opacity}
                  className="w-4 h-4 rounded-sm"
                  style={{ backgroundColor: `rgba(88, 101, 242, ${opacity})` }}
                />
              ))}
            </div>
            <span>Plus</span>
          </div>
        </div>
      </main>
    </div>
  );
}
