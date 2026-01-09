import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-discord-accent/20 via-transparent to-transparent" />
        
        {/* Navigation */}
        <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <span className="text-xl font-bold">ISROBOT</span>
          </div>
          <div className="flex items-center gap-4">
            <Link 
              href="/dashboard"
              className="px-4 py-2 text-discord-gray hover:text-white transition-colors"
            >
              Dashboard
            </Link>
            <Link 
              href="/api/auth/signin"
              className="px-6 py-2 bg-discord-accent hover:bg-discord-accent-hover rounded-lg font-medium transition-colors"
            >
              Login avec Discord
            </Link>
          </div>
        </nav>

        {/* Hero Content */}
        <div className="relative z-10 flex flex-col items-center justify-center px-8 py-24 text-center max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Gérez votre serveur Discord
            <span className="text-discord-accent"> simplement</span>
          </h1>
          <p className="text-xl text-discord-gray mb-12 max-w-2xl">
            ISROBOT est un bot Discord complet avec système XP, onboarding automatisé,
            challenges hebdomadaires, modération IA et bien plus encore.
          </p>
          
          <div className="flex flex-wrap gap-4 justify-center">
            <a 
              href="https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands"
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-4 bg-discord-accent hover:bg-discord-accent-hover rounded-lg font-semibold text-lg transition-colors card-hover"
            >
              Inviter le Bot
            </a>
            <Link 
              href="/api/auth/signin"
              className="px-8 py-4 bg-discord-darker hover:bg-discord-dark rounded-lg font-semibold text-lg border border-discord-gray/30 transition-colors card-hover"
            >
              Accéder au Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-16">
            Fonctionnalités
          </h2>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature Card 1 */}
            <div className="bg-discord-darker rounded-xl p-6 card-hover">
              <div className="text-4xl mb-4">⭐</div>
              <h3 className="text-xl font-semibold mb-2">Système XP</h3>
              <p className="text-discord-gray">
                Système de points d&apos;expérience avec paliers, rôles automatiques
                et leaderboard en temps réel.
              </p>
            </div>

            {/* Feature Card 2 */}
            <div className="bg-discord-darker rounded-xl p-6 card-hover">
              <div className="text-4xl mb-4">👋</div>
              <h3 className="text-xl font-semibold mb-2">Onboarding</h3>
              <p className="text-discord-gray">
                Accueillez automatiquement les nouveaux membres avec messages
                personnalisés et rôles temporaires.
              </p>
            </div>

            {/* Feature Card 3 */}
            <div className="bg-discord-darker rounded-xl p-6 card-hover">
              <div className="text-4xl mb-4">🎯</div>
              <h3 className="text-xl font-semibold mb-2">Challenges</h3>
              <p className="text-discord-gray">
                Lancez des challenges hebdomadaires pour engager votre communauté
                et récompenser les participants.
              </p>
            </div>

            {/* Feature Card 4 */}
            <div className="bg-discord-darker rounded-xl p-6 card-hover">
              <div className="text-4xl mb-4">🤖</div>
              <h3 className="text-xl font-semibold mb-2">Modération IA</h3>
              <p className="text-discord-gray">
                Modération intelligente basée sur l&apos;IA pour détecter et
                signaler les contenus problématiques.
              </p>
            </div>

            {/* Feature Card 5 */}
            <div className="bg-discord-darker rounded-xl p-6 card-hover">
              <div className="text-4xl mb-4">📅</div>
              <h3 className="text-xl font-semibold mb-2">Rappels Events</h3>
              <p className="text-discord-gray">
                Rappels automatiques pour les événements Discord programmés
                à 24h et 1h avant le début.
              </p>
            </div>

            {/* Feature Card 6 */}
            <div className="bg-discord-darker rounded-xl p-6 card-hover">
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-xl font-semibold mb-2">Analytics</h3>
              <p className="text-discord-gray">
                Tableau de bord complet avec statistiques détaillées,
                graphiques et export CSV.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 px-8 bg-discord-darker/50">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <div className="text-4xl font-bold text-discord-accent">1+</div>
              <div className="text-discord-gray mt-2">Serveurs</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-discord-green">100+</div>
              <div className="text-discord-gray mt-2">Utilisateurs</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-discord-yellow">10k+</div>
              <div className="text-discord-gray mt-2">Messages traités</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-white">99.9%</div>
              <div className="text-discord-gray mt-2">Uptime</div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-8 border-t border-discord-gray/20">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <span className="font-semibold">ISROBOT</span>
            <span className="text-discord-gray">© 2024</span>
          </div>
          <div className="flex items-center gap-6 text-discord-gray">
            <a href="#" className="hover:text-white transition-colors">Documentation</a>
            <a href="#" className="hover:text-white transition-colors">Support</a>
            <a href="https://github.com/isoura4/ISROBOT_python" className="hover:text-white transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </main>
  );
}
