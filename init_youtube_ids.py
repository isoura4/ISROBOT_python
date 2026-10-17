#!/usr/bin/env python3
"""
Script pour initialiser les derniers IDs de vidéos/shorts YouTube
pour éviter que le bot annonce toutes les anciennes vidéos au démarrage.
"""

import sqlite3
import sys

from dotenv import load_dotenv

import database

load_dotenv()


def main() -> int:
    # Utiliser le chemin résolu de façon centralisée (relatif → absolu par rapport au projet)
    db_path = database.DB_PATH

    if not db_path:
        print("❌ Erreur: db_path non défini dans .env")
        return 1

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Récupérer toutes les chaînes YouTube
    cursor.execute(
        "SELECT id, channelId, channelName, lastVideoId, lastShortId, lastLiveId "
        "FROM youtube_channels"
    )
    channels = cursor.fetchall()

    print(f"📋 {len(channels)} chaîne(s) YouTube configurée(s)\n")

    for channel in channels:
        (
            channel_db_id,
            channel_id,
            channel_name,
            last_video_id,
            last_short_id,
            last_live_id,
        ) = channel

        print(f"🔧 Configuration de: {channel_name} (ID: {channel_id})")
        print(f"   Dernière vidéo: {last_video_id or 'Non défini'}")
        print(f"   Dernier short: {last_short_id or 'Non défini'}")
        print(f"   Dernier live: {last_live_id or 'Non défini'}")

        # Si les IDs sont déjà définis, demander confirmation
        if last_video_id and last_short_id:
            print(
                "   ℹ️  Les IDs sont déjà initialisés. Passer à la chaîne suivante.\n"
            )
            continue

        # Proposer d'initialiser avec des IDs fictifs pour ignorer le contenu actuel
        print("\n   Options:")
        print("   1. Initialiser avec 'INIT' (ignore tout le contenu actuel)")
        print("   2. Laisser vide (annoncera tout le nouveau contenu)")
        print("   3. Passer (garder l'état actuel)")

        choice = input("   Votre choix (1/2/3): ").strip()

        if choice == "1":
            cursor.execute(
                "UPDATE youtube_channels SET lastVideoId = 'INIT', lastShortId = 'INIT' WHERE id = ?",
                (channel_db_id,),
            )
            print("   ✅ IDs initialisés à 'INIT'\n")
        elif choice == "2":
            cursor.execute(
                "UPDATE youtube_channels SET lastVideoId = NULL, lastShortId = NULL WHERE id = ?",
                (channel_db_id,),
            )
            print("   ✅ IDs laissés vides (annoncera le nouveau contenu)\n")
        else:
            print("   ⏭️  Passé\n")

    conn.commit()
    conn.close()

    print("✅ Configuration terminée!")
    print("\n💡 Remarque: Le quota YouTube API est dépassé actuellement.")
    print("   Il se réinitialise à minuit (heure du Pacifique).")
    print("   Le bot vérifie maintenant toutes les 30 minutes au lieu de 5.")
    print("   Les vérifications de live sont réduites à 1x/3 cycles (~90 min).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
