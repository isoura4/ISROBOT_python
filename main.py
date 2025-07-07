#Importation des librairy et modules
import os
import discord
import logging
from dotenv import load_dotenv
from discord import Intents, app_commands
from discord.ext import commands
from pathlib import Path

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
APP_ID = int(os.getenv('app_id', '0'))
TOKEN = os.getenv('secret_key')
SERVER_ID = int(os.getenv('server_id', '0'))

#Parametrage des logs
logging.basicConfig(filename='discord.log', level=logging.INFO, encoding='utf-8', format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# Configuration des intents
intents = discord.Intents(messages = True, guilds = True, voice_states = True, message_content = True)


# --- Événements du bot ---

class ISROBOT(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="", intents=intents, application_id=APP_ID)

    async def setup_hook(self):
        #suprime toutes les commande /
        self.tree.clear_commands(guild=None)
        print("Commande existante vidée")
        #Parcour les fichier contenant des commandes
        commands_path = Path("commands/")
        for file in commands_path.glob('*.py') :
            if file.name.startswith('_'):
                continue
            # Charger le module comme extension
            module_name = f"commands.{file.stem}"
            try:
                await self.load_extension(module_name)
                print(f"Extension {module_name} chargée avec succès")
            except Exception as e:
                print(f"Erreur lors du chargement de {module_name}: {e}")
        
        # Synchroniser les commandes avec Discord
        try:
            # Synchronisation globale (peut prendre jusqu'à 1 heure)
            synced_global = await self.tree.sync()
            print(f"{len(synced_global)} commande(s) synchronisée(s) globalement")
            
            # Synchronisation sur le serveur spécifique (instantané)
            synced_guild = await self.tree.sync(guild=discord.Object(id=SERVER_ID))
            print(f"{len(synced_guild)} commande(s) synchronisée(s) avec le serveur")
            
        except Exception as e:
            print(f"Erreur lors de la synchronisation: {e}")
            import traceback
            traceback.print_exc()

    async def on_ready(self):
        print('Ready !')
        if self.user:
            print(f'Connecté en tant que {self.user} (ID: {self.user.id})')
        else:
            print('Erreur: Utilisateur non défini')

client = ISROBOT()
if TOKEN:
    client.run(TOKEN)
else:
    print("Erreur: TOKEN non trouvé dans le fichier .env")