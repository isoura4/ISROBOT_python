#Importation des librairy et modules
import os
import discord
import logging
from dotenv import load_dotenv
from discord import Intents, app_commands
from discord.ext import commands

# Chargement du fichier .env
load_dotenv()

# Récupération des variables d'environnement
APP_ID = int(os.getenv('app_id'))
TOKEN = os.getenv('secret_key')
SERVER_ID = int(os.getenv('server_id'))

#Parametrage des logs
logging.basicConfig(filename='discord.log', level=logging.INFO, encoding='utf-8', format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# Configuration des intents
intents = discord.Intents(messages = True, guilds = True, voice_states = True, message_content = True)

# Création du client Discord
bot = commands.Bot(command_prefix="!", intents=intents, application_id=APP_ID)

#Initialisation des commande "/"
tree = bot.tree

# test en dessous test :

@bot.event 
async def setup_hook():
    for x in bot.extensions:
        print(x)
        await bot.tree.clear_commands
    
    print("Commende vidé")

@bot.event
async def on_ready():
    print('Ready !')
    print(f'Connecté en tant que {bot.user} (ID: {bot.user.id})')


#Lancement du bot
if __name__ == "__main__":
    bot.run(TOKEN)