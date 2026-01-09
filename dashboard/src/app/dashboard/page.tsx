'use client';

import Link from 'next/link';
import { useState } from 'react';

// Mock data for demonstration - replace with actual Discord OAuth data
const mockGuilds = [
  { id: '123456789', name: 'Mon Serveur', icon: null, memberCount: 150 },
  { id: '987654321', name: 'Gaming Community', icon: null, memberCount: 500 },
  { id: '456789123', name: 'Dev Hub', icon: null, memberCount: 75 },
];

export default function DashboardPage() {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredGuilds = mockGuilds.filter((guild) =>
    guild.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-discord-darker">
      {/* Header */}
      <header className="bg-discord-dark border-b border-discord-gray/20">
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <span className="text-xl font-bold">ISROBOT</span>
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-discord-gray">Connecté en tant que</span>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-discord-accent rounded-full flex items-center justify-center">
                U
              </div>
              <span>Utilisateur</span>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-8 py-12">
        <h1 className="text-3xl font-bold mb-2">Sélectionnez un serveur</h1>
        <p className="text-discord-gray mb-8">
          Choisissez le serveur que vous souhaitez gérer
        </p>

        {/* Search */}
        <div className="mb-8">
          <input
            type="text"
            placeholder="Rechercher un serveur..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full max-w-md px-4 py-3 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none transition-colors"
          />
        </div>

        {/* Guild Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredGuilds.map((guild) => (
            <Link
              key={guild.id}
              href={`/dashboard/${guild.id}`}
              className="bg-discord-dark rounded-xl p-6 card-hover border border-discord-gray/20 hover:border-discord-accent/50 transition-colors"
            >
              <div className="flex items-center gap-4 mb-4">
                <div className="w-14 h-14 bg-discord-accent/20 rounded-full flex items-center justify-center text-2xl">
                  {guild.icon ? (
                    <img
                      src={guild.icon}
                      alt={guild.name}
                      className="w-full h-full rounded-full object-cover"
                    />
                  ) : (
                    guild.name.charAt(0).toUpperCase()
                  )}
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{guild.name}</h3>
                  <p className="text-discord-gray text-sm">
                    {guild.memberCount} membres
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-discord-accent">Gérer →</span>
                <span className="px-2 py-1 bg-discord-green/20 text-discord-green rounded">
                  Admin
                </span>
              </div>
            </Link>
          ))}
        </div>

        {filteredGuilds.length === 0 && (
          <div className="text-center py-12 text-discord-gray">
            <p className="text-xl mb-4">Aucun serveur trouvé</p>
            <p>
              Assurez-vous d&apos;être administrateur des serveurs que vous souhaitez gérer.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
