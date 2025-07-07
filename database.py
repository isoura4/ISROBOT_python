import os
import sqlite3
import dotenv

if os.path.exists('./database.sqlite3'):
    print("La base de données existe déjà.")
else:
    print("La base de données n'existe pas, elle vas être créée.")
    write_db = open('./database.sqlite3', 'w')
    write_db.close()

# Charger les variables d'environnement depuis le fichier .env
dotenv.load_dotenv()

# Chemin vers la base de données SQLite
DB_PATH = os.getenv('db_path')

def get_db_connection():
    """Crée une connexion à la base de données SQLite."""
    if not DB_PATH:
        raise ValueError("Le chemin de la base de données n'est pas défini dans les variables d'environnement.")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    return conn