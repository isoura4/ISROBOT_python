'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

type TabId = 'moderation' | 'engagement' | 'notifications' | 'streamers' | 'minigames';

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
    logChannelId: '',
    appealChannelId: '',
    warnDecay1Days: 7,
    warnDecay2Days: 14,
    warnDecay3Days: 21,
    
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
    ambassadorRoleId: '',
    newMemberRoleId: '',
    newMemberRoleDays: 7,
    announcementsChannelId: '',
    
    // XP Thresholds
    xpThresholds: [
      { points: 50, roleId: '', roleName: 'Membre Actif' },
      { points: 100, roleId: '', roleName: 'Contributeur' },
      { points: 250, roleId: '', roleName: 'Vétéran' },
      { points: 500, roleId: '', roleName: 'Champion' },
      { points: 1000, roleId: '', roleName: 'Légende' },
    ],
    
    // Voice XP
    voiceXpEnabled: true,
    voiceXpMin: 15,
    voiceXpMax: 25,
    voiceXpInterval: 60, // minutes
    
    // Notifications
    eventRemindersEnabled: true,
    eventReminder24hEnabled: true,
    eventReminder1hEnabled: true,
    
    // Minigames
    minigameEnabled: true,
    minigameChannelId: '',
    xpTradingEnabled: true,
    tradeTaxPercent: 10,
    duelTaxPercent: 10,
    captureCooldownSeconds: 60,
    duelCooldownSeconds: 300,
  });

  // Challenges state
  const [challenges, setChallenges] = useState([
    { id: 1, name: '📸 Meme Week', description: 'Créez et partagez vos meilleurs mèmes', rewardXp: 100, active: true },
    { id: 2, name: '💻 Setup Showcase', description: 'Montrez votre setup gaming/travail', rewardXp: 150, active: true },
    { id: 3, name: '🎨 Art Challenge', description: 'Créez une œuvre artistique', rewardXp: 200, active: true },
  ]);

  // Streamers state
  const [streamers, setStreamers] = useState([
    { id: 1, name: 'streamer1', channelId: '', roleId: '', platform: 'twitch' },
  ]);
  const [newStreamer, setNewStreamer] = useState({ name: '', channelId: '', roleId: '' });

  // YouTube channels state
  const [youtubeChannels, setYoutubeChannels] = useState([
    { id: 1, channelId: '', channelName: 'Ma Chaîne', discordChannelId: '', roleId: '', notifyVideos: true, notifyShorts: true, notifyLive: true },
  ]);
  const [newYoutubeChannel, setNewYoutubeChannel] = useState({ channelId: '', channelName: '', discordChannelId: '', roleId: '' });

  const handleSave = async () => {
    setSaving(true);
    // In production: await api.updateGuildConfig(guildId, config);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setSaving(false);
    alert('Configuration sauvegardée !');
  };

  const handleAddStreamer = () => {
    if (newStreamer.name.trim()) {
      setStreamers([...streamers, { ...newStreamer, id: Date.now(), platform: 'twitch' }]);
      setNewStreamer({ name: '', channelId: '', roleId: '' });
    }
  };

  const handleRemoveStreamer = (id: number) => {
    setStreamers(streamers.filter(s => s.id !== id));
  };

  const handleAddYoutubeChannel = () => {
    if (newYoutubeChannel.channelId.trim()) {
      setYoutubeChannels([...youtubeChannels, { 
        ...newYoutubeChannel, 
        id: Date.now(), 
        notifyVideos: true, 
        notifyShorts: true, 
        notifyLive: true 
      }]);
      setNewYoutubeChannel({ channelId: '', channelName: '', discordChannelId: '', roleId: '' });
    }
  };

  const handleRemoveYoutubeChannel = (id: number) => {
    setYoutubeChannels(youtubeChannels.filter(c => c.id !== id));
  };

  const handleAddChallenge = () => {
    const name = prompt('Nom du challenge:');
    const description = prompt('Description:');
    const rewardXp = parseInt(prompt('Récompense XP:') || '100');
    if (name && description) {
      setChallenges([...challenges, { id: Date.now(), name, description, rewardXp, active: true }]);
    }
  };

  const handleRemoveChallenge = (id: number) => {
    setChallenges(challenges.filter(c => c.id !== id));
  };

  const tabs = [
    { id: 'engagement' as const, name: 'Engagement', icon: '⭐' },
    { id: 'moderation' as const, name: 'Modération & AI', icon: '🛡️' },
    { id: 'notifications' as const, name: 'Notifications', icon: '🔔' },
    { id: 'streamers' as const, name: 'Twitch & YouTube', icon: '📺' },
    { id: 'minigames' as const, name: 'Minijeux', icon: '🎮' },
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
        <div className="flex flex-wrap gap-2 mb-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
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
          {/* ENGAGEMENT TAB */}
          {activeTab === 'engagement' && (
            <div className="space-y-8">
              <h2 className="text-xl font-semibold mb-6">Système d&apos;Engagement</h2>
              
              {/* XP Settings */}
              <div className="grid md:grid-cols-3 gap-6">
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
                <div>
                  <label className="block font-medium mb-2">Salon annonces</label>
                  <input
                    type="text"
                    placeholder="ID du salon"
                    value={config.announcementsChannelId}
                    onChange={(e) => setConfig({ ...config, announcementsChannelId: e.target.value })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                </div>
              </div>

              {/* Voice XP */}
              <div className="border-t border-discord-gray/20 pt-8">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-medium">XP Vocal</h3>
                    <p className="text-sm text-discord-gray">Gagner de l&apos;XP en étant en vocal</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.voiceXpEnabled}
                      onChange={(e) => setConfig({ ...config, voiceXpEnabled: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                  </label>
                </div>
                {config.voiceXpEnabled && (
                  <div className="grid md:grid-cols-3 gap-6">
                    <div>
                      <label className="block font-medium mb-2">XP min/heure</label>
                      <input
                        type="number"
                        min="1"
                        value={config.voiceXpMin}
                        onChange={(e) => setConfig({ ...config, voiceXpMin: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block font-medium mb-2">XP max/heure</label>
                      <input
                        type="number"
                        min="1"
                        value={config.voiceXpMax}
                        onChange={(e) => setConfig({ ...config, voiceXpMax: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block font-medium mb-2">Intervalle (min)</label>
                      <input
                        type="number"
                        min="1"
                        value={config.voiceXpInterval}
                        onChange={(e) => setConfig({ ...config, voiceXpInterval: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* XP Thresholds */}
              <div className="border-t border-discord-gray/20 pt-8">
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
                      <input
                        type="text"
                        value={threshold.roleId}
                        onChange={(e) => {
                          const newThresholds = [...config.xpThresholds];
                          newThresholds[index].roleId = e.target.value;
                          setConfig({ ...config, xpThresholds: newThresholds });
                        }}
                        className="w-48 px-3 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                        placeholder="ID du rôle"
                      />
                      <button
                        onClick={() => {
                          const newThresholds = config.xpThresholds.filter((_, i) => i !== index);
                          setConfig({ ...config, xpThresholds: newThresholds });
                        }}
                        className="text-discord-red hover:text-red-400"
                      >
                        🗑️
                      </button>
                    </div>
                  ))}
                  <button
                    onClick={() => {
                      setConfig({
                        ...config,
                        xpThresholds: [...config.xpThresholds, { points: 0, roleId: '', roleName: '' }]
                      });
                    }}
                    className="px-4 py-2 bg-discord-accent/20 text-discord-accent rounded-lg hover:bg-discord-accent/30 transition-colors"
                  >
                    + Ajouter un palier
                  </button>
                </div>
              </div>

              {/* Onboarding */}
              <div className="border-t border-discord-gray/20 pt-8">
                <h3 className="font-medium mb-4">Onboarding</h3>
                
                <div className="space-y-4">
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <label className="block font-medium mb-2">Rôle Ambassadeur</label>
                      <input
                        type="text"
                        placeholder="ID du rôle"
                        value={config.ambassadorRoleId}
                        onChange={(e) => setConfig({ ...config, ambassadorRoleId: e.target.value })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block font-medium mb-2">Rôle Nouveau Membre</label>
                      <input
                        type="text"
                        placeholder="ID du rôle"
                        value={config.newMemberRoleId}
                        onChange={(e) => setConfig({ ...config, newMemberRoleId: e.target.value })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                  </div>
                  
                  <div>
                    <label className="block font-medium mb-2">Durée rôle nouveau (jours)</label>
                    <input
                      type="number"
                      min="1"
                      max="30"
                      value={config.newMemberRoleDays}
                      onChange={(e) => setConfig({ ...config, newMemberRoleDays: parseInt(e.target.value) })}
                      className="w-32 px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                    />
                  </div>

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

                  {/* Public welcome text */}
                  <div>
                    <label className="block font-medium mb-2">Message de bienvenue public</label>
                    <input
                      type="text"
                      value={config.welcomePublicText}
                      onChange={(e) => setConfig({ ...config, welcomePublicText: e.target.value })}
                      className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      placeholder="Utilisez {user} pour mentionner le membre"
                    />
                  </div>

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

                  {/* Welcome detection */}
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">Détection &quot;Bienvenue&quot;</div>
                      <p className="text-sm text-discord-gray">Bonus XP quand un membre dit bienvenue à un nouveau</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={config.welcomeDetectionEnabled}
                        onChange={(e) => setConfig({ ...config, welcomeDetectionEnabled: e.target.checked })}
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
                  <button 
                    onClick={handleAddChallenge}
                    className="px-4 py-2 bg-discord-accent/20 text-discord-accent rounded-lg hover:bg-discord-accent/30 transition-colors"
                  >
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
                      <button 
                        onClick={() => handleRemoveChallenge(challenge.id)}
                        className="text-discord-red hover:text-red-400"
                      >
                        🗑️
                      </button>
                    </div>
                  ))}
                </div>

                <button className="mt-4 px-4 py-2 bg-discord-green text-white rounded-lg hover:opacity-90 transition-opacity">
                  🚀 Lancer un challenge maintenant
                </button>
              </div>
            </div>
          )}

          {/* MODERATION TAB */}
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

              {/* Channels */}
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <label className="block font-medium mb-2">Salon de logs</label>
                  <input
                    type="text"
                    placeholder="ID du salon"
                    value={config.logChannelId}
                    onChange={(e) => setConfig({ ...config, logChannelId: e.target.value })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block font-medium mb-2">Salon d&apos;appels</label>
                  <input
                    type="text"
                    placeholder="ID du salon"
                    value={config.appealChannelId}
                    onChange={(e) => setConfig({ ...config, appealChannelId: e.target.value })}
                    className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                </div>
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

              {/* Warning Decay */}
              <div className="border-t border-discord-gray/20 pt-8">
                <h3 className="font-medium mb-4">Expiration des avertissements</h3>
                <div className="grid md:grid-cols-3 gap-6">
                  <div>
                    <label className="block font-medium mb-2">1er warn expire après (jours)</label>
                    <input
                      type="number"
                      min="1"
                      value={config.warnDecay1Days}
                      onChange={(e) => setConfig({ ...config, warnDecay1Days: parseInt(e.target.value) })}
                      className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-medium mb-2">2ème warn expire après (jours)</label>
                    <input
                      type="number"
                      min="1"
                      value={config.warnDecay2Days}
                      onChange={(e) => setConfig({ ...config, warnDecay2Days: parseInt(e.target.value) })}
                      className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-medium mb-2">3ème warn expire après (jours)</label>
                    <input
                      type="number"
                      min="1"
                      value={config.warnDecay3Days}
                      onChange={(e) => setConfig({ ...config, warnDecay3Days: parseInt(e.target.value) })}
                      className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* NOTIFICATIONS TAB */}
          {activeTab === 'notifications' && (
            <div className="space-y-8">
              <h2 className="text-xl font-semibold mb-6">Notifications</h2>
              
              {/* Event Reminders */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium">Rappels d&apos;événements</h3>
                    <p className="text-sm text-discord-gray">
                      Envoyer des rappels automatiques pour les événements Discord
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

                {config.eventRemindersEnabled && (
                  <div className="ml-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-discord-gray">Rappel 24h avant</span>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={config.eventReminder24hEnabled}
                          onChange={(e) => setConfig({ ...config, eventReminder24hEnabled: e.target.checked })}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                      </label>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-discord-gray">Rappel 1h avant</span>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={config.eventReminder1hEnabled}
                          onChange={(e) => setConfig({ ...config, eventReminder1hEnabled: e.target.checked })}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                      </label>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STREAMERS TAB */}
          {activeTab === 'streamers' && (
            <div className="space-y-8">
              {/* Twitch Section */}
              <div>
                <h2 className="text-xl font-semibold mb-6">🟣 Streamers Twitch</h2>
                
                <div className="space-y-4">
                  {streamers.map((streamer) => (
                    <div key={streamer.id} className="flex items-center gap-4 p-4 bg-discord-darker rounded-lg">
                      <div className="flex-1">
                        <div className="font-medium">{streamer.name}</div>
                        <div className="text-sm text-discord-gray">Salon: {streamer.channelId || 'Non configuré'}</div>
                      </div>
                      <input
                        type="text"
                        placeholder="ID salon Discord"
                        value={streamer.channelId}
                        onChange={(e) => {
                          setStreamers(streamers.map(s => 
                            s.id === streamer.id ? { ...s, channelId: e.target.value } : s
                          ));
                        }}
                        className="w-40 px-3 py-2 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                      <input
                        type="text"
                        placeholder="ID rôle ping"
                        value={streamer.roleId}
                        onChange={(e) => {
                          setStreamers(streamers.map(s => 
                            s.id === streamer.id ? { ...s, roleId: e.target.value } : s
                          ));
                        }}
                        className="w-40 px-3 py-2 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                      <button 
                        onClick={() => handleRemoveStreamer(streamer.id)}
                        className="text-discord-red hover:text-red-400"
                      >
                        🗑️
                      </button>
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex gap-4">
                  <input
                    type="text"
                    placeholder="Nom Twitch"
                    value={newStreamer.name}
                    onChange={(e) => setNewStreamer({ ...newStreamer, name: e.target.value })}
                    className="flex-1 px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                  <button
                    onClick={handleAddStreamer}
                    className="px-4 py-2 bg-discord-accent hover:bg-discord-accent-hover rounded-lg font-medium transition-colors"
                  >
                    + Ajouter
                  </button>
                </div>
              </div>

              {/* YouTube Section */}
              <div className="border-t border-discord-gray/20 pt-8">
                <h2 className="text-xl font-semibold mb-6">🔴 Chaînes YouTube</h2>
                
                <div className="space-y-4">
                  {youtubeChannels.map((channel) => (
                    <div key={channel.id} className="p-4 bg-discord-darker rounded-lg">
                      <div className="flex items-center gap-4 mb-3">
                        <div className="flex-1">
                          <div className="font-medium">{channel.channelName || 'Chaîne YouTube'}</div>
                          <div className="text-sm text-discord-gray">{channel.channelId || 'ID non configuré'}</div>
                        </div>
                        <button 
                          onClick={() => handleRemoveYoutubeChannel(channel.id)}
                          className="text-discord-red hover:text-red-400"
                        >
                          🗑️
                        </button>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <input
                          type="text"
                          placeholder="ID chaîne YouTube"
                          value={channel.channelId}
                          onChange={(e) => {
                            setYoutubeChannels(youtubeChannels.map(c => 
                              c.id === channel.id ? { ...c, channelId: e.target.value } : c
                            ));
                          }}
                          className="px-3 py-2 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                        />
                        <input
                          type="text"
                          placeholder="ID salon Discord"
                          value={channel.discordChannelId}
                          onChange={(e) => {
                            setYoutubeChannels(youtubeChannels.map(c => 
                              c.id === channel.id ? { ...c, discordChannelId: e.target.value } : c
                            ));
                          }}
                          className="px-3 py-2 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                        />
                        <input
                          type="text"
                          placeholder="ID rôle ping"
                          value={channel.roleId}
                          onChange={(e) => {
                            setYoutubeChannels(youtubeChannels.map(c => 
                              c.id === channel.id ? { ...c, roleId: e.target.value } : c
                            ));
                          }}
                          className="px-3 py-2 bg-discord-dark rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                        />
                      </div>
                      <div className="flex gap-6 mt-3">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={channel.notifyVideos}
                            onChange={(e) => {
                              setYoutubeChannels(youtubeChannels.map(c => 
                                c.id === channel.id ? { ...c, notifyVideos: e.target.checked } : c
                              ));
                            }}
                            className="w-4 h-4 accent-discord-accent"
                          />
                          <span className="text-sm">Vidéos</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={channel.notifyShorts}
                            onChange={(e) => {
                              setYoutubeChannels(youtubeChannels.map(c => 
                                c.id === channel.id ? { ...c, notifyShorts: e.target.checked } : c
                              ));
                            }}
                            className="w-4 h-4 accent-discord-accent"
                          />
                          <span className="text-sm">Shorts</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={channel.notifyLive}
                            onChange={(e) => {
                              setYoutubeChannels(youtubeChannels.map(c => 
                                c.id === channel.id ? { ...c, notifyLive: e.target.checked } : c
                              ));
                            }}
                            className="w-4 h-4 accent-discord-accent"
                          />
                          <span className="text-sm">Lives</span>
                        </label>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex gap-4">
                  <input
                    type="text"
                    placeholder="ID ou @handle YouTube"
                    value={newYoutubeChannel.channelId}
                    onChange={(e) => setNewYoutubeChannel({ ...newYoutubeChannel, channelId: e.target.value })}
                    className="flex-1 px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                  <input
                    type="text"
                    placeholder="Nom de la chaîne"
                    value={newYoutubeChannel.channelName}
                    onChange={(e) => setNewYoutubeChannel({ ...newYoutubeChannel, channelName: e.target.value })}
                    className="flex-1 px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                  />
                  <button
                    onClick={handleAddYoutubeChannel}
                    className="px-4 py-2 bg-discord-accent hover:bg-discord-accent-hover rounded-lg font-medium transition-colors"
                  >
                    + Ajouter
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* MINIGAMES TAB */}
          {activeTab === 'minigames' && (
            <div className="space-y-8">
              <h2 className="text-xl font-semibold mb-6">Système de Minijeux</h2>
              
              {/* Main Toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium">Activer les minijeux</h3>
                  <p className="text-sm text-discord-gray">
                    Système de capture, duels, échanges et plus
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config.minigameEnabled}
                    onChange={(e) => setConfig({ ...config, minigameEnabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                </label>
              </div>

              {config.minigameEnabled && (
                <>
                  {/* Minigame Channel */}
                  <div>
                    <label className="block font-medium mb-2">Salon des minijeux</label>
                    <input
                      type="text"
                      placeholder="ID du salon (laisser vide pour tous les salons)"
                      value={config.minigameChannelId}
                      onChange={(e) => setConfig({ ...config, minigameChannelId: e.target.value })}
                      className="w-full max-w-md px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                    />
                    <p className="text-sm text-discord-gray mt-1">Si configuré, les minijeux ne fonctionneront que dans ce salon</p>
                  </div>

                  {/* XP Trading */}
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium">Échange d&apos;XP</h3>
                      <p className="text-sm text-discord-gray">
                        Permettre aux membres d&apos;échanger leur XP
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={config.xpTradingEnabled}
                        onChange={(e) => setConfig({ ...config, xpTradingEnabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-discord-gray/30 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-discord-accent"></div>
                    </label>
                  </div>

                  {/* Taxes */}
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <label className="block font-medium mb-2">Taxe échanges (%)</label>
                      <input
                        type="number"
                        min="0"
                        max="50"
                        value={config.tradeTaxPercent}
                        onChange={(e) => setConfig({ ...config, tradeTaxPercent: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block font-medium mb-2">Taxe duels (%)</label>
                      <input
                        type="number"
                        min="0"
                        max="50"
                        value={config.duelTaxPercent}
                        onChange={(e) => setConfig({ ...config, duelTaxPercent: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                  </div>

                  {/* Cooldowns */}
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <label className="block font-medium mb-2">Cooldown capture (secondes)</label>
                      <input
                        type="number"
                        min="0"
                        value={config.captureCooldownSeconds}
                        onChange={(e) => setConfig({ ...config, captureCooldownSeconds: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block font-medium mb-2">Cooldown duel (secondes)</label>
                      <input
                        type="number"
                        min="0"
                        value={config.duelCooldownSeconds}
                        onChange={(e) => setConfig({ ...config, duelCooldownSeconds: parseInt(e.target.value) })}
                        className="w-full px-4 py-2 bg-discord-darker rounded-lg border border-discord-gray/30 focus:border-discord-accent focus:outline-none"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
