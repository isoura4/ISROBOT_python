#Importation des librairy et modules
import os
import discord
import logging
import random
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
DB_PATH = os.getenv('db_path')

#Parametrage des logs
logging.basicConfig(filename='discord.log', level=logging.INFO, encoding='utf-8', format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# Configuration des intents
intents = discord.Intents(messages = True, guilds = True, voice_states = True, message_content = True)


# --- Événements du bot ---

class ISROBOT(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="µ", intents=intents, application_id=APP_ID)

    async def setup_hook(self):
        # Lancer le script database.py pour créer la base de données
        print("Initialisation de la base de données...")
        try:
            import database
            database.create_database()
            print("Base de données initialisée avec succès.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation de la base de données: {e}")
        
        # Supprimer toutes les commandes /
        self.tree.clear_commands(guild=None)
        print("Commandes existantes vidées")
        
        # Parcourir les fichiers contenant des commandes
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

        # Vérifie si le minijeux du compteur est configuré
        try:
            import database
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM counter_game WHERE guildId = ?', (str(SERVER_ID),))
            result = cursor.fetchone()
            if result:
                print("Le minijeux du compteur est déjà configuré.")
            else:
                print("Le minijeux du compteur n'est pas configuré.")
            conn.close()
        except Exception as e:
            print(f"Erreur lors de la vérification du minijeux du compteur: {e}")
            import traceback
            traceback.print_exc()

    async def on_message(self, message: discord.Message):
        # Ignorer les messages des bots
        if message.author.bot:
            return
        # Quand un message est envoyé dans le salon compteur du minijeux comparé avec le dernier chiffre
        import sqlite3
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM counter_game WHERE guildId = ? AND channelId = ?',
                       (str(message.guild.id), str(message.channel.id)))
        result = cursor.fetchone()
        if result:
            # Si le message est envoyé dans le salon du minijeux compteur
            last_user_id = result['lastUserId']
            last_count = result['count']
            count = message.content
            if message.content.isdigit() and not str(message.content).isspace(): # Vérifie si le message est un chiffre
                if str(message.author.id) == last_user_id:
                    await message.add_reaction('❌')
                    await message.channel.send("Vous ne pouvez pas compter deux fois de suite !")
                    await message.channel.send("On recommence à zéro !")
                    # Réinitialiser le compteur
                    cursor.execute('UPDATE counter_game SET count = 0, lastUserId = NULL WHERE guildId = ?',
                                (str(message.guild.id),))
                    conn.commit()
                    await message.channel.send("Le compteur a été réinitialisé.")
                    return
                if str(int(message.content)) == str(result['count'] + 1):
                    await message.add_reaction('✅')
                    # Mettre à jour le compteur
                    cursor.execute('UPDATE counter_game SET count = ?, lastUserId = ? WHERE guildId = ? AND channelId = ?',
                                (count, str(message.author.id), str(message.guild.id), str(message.channel.id)))
                    conn.commit()
                    return
                if str(int(message.content)) == str(result['count']):
                    await message.add_reaction('❌')
                    await message.channel.send("Vous avez mis le même chiffre ! Le bon chiffre était " + str(last_count + 1))
                    await message.channel.send("On recommence à zéro !")
                    # Réinitialiser le compteur
                    cursor.execute('UPDATE counter_game SET count = 0, lastUserId = NULL WHERE guildId = ?',
                                (str(message.guild.id),))
                    conn.commit()
                    await message.channel.send("Le compteur a été réinitialisé.")
                    return
            else:
                return


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