"""
ISROBOT Setup Wizard

This module provides a web-based setup interface that allows users to configure
the bot's .env file through a browser before the first launch.

The setup wizard runs on port 8080 by default and provides:
- Initial configuration of all environment variables
- Validation of Discord token and API credentials
- Database initialization
- Automatic .env file generation
"""

import os

import webbrowser
import threading
from pathlib import Path

from flask import Flask, render_template_string, request, jsonify


# Get the directory where this script is located
BASE_DIR = Path(__file__).parent.resolve()
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"

app = Flask(__name__)

# HTML template for the setup wizard
SETUP_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ISROBOT - Configuration Initiale</title>
    <style>
        :root {
            --bg-darker: #1a1a2e;
            --bg-dark: #16213e;
            --bg-card: #0f3460;
            --accent: #5865F2;
            --accent-hover: #4752c4;
            --text: #ffffff;
            --text-muted: #b9bbbe;
            --success: #43b581;
            --error: #f04747;
            --warning: #faa61a;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, var(--bg-darker) 0%, var(--bg-dark) 100%);
            color: var(--text);
            min-height: 100vh;
            padding: 2rem;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 2rem;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .header p {
            color: var(--text-muted);
            font-size: 1.1rem;
        }

        .card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        .card h2 {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--accent);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }

        .form-group small {
            display: block;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 0.25rem;
        }

        input, select {
            width: 100%;
            padding: 0.75rem 1rem;
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            background: var(--bg-darker);
            color: var(--text);
            font-size: 1rem;
            transition: border-color 0.2s;
        }

        input:focus, select:focus {
            outline: none;
            border-color: var(--accent);
        }

        input::placeholder {
            color: var(--text-muted);
        }

        .required::after {
            content: " *";
            color: var(--error);
        }

        .optional {
            color: var(--text-muted);
            font-size: 0.85rem;
            font-weight: normal;
        }

        .row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        @media (max-width: 600px) {
            .row {
                grid-template-columns: 1fr;
            }
        }

        .btn {
            display: inline-block;
            padding: 1rem 2rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--accent);
            color: white;
            width: 100%;
        }

        .btn-primary:hover {
            background: var(--accent-hover);
            transform: translateY(-2px);
        }

        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .toggle-section {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem;
            background: var(--bg-darker);
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .toggle-label {
            font-weight: 500;
        }

        .toggle-switch {
            position: relative;
            width: 50px;
            height: 26px;
        }

        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: var(--bg-card);
            transition: 0.3s;
            border-radius: 26px;
        }

        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: 0.3s;
            border-radius: 50%;
        }

        .toggle-switch input:checked + .toggle-slider {
            background-color: var(--accent);
        }

        .toggle-switch input:checked + .toggle-slider:before {
            transform: translateX(24px);
        }

        .collapsible {
            display: none;
            margin-top: 1rem;
        }

        .collapsible.show {
            display: block;
        }

        .alert {
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .alert-success {
            background: rgba(67, 181, 129, 0.2);
            border: 1px solid var(--success);
            color: var(--success);
        }

        .alert-error {
            background: rgba(240, 71, 71, 0.2);
            border: 1px solid var(--error);
            color: var(--error);
        }

        .alert-info {
            background: rgba(88, 101, 242, 0.2);
            border: 1px solid var(--accent);
            color: var(--text);
        }

        .steps {
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .step {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            background: var(--bg-card);
            color: var(--text-muted);
        }

        .step.active {
            background: var(--accent);
            color: white;
        }

        .step-number {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85rem;
            font-weight: 600;
        }

        #loading {
            display: none;
            text-align: center;
            padding: 2rem;
        }

        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.2);
            border-top: 4px solid var(--accent);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .success-message {
            display: none;
            text-align: center;
            padding: 3rem;
        }

        .success-message .icon {
            font-size: 4rem;
            margin-bottom: 1rem;
        }

        .success-message h2 {
            color: var(--success);
            margin-bottom: 1rem;
            border: none;
            justify-content: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 ISROBOT</h1>
            <p>Assistant de configuration initiale</p>
        </div>

        <div class="steps">
            <div class="step active">
                <span class="step-number">1</span>
                <span>Configuration</span>
            </div>
            <div class="step">
                <span class="step-number">2</span>
                <span>Validation</span>
            </div>
            <div class="step">
                <span class="step-number">3</span>
                <span>Terminé</span>
            </div>
        </div>

        <div id="alert-container"></div>

        <form id="setup-form">
            <!-- Discord Configuration -->
            <div class="card">
                <h2>🎮 Configuration Discord (Requis)</h2>

                <div class="form-group">
                    <label class="required" for="app_id">Application ID</label>
                    <input type="text" id="app_id" name="app_id" placeholder="123456789012345678" required>
                    <small>ID de votre application Discord (Developer Portal → Applications → General Information)</small>
                </div>

                <div class="form-group">
                    <label class="required" for="secret_key">Token du Bot</label>
                    <input type="password" id="secret_key" name="secret_key" placeholder="Votre token secret" required>
                    <small>Token de votre bot (Developer Portal → Bot → Token). Gardez-le secret !</small>
                </div>

                <div class="form-group">
                    <label class="required" for="server_id">ID du Serveur</label>
                    <input type="text" id="server_id" name="server_id" placeholder="123456789012345678" required>
                    <small>ID de votre serveur Discord (Clic droit sur le serveur → Copier l'ID)</small>
                </div>
            </div>

            <!-- Database Configuration -->
            <div class="card">
                <h2>💾 Base de Données</h2>

                <div class="form-group">
                    <label for="db_path">Chemin de la base de données</label>
                    <input type="text" id="db_path" name="db_path" value="./database.sqlite3" placeholder="./database.sqlite3">
                    <small>Chemin vers le fichier SQLite (le fichier sera créé automatiquement)</small>
                </div>
            </div>

            <!-- Twitch Configuration -->
            <div class="card">
                <h2>🟣 Twitch <span class="optional">(Optionnel)</span></h2>

                <div class="toggle-section">
                    <span class="toggle-label">Activer les notifications Twitch</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="twitch_enabled" onchange="toggleSection('twitch')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>

                <div id="twitch-section" class="collapsible">
                    <div class="row">
                        <div class="form-group">
                            <label for="twitch_client_id">Client ID</label>
                            <input type="text" id="twitch_client_id" name="twitch_client_id" placeholder="Votre Client ID Twitch">
                        </div>
                        <div class="form-group">
                            <label for="twitch_client_secret">Client Secret</label>
                            <input type="password" id="twitch_client_secret" name="twitch_client_secret" placeholder="Votre Client Secret Twitch">
                        </div>
                    </div>
                    <small>Obtenez vos identifiants sur <a href="https://dev.twitch.tv/console" target="_blank" style="color: var(--accent)">dev.twitch.tv/console</a></small>
                </div>
            </div>

            <!-- YouTube Configuration -->
            <div class="card">
                <h2>🔴 YouTube <span class="optional">(Optionnel)</span></h2>

                <div class="toggle-section">
                    <span class="toggle-label">Activer les notifications YouTube</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="youtube_enabled" onchange="toggleSection('youtube')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>

                <div id="youtube-section" class="collapsible">
                    <div class="form-group">
                        <label for="youtube_api_key">Clé API YouTube</label>
                        <input type="password" id="youtube_api_key" name="youtube_api_key" placeholder="Votre clé API YouTube">
                        <small>Obtenez une clé sur <a href="https://console.cloud.google.com" target="_blank" style="color: var(--accent)">Google Cloud Console</a></small>
                    </div>
                </div>
            </div>

            <!-- AI Configuration -->
            <div class="card">
                <h2>🧠 Intelligence Artificielle <span class="optional">(Optionnel)</span></h2>

                <div class="toggle-section">
                    <span class="toggle-label">Activer les fonctionnalités IA</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="ai_enabled" onchange="toggleSection('ai')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>

                <div id="ai-section" class="collapsible">
                    <div class="row">
                        <div class="form-group">
                            <label for="ollama_host">URL Ollama</label>
                            <input type="text" id="ollama_host" name="ollama_host" value="http://localhost:11434" placeholder="http://localhost:11434">
                        </div>
                        <div class="form-group">
                            <label for="ollama_model">Modèle</label>
                            <select id="ollama_model" name="ollama_model">
                                <option value="llama2">Llama 2</option>
                                <option value="llama3">Llama 3</option>
                                <option value="mistral">Mistral</option>
                                <option value="mixtral">Mixtral</option>
                            </select>
                        </div>
                    </div>

                    <div class="toggle-section" style="margin-top: 1rem;">
                        <span class="toggle-label">Commande /ai</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="ai_command_enabled" name="ai_command_enabled">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>

                    <div class="toggle-section">
                        <span class="toggle-label">Modération AI automatique</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="ai_moderation_enabled" name="ai_moderation_enabled">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
            </div>

            <!-- Dashboard/API Configuration -->
            <div class="card">
                <h2>🌐 Dashboard Web <span class="optional">(Optionnel)</span></h2>

                <div class="toggle-section">
                    <span class="toggle-label">Activer le dashboard web</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="api_enabled" onchange="toggleSection('api')" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </div>

                <div id="api-section" class="collapsible show">
                    <div class="row">
                        <div class="form-group">
                            <label for="api_port">Port API</label>
                            <input type="number" id="api_port" name="api_port" value="5000" placeholder="5000">
                        </div>
                        <div class="form-group">
                            <label for="api_secret">Clé secrète API</label>
                            <input type="text" id="api_secret" name="api_secret" placeholder="Généré automatiquement">
                            <small>Laissez vide pour générer automatiquement</small>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Minigames -->
            <div class="card">
                <h2>🎮 Minijeux</h2>

                <div class="toggle-section">
                    <span class="toggle-label">Activer les minijeux</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="minigame_enabled" name="minigame_enabled" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </div>

            <div id="loading">
                <div class="spinner"></div>
                <p>Configuration en cours...</p>
            </div>

            <button type="submit" class="btn btn-primary" id="submit-btn">
                🚀 Sauvegarder et démarrer le bot
            </button>
        </form>

        <div class="success-message" id="success-message">
            <div class="icon">✅</div>
            <h2>Configuration terminée !</h2>
            <p>Le fichier .env a été créé avec succès.</p>
            <p style="margin-top: 1rem; color: var(--text-muted);">
                Le bot va démarrer automatiquement...<br>
                Vous pouvez fermer cette fenêtre.
            </p>
        </div>
    </div>

    <script>
        function toggleSection(section) {
            const checkbox = document.getElementById(section + '_enabled');
            const sectionDiv = document.getElementById(section + '-section');
            if (checkbox && sectionDiv) {
                if (checkbox.checked) {
                    sectionDiv.classList.add('show');
                } else {
                    sectionDiv.classList.remove('show');
                }
            }
        }

        function showAlert(message, type) {
            const container = document.getElementById('alert-container');
            container.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
            setTimeout(() => container.innerHTML = '', 5000);
        }

        function generateSecret() {
            const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
            let result = '';
            for (let i = 0; i < 32; i++) {
                result += chars.charAt(Math.floor(Math.random() * chars.length));
            }
            return result;
        }

        document.getElementById('setup-form').addEventListener('submit', async function(e) {
            e.preventDefault();

            const form = e.target;
            const submitBtn = document.getElementById('submit-btn');
            const loading = document.getElementById('loading');

            submitBtn.disabled = true;
            loading.style.display = 'block';

            // Collect form data
            const data = {
                app_id: form.app_id.value.trim(),
                secret_key: form.secret_key.value.trim(),
                server_id: form.server_id.value.trim(),
                db_path: form.db_path.value.trim() || './database.sqlite3',

                // Twitch
                twitch_client_id: document.getElementById('twitch_enabled').checked
                    ? form.twitch_client_id.value.trim() : '',
                twitch_client_secret: document.getElementById('twitch_enabled').checked
                    ? form.twitch_client_secret.value.trim() : '',

                // YouTube
                youtube_api_key: document.getElementById('youtube_enabled').checked
                    ? form.youtube_api_key.value.trim() : '',

                // AI
                ai_enabled: document.getElementById('ai_enabled').checked,
                ollama_host: form.ollama_host.value.trim() || 'http://localhost:11434',
                ollama_model: form.ollama_model.value,
                ai_command_enabled: document.getElementById('ai_command_enabled')?.checked || false,
                ai_moderation_enabled: document.getElementById('ai_moderation_enabled')?.checked || false,

                // API/Dashboard
                api_enabled: document.getElementById('api_enabled').checked,
                api_port: form.api_port.value || '5000',
                api_secret: form.api_secret.value.trim() || generateSecret(),

                // Minigames
                minigame_enabled: document.getElementById('minigame_enabled').checked
            };

            try {
                const response = await fetch('/save-config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (result.success) {
                    form.style.display = 'none';
                    document.getElementById('success-message').style.display = 'block';
                    document.querySelectorAll('.step')[1].classList.add('active');
                    document.querySelectorAll('.step')[2].classList.add('active');

                    // Redirect after 3 seconds
                    setTimeout(() => {
                        window.location.href = '/complete';
                    }, 3000);
                } else {
                    showAlert(result.error || 'Une erreur est survenue', 'error');
                    submitBtn.disabled = false;
                    loading.style.display = 'none';
                }
            } catch (error) {
                showAlert('Erreur de connexion: ' + error.message, 'error');
                submitBtn.disabled = false;
                loading.style.display = 'none';
            }
        });

        // Initialize sections
        toggleSection('api');
    </script>
</body>
</html>
"""

COMPLETE_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ISROBOT - Configuration Terminée</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .container {
            text-align: center;
            padding: 3rem;
        }
        .icon { font-size: 5rem; margin-bottom: 1rem; }
        h1 { color: #43b581; margin-bottom: 1rem; }
        p { color: #b9bbbe; margin-bottom: 0.5rem; }
        .code {
            background: #0f3460;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 2rem;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🎉</div>
        <h1>Configuration terminée !</h1>
        <p>Le fichier .env a été créé avec succès.</p>
        <p>Vous pouvez maintenant fermer cette fenêtre et redémarrer le bot.</p>
        <div class="code">
            python main.py
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    """Display the setup wizard."""
    return render_template_string(SETUP_HTML)


@app.route("/save-config", methods=["POST"])
def save_config():
    """Save the configuration to .env file."""
    try:
        data = request.get_json()

        # Validate required fields
        required = ["app_id", "secret_key", "server_id"]
        for field in required:
            if not data.get(field):
                return jsonify({"success": False, "error": f"Le champ {field} est requis"})

        # Validate IDs are numeric
        for field in ["app_id", "server_id"]:
            try:
                int(data[field])
            except ValueError:
                return jsonify({"success": False, "error": f"{field} doit être un nombre"})

        # Build .env content
        env_content = f"""# Configuration du bot Discord - Généré par l'assistant de configuration
# Date: {os.popen('date').read().strip()}

# ============================================================================
# CONFIGURATION DISCORD (Requis)
# ============================================================================

# ID de votre application Discord
app_id={data['app_id']}

# Token secret de votre bot
secret_key={data['secret_key']}

# ID de votre serveur Discord
server_id={data['server_id']}

# ============================================================================
# BASE DE DONNÉES
# ============================================================================

db_path={data.get('db_path', './database.sqlite3')}

# ============================================================================
# TWITCH API
# ============================================================================

twitch_client_id={data.get('twitch_client_id', '')}
twitch_client_secret={data.get('twitch_client_secret', '')}

# ============================================================================
# YOUTUBE API
# ============================================================================

youtube_api_key={data.get('youtube_api_key', '')}

# ============================================================================
# INTELLIGENCE ARTIFICIELLE (Ollama)
# ============================================================================

ollama_host={data.get('ollama_host', 'http://localhost:11434')}
ollama_model={data.get('ollama_model', 'llama2')}
AI_ENABLED={'true' if data.get('ai_enabled') else 'false'}
AI_COMMAND_ENABLED={'true' if data.get('ai_command_enabled') else 'false'}
AI_MODERATION_ENABLED={'true' if data.get('ai_moderation_enabled') else 'false'}
AI_CONTENT_FILTER_ENABLED={'true' if data.get('ai_enabled') else 'false'}

# ============================================================================
# DASHBOARD WEB / API
# ============================================================================

API_ENABLED={'true' if data.get('api_enabled') else 'false'}
API_PORT={data.get('api_port', '5000')}
API_SECRET={data.get('api_secret', 'change-me-in-production')}
DASHBOARD_ORIGINS=http://localhost:3000

# ============================================================================
# MINIJEUX
# ============================================================================

minigame_enabled={'true' if data.get('minigame_enabled', True) else 'false'}

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL=INFO
LOG_FILE=discord.log
LOG_MAX_SIZE_MB=5
LOG_BACKUP_COUNT=5

# ============================================================================
# BACKUPS
# ============================================================================

BACKUP_DIR=backups
MAX_BACKUPS=10
"""

        # Write to .env file
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(env_content)

        # Create a flag file to indicate setup is complete
        setup_complete_file = BASE_DIR / ".setup_complete"
        setup_complete_file.touch()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/complete")
def complete():
    """Display completion page."""
    return render_template_string(COMPLETE_HTML)


def is_setup_required():
    """Check if initial setup is required."""
    # Check if .env exists and has required values
    if not ENV_FILE.exists():
        return True

    # Try to load and validate the .env
    try:
        from dotenv import dotenv_values
        config = dotenv_values(ENV_FILE)

        required = ["app_id", "secret_key", "server_id"]
        for key in required:
            value = config.get(key, "")
            if not value or value.startswith("VOTRE_") or value == "123456789012345678":
                return True

        return False
    except Exception:
        return True


def run_setup_wizard(port=8080):
    """Run the setup wizard web server."""
    print("\n" + "=" * 60)
    print("🤖 ISROBOT - Assistant de Configuration")
    print("=" * 60)
    print("\n📋 Le fichier .env n'est pas configuré.")
    print("🌐 Ouverture de l'assistant de configuration dans votre navigateur...")
    print(f"\n   URL: http://localhost:{port}")
    print("\n   (Appuyez sur Ctrl+C pour annuler)")
    print("=" * 60 + "\n")

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    # Run Flask server
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    if is_setup_required():
        run_setup_wizard()
    else:
        print("✅ Configuration déjà effectuée. Utilisez 'python main.py' pour démarrer le bot.")
