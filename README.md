# 🤖 ISROBOT - Bot Discord Complet

Bot Discord riche en fonctionnalités avec dashboard web, système d'XP, modération IA, minijeux, et intégrations Twitch/YouTube.

## 🚀 Installation Ultra-Simple

### 1. Cloner le projet
```bash
git clone https://github.com/isoura4/ISROBOT_python.git
cd ISROBOT_python
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Lancer le bot
```bash
python main.py
```

**C'est tout !** 🎉

Au premier lancement, un **assistant de configuration web** s'ouvrira automatiquement dans votre navigateur pour configurer le bot (http://localhost:8080).

---

## ⚙️ Configuration via l'Assistant Web

L'assistant de configuration permet de configurer :

| Section | Description |
|---------|-------------|
| 🎮 **Discord** | Token du bot, ID application, ID serveur |
| 🟣 **Twitch** | Client ID et Secret pour les notifications de stream |
| 🔴 **YouTube** | Clé API pour les notifications vidéo |
| 🧠 **IA** | Configuration Ollama pour modération et commande /ai |
| 🌐 **Dashboard** | Activation et configuration de l'interface web |
| 🎮 **Minijeux** | Activation du système de jeux et économie |

### Obtenir les identifiants requis

<details>
<summary><b>Discord</b></summary>

1. Allez sur [Discord Developer Portal](https://discord.com/developers/applications)
2. Créez une nouvelle application
3. Copiez l'**Application ID**
4. Dans la section "Bot", créez un bot et copiez le **Token**
5. Activez les intents : `MESSAGE CONTENT`, `SERVER MEMBERS`
6. Pour l'**ID Serveur** : Activez le mode développeur dans Discord, puis clic droit sur votre serveur → Copier l'ID
</details>

<details>
<summary><b>Twitch (optionnel)</b></summary>

1. Allez sur [Twitch Developers](https://dev.twitch.tv/console)
2. Créez une nouvelle application
3. Copiez le **Client ID** et **Client Secret**
</details>

<details>
<summary><b>YouTube (optionnel)</b></summary>

1. Allez sur [Google Cloud Console](https://console.cloud.google.com)
2. Créez un projet ou sélectionnez-en un
3. Activez l'API YouTube Data API v3
4. Créez des identifiants (Clé API)
</details>

---

## 🌐 Dashboard Web

Le dashboard web permet de **gérer toutes les fonctionnalités** du bot sans commandes Discord.

### Activer le Dashboard

Le dashboard est activé automatiquement si vous l'avez coché dans l'assistant de configuration.

Pour lancer le serveur web du dashboard :

```bash
cd dashboard
npm install
npm run dev
```

Le dashboard sera accessible sur http://localhost:3000

### Fonctionnalités du Dashboard

| Page | Description |
|------|-------------|
| **Vue d'ensemble** | KPIs, graphiques d'activité, leaderboard XP |
| **Configuration** | Tous les paramètres du bot organisés par onglets |
| **Analytics** | Statistiques détaillées avec export CSV |

#### Onglets de Configuration

- **⭐ Engagement** : XP messages, XP vocal, paliers et rôles, onboarding, challenges
- **🛡️ Modération** : IA, mutes, warnings, logs
- **🔔 Notifications** : Rappels d'événements
- **📺 Twitch/YouTube** : Gestion des streamers et chaînes
- **🎮 Minijeux** : Activation, taxes, cooldowns

---

## 📋 Fonctionnalités

### 📊 Système d'XP
- Gain d'XP par message (cooldown anti-spam)
- XP vocal (gain par heure en vocal)
- Niveaux automatiques avec annonces
- Attribution automatique de rôles par palier
- Leaderboard et commande `/level`

### 🛡️ Modération
- Système de warnings avec escalade automatique
- Mutes temporaires avec expiration
- Décroissance intelligente des warnings
- Modération IA (Ollama) avec validation humaine
- Système d'appels pour les utilisateurs
- Logs complets de toutes les actions

### 🎮 Minijeux
- **Économie** : Coins et XP échangeables
- **Quêtes journalières** : Récompenses et streaks
- **Capture** : Mise de coins pour en gagner plus
- **Duels** : Affrontez d'autres joueurs
- **Boutique** : Items et effets temporaires
- **Échanges P2P** : Trading entre joueurs

### 🟣 Twitch
- Notifications automatiques de streams
- Détection en temps réel (toutes les 5 min)
- Embeds riches avec miniatures

### 🔴 YouTube
- Notifications de vidéos et shorts
- Support des handles (@channel)
- Configuration par type de contenu

### 🧠 IA (Ollama)
- Commande `/ai` pour poser des questions
- Modération automatique des messages
- Filtrage de contenu inapproprié
- Support multi-modèles (Llama, Mistral...)

### 👋 Onboarding
- Message de bienvenue public personnalisable
- DM automatique aux nouveaux membres
- Rôle temporaire "Nouveau"
- Ping aléatoire d'ambassadeur

### 🏆 Challenges
- Challenges hebdomadaires automatiques
- Récompenses en XP et rôles
- Gestion via dashboard

---

## 🔧 Commandes Discord

### Générales
| Commande | Description |
|----------|-------------|
| `/ping` | Test de latence |
| `/ai <question>` | Poser une question à l'IA |
| `/coinflip` | Pile ou face |

### XP & Niveaux
| Commande | Description |
|----------|-------------|
| `/level [user]` | Voir son niveau ou celui d'un autre |
| `/leaderboard` | Classement du serveur |

### Minijeux
| Commande | Description |
|----------|-------------|
| `/wallet` | Voir ses coins et XP |
| `/daily claim` | Récupérer les quêtes journalières |
| `/capture <mise>` | Miser des coins |
| `/duel @user <mise>` | Défier un joueur |
| `/shop list` | Voir la boutique |
| `/trade offer @user` | Proposer un échange |

### Modération (Admin)
| Commande | Description |
|----------|-------------|
| `/warn <user> <raison>` | Avertir un utilisateur |
| `/mute <user> <durée>` | Mute temporaire |
| `/modconfig view` | Voir la configuration |

### Administration
| Commande | Description |
|----------|-------------|
| `/stream_add` | Ajouter un streamer Twitch |
| `/youtube_add` | Ajouter une chaîne YouTube |
| `/minigame enable/disable` | Activer/désactiver les minijeux |
| `/reload` | Recharger les extensions |

---

## 📁 Structure du Projet

```
ISROBOT_python/
├── main.py              # Point d'entrée principal
├── setup_wizard.py      # Assistant de configuration web
├── api.py               # API REST pour le dashboard
├── database.py          # Gestion base de données
├── requirements.txt     # Dépendances Python
├── .env                 # Configuration (généré par l'assistant)
├── commands/            # Modules de commandes
│   ├── ai.py           # Commande IA
│   ├── moderation.py   # Modération
│   ├── xp_system.py    # Système XP
│   ├── stream.py       # Twitch
│   ├── youtube.py      # YouTube
│   ├── minigame.py     # Minijeux
│   └── engagement.py   # Engagement (XP, onboarding, challenges)
├── dashboard/           # Interface web Next.js
│   ├── src/app/        # Pages
│   └── src/lib/        # Utilitaires
└── utils/               # Utilitaires
    ├── ai_moderation.py
    └── logging_config.py
```

---

## 🔒 Sécurité

- **Token Discord** : Jamais exposé, stocké dans `.env`
- **API Dashboard** : Authentification par clé secrète
- **Base de données** : SQLite local uniquement
- **IA** : Ollama en local, aucune donnée externe

---

## 📝 Reconfiguration

Pour relancer l'assistant de configuration :

```bash
rm .env
python main.py
```

Ou modifiez directement le fichier `.env`.

---

## 🆘 Support

- Créez une issue sur GitHub pour signaler un bug
- Consultez les logs dans `discord.log` en cas d'erreur

---

## 📜 Licence

MIT License - Voir le fichier LICENSE
