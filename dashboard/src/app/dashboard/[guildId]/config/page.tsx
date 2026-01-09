'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

type TabId = 'moderation' | 'engagement' | 'notifications';

export default function ConfigPage() {
  const params = useParams();
  const guildId = params.guildId as string;
  const [activeTab, setActiveTab] = useState<TabId>('engagement');
  const [saving, setSaving] = useState(false);

  // Form state
  const [config, setConfig] = useState({
    // Moderation & AI
    aiEnabled: true,
    aiConfidenceThreshold: 60,
    muteDurationWarn2: 3600,
    muteDurationWarn3: 86400,
    aiModel: 'llama2',
    
    // Engagement
    xpPerMessage: 1,
    welcomeBonusXp: 10,
    welcomeDetectionEnabled: true,
    welcomeDmEnabled: true,
    welcomeDmText: `Bienvenue sur le serveur ! 🎉

**Guide de démarrage:**
1. 📋 Consultez les règles du serveur
2. 🎭 Choisissez vos rôles
3. 👋 Présentez-vous dans le salon approprié
4. 🔍 Explorez les différents salons

N'hésitez pas à poser des questions !`,
    welcomePublicText: 'Bienvenue {user} sur le serveur ! 🎉',
    ambassadorPingEnabled: true,
    newMemberRoleDays: 7,
    
    // XP Thresholds
    xpThresholds: [
      { points: 50, roleId: '', roleName: 'Membre Actif' },
      { points: 100, roleId: '', roleName: 'Contributeur' },
      { points: 250, roleId: '', roleName: 'Vétéran' },
      { points: 500, roleId: '', roleName: 'Champion' },
      { points: 1000, roleId: '', roleName: 'Légende' },
    ],
    
    // Notifications
    eventRemindersEnabled: true,
  });

  // Challenges state
  const [challenges, setChallenges] = useState([
    { id: 1, name: '📸 Meme Week', description: 'Créez et partagez vos meilleurs mèmes', rewardXp: 100, active: true },
    { id: 2, name: '💻 Setup Showcase', description: 'Montrez votre setup gaming/travail', rewardXp: 150, active: true },
    { id: 3, name: '🎨 Art Challenge', description: 'Créez une œuvre artistique', rewardXp: 200, active: true },
  ]);

  const handleSave = async () => {
    setSaving(true);
    // In production: await api.updateGuildConfig(guildId, config);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setSaving(false);
    alert('Configuration sauvegardée !');
  };

  const tabs = [
    { id: 'moderation' as const, name: 'Modération & AI', icon: '🛡️' },
    { id: 'engagement' as const, name: 'Engagement', icon: '⭐' },
    { id: 'notifications' as const, name: 'Notifications', icon: '🔔' },
  ];

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
              className="text-white font-medium"
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
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Configuration</h1>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-discord-accent hover:bg-discord-accent-hover rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {saving ? 'Sauvegarde...' : 'Sauvegarder'}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 rounded-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-discord-accent text-white'
                  : 'bg-discord-dark text-discord-gray hover:text-white'
              }`}
            >
              {tab.icon} {tab.name}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-discord-dark rounded-xl p-8">
          {activeTab === 'moderation' && (
            <div className="space-y-8">
              <h2 className="text-xl font-semibold mb-6">Modération & AI</h2>
              
              {/* AI Toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium">Modération AI</h3>
                  <p className="text-sm text-discord-gray">
                    Activer l&apos;analyse automatique des messages
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.aiEnabled}
                    onChange={(e) => setConfig({ ...config, aiEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                </label>
              </div>

              {/* Confidence Slider */}
              <div>
                <label className="block font-medium mb-2">
                  Seuil de confiance AI: {config.aiConfidenceThreshold}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={config.aiConfidenceThreshold}
                  onChange={(e) => setConfig({ ...config, aiConfidenceThreshold: parseInt(e.target.value) })}
                  className="w-full max-w-md h-2 bg-discord-gray/30 rounded-lg appearance-none cursor-pointer accent-discord-accent"
                />
              </div>

              {/* Mute Durations */}
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block font-medium mb-2">Durée mute (2ème avertissement)</label>
                  <select
                    value={config.muteDurationWarn2}
                    onChange={(e) => setConfig({ ...config, muteDurationWarn2: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  >
                    <option value={1800}>30 minutes</option>
                    <option value={3600}>1 heure</option>
                    <option value={7200}>2 heures</option>
                    <option value={14400}>4 heures</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium mb-2">Durée mute (3ème avertissement)</label>
                  <select
                    value={config.muteDurationWarn3}
                    onChange={(e) => setConfig({ ...config, muteDurationWarn3: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  >
                    <option value={43200}>12 heures</option>
                    <option value={86400}>24 heures</option>
                    <option value={172800}>48 heures</option>
                    <option value={604800}>1 semaine</option>
                  </select>
                </div>
              </div>

              {/* AI Model */}
              <div>
                <label className="block font-medium mb-2">Modèle AI (Ollama)</label>
                <select
                  value={config.aiModel}
                  onChange={(e) => setConfig({ ...config, aiModel: e.target.value })}
                  className="w-full max-w-md px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                >
                  <option value="llama2">Llama 2</option>
                  <option value="llama3">Llama 3</option>
                  <option value="mistral">Mistral</option>
                  <option value="mixtral">Mixtral</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === 'engagement' && (
            <div className="space-y-8">
              <h2 className="text-xl font-semibold mb-6">Système d&apos;Engagement</h2>
              
              {/* XP Settings */}
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block font-medium mb-2">XP par message</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={config.xpPerMessage}
                    onChange={(e) => setConfig({ ...config, xpPerMessage: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-2">Bonus XP (accueil)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={config.welcomeBonusXp}
                    onChange={(e) => setConfig({ ...config, welcomeBonusXp: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                </div>
              </div>

              {/* XP Thresholds */}
              <div>
                <h3 className="font-medium mb-4">Paliers XP et Rôles</h3>
                <div className="space-y-3">
                  {config.xpThresholds.map((threshold, index) => (
                    <div key={index} className="flex items-center gap-4">
                      <input
                        type="number"
                        value={threshold.points}
                        onChange={(e) => {
                          const newThresholds = [...config.xpThresholds];
                          newThresholds[index].points = parseInt(e.target.value);
                          setConfig({ ...config, xpThresholds: newThresholds });
                        }}
                        className="w-24 px-3 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                      <span className="text-discord-gray">points →</span>
                      <input
                        type="text"
                        value={threshold.roleName}
                        onChange={(e) => {
                          const newThresholds = [...config.xpThresholds];
                          newThresholds[index].roleName = e.target.value;
                          setConfig({ ...config, xpThresholds: newThresholds });
                        }}
                        className="flex-1 px-3 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                        placeholder="Nom du rôle"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Onboarding */}
              <div className="border-t border-discord-gray/20 pt-8">
                <h3 className="font-medium mb-4">Onboarding</h3>
                
                <div className="space-y-4">
                  {/* DM Toggle */}
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">Message de bienvenue (DM)</div>
                      <p className="text-sm text-discord-gray">Envoyer un guide aux nouveaux membres</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={config.welcomeDmEnabled}
                        onChange={(e) => setConfig({ ...config, welcomeDmEnabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                    </label>
                  </div>

                  {/* DM Text */}
                  {config.welcomeDmEnabled && (
                    <div>
                      <label className="block font-medium mb-2">Texte du DM</label>
                      <textarea
                        value={config.welcomeDmText}
                        onChange={(e) => setConfig({ ...config, welcomeDmText: e.target.value })}
                        rows={6}
                        className="w-full px-4 py-3 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none resize-none"
                      />
                    </div>
                  )}

                  {/* Ambassador Ping */}
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">Ping Ambassadeur</div>
                      <p className="text-sm text-discord-gray">Notifier un ambassadeur pour accueillir les nouveaux</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={config.ambassadorPingEnabled}
                        onChange={(e) => setConfig({ ...config, ambassadorPingEnabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                    </label>
                  </div>
                </div>
              </div>

              {/* Challenges */}
              <div className="border-t border-discord-gray/20 pt-8">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium">Challenges Hebdomadaires</h3>
                  <button className="px-4 py-2 bg-discord-accent/20 text-discord-accent rounded-lg hover:bg-discord-accent/30 transition-colors">
                    + Ajouter
                  </button>
                </div>
                
                <div className="space-y-3">
                  {challenges.map((challenge) => (
                    <div key={challenge.id} className="flex items-center gap-4 p-4 bg-discord-darker rounded-lg">
                      <div className="flex-1">
                        <div className="font-medium">{challenge.name}</div>
                        <div className="text-sm text-discord-gray">{challenge.description}</div>
                      </div>
                      <div className="text-discord-accent">{challenge.rewardXp} XP</div>
                      <button className="text-discord-gray hover:text-white">✏️</button>
                      <button className="text-discord-red hover:text-red-400">🗑️</button>
                    </div>
                  ))}
                </div>

                <button className="mt-4 px-4 py-2 bg-discord-green text-white rounded-lg hover:opacity-90 transition-opacity">
                  🚀 Lancer un challenge maintenant
                </button>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-8">
              <h2 className="text-xl font-semibold mb-6">Notifications</h2>
              
              {/* Event Reminders */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium">Rappels d&apos;événements</h3>
                  <p className="text-sm text-discord-gray">
                    Envoyer des rappels 24h et 1h avant les événements
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.eventRemindersEnabled}
                    onChange={(e) => setConfig({ ...config, eventRemindersEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                </label>
              </div>

              {/* Twitch/YouTube alerts would go here */}
              <div className="p-6 bg-discord-darker rounded-lg text-center text-discord-gray">
                <p>Configuration des alertes Twitch/YouTube</p>
                <p className="text-sm mt-2">Disponible dans les paramètres du bot Discord</p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
