# ISROBOT Dashboard

Dashboard web pour gérer le bot Discord ISROBOT.

## Fonctionnalités

- **Landing Page** : Présentation du bot avec statistiques globales
- **Sélecteur de Serveur** : Liste des serveurs où l'utilisateur est admin
- **Dashboard Principal** : Vue d'ensemble avec KPIs, graphiques d'activité et leaderboard XP
- **Configuration** : Gestion des paramètres de modération, engagement et notifications
- **Analytics** : Statistiques détaillées avec export CSV

## Stack Technique

- **Framework** : Next.js 14 (App Router)
- **Styling** : Tailwind CSS
- **Design** : Palette Discord-like (#2C2F33, #23272A, #5865F2)
- **Auth** : Discord OAuth2 (via NextAuth)

## Installation

1. Installer les dépendances :
```bash
npm install
```

2. Copier le fichier d'environnement :
```bash
cp .env.example .env.local
```

3. Configurer les variables d'environnement dans `.env.local`

4. Lancer le serveur de développement :
```bash
npm run dev
```

5. Ouvrir [http://localhost:3000](http://localhost:3000)

## Configuration

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | URL de l'API backend (Flask) |
| `API_SECRET` | Clé secrète pour l'authentification API |
| `DISCORD_CLIENT_ID` | ID client Discord pour OAuth |
| `DISCORD_CLIENT_SECRET` | Secret client Discord |
| `NEXTAUTH_SECRET` | Secret pour NextAuth |

## Structure

```
dashboard/
├── src/
│   ├── app/
│   │   ├── page.tsx              # Landing page
│   │   ├── layout.tsx            # Layout principal
│   │   ├── globals.css           # Styles globaux
│   │   └── dashboard/
│   │       ├── page.tsx          # Sélecteur de serveur
│   │       └── [guildId]/
│   │           ├── page.tsx      # Dashboard principal
│   │           ├── config/       # Configuration
│   │           └── analytics/    # Analytics
│   ├── components/               # Composants réutilisables
│   └── lib/
│       └── api.ts                # Client API
├── public/                       # Assets statiques
├── tailwind.config.js
└── next.config.js
```

## Build Production

```bash
npm run build
npm start
```
