# ROADMAP - Corrections & optimisations ISROBOT

Liste des problèmes relevés lors de la revue de code, par priorité.
Cocher au fur et à mesure que les corrections sont appliquées.

## 🔴 Bugs critiques

- [x] `corners` fantôme : `commands/xp_system.py:89`, `commands/xp_voice.py:88` insèrent `corners` alors que la colonne est supprimée par la migration (`db_migrations.remove_corners_column`, appelée `main.py:254`). Les nouveaux utilisateurs ne gagnent aucun XP. À retirer aussi de `database.py:78`.
- [x] Mutes manuels supprimés par erreur quand les warns atteignent 0 (`commands/moderation.py` ~263-267 et `main.py:928-943`). Distinguer mutes auto (warns) et manuels. → colonne `is_auto` ajoutée.
- [x] Décroissance des warns : `utils/moderation_utils.py:116` remettait `updated_at = now()` (timer glissant) alors que `MODERATION.md` dit « seul le plus ancien décroît ». → `updated_at` suit désormais l'ancienneté du plus ancien warn actif : `increment_warning` ne réarme plus le timer quand des warns existent déjà, et `decrement_warning` recale sur le 2e plus ancien (via `warning_history`). Testé.
- [x] Exploit économique `/capture` : `minigame_engine.py:109-112` → espérance positive dès odds > ~0,38. → plafond de payout avec marge maison (`CAPTURE_HOUSE_EDGE`), EV négative.
- [x] `/trade accept` non atomique → double escrow (`trades.py:267-347`). Idem `cancel_trade` (`trades.py:503`), `complete_trade`, stock shop (`shop.py:125-178`), `use_item` (`shop.py:286-305`). → transitions `UPDATE ... WHERE status='pending'` + `rowcount`, débit après transition ; helpers `db_helpers` ne `commit()` plus que s'ils possèdent la connexion (`should_close`). Testé (rollback conserve le stock).
- [x] Quêtes jamais complétées : `quests.increment_quest_progress` jamais appelé en production. → câblé sur `messages_sent` (`main.py on_message`, hors salons d'exception), `counting_participation` (`main.py`, compteur validé), `coinflip_used` (`commands/coinflip.py`), `capture_attempt` + `coins_won_capture` (`commands/minigame.py capture`), `duel_challenge` (`duel`), `coins_spent` (`shop_buy`). Multiplicateur de streak (`quests.py:525`) toujours non appliqué aux récompenses (laissé tel quel).
- [x] Quêtes `type = 'random'` (capture/duel/shop) jamais assignées : `assign_daily_quests` (`quests.py:138`) n'appelait que `get_available_quests("daily")`. → les bonus « random » (jusqu'à 2, 50 % chacun) sont tirés de `get_available_quests("random")`, uniquement si l'utilisateur n'a pas déjà une quête random active. Testé.
- [x] Objets de boutique inutiles : `shop.use_item` (`shop.py:251`) jamais appelé. → commande `/use <item_id>` ajoutée (`commands/minigame.py`), import `use_item`. Testé (effet appliqué, double-usage bloqué).
- [x] `commands/stream.py:130` : `.get()` sur `sqlite3.Row` → `AttributeError`. → code mort supprimé (`check_streams`, `StartStreamCheckInterval`).
- [x] `commands/moderation_context.py:72-82` : `Select` dans un Modal ignoré par discord.py 2.x. → remplacé par un champ `TextInput` « Raison » (obligatoire) + notes optionnelles.
- [x] `commands/minigame.py:740` : `max(... r.get("new_level", 0))` → `TypeError` si valeur `None`.
- [x] `commands/minigame.py` : imports fantômes `get_trade_offers_for_user` et `release_trade` (inexistants dans `trades.py`) → `ImportError` au chargement, tout le cog minigame ne se chargeait pas. Retirés (non utilisés).

## 🟠 Incohérences

- [x] README Python 3.8+ vs `commands/youtube.py:25` `tuple[bool, str]` (≥3.9). → README « Python 3.9+ ».
- [x] README YouTube « 5 min » + « live » vs code 600 s (`main.py:888`) et live retiré. → README « 10 minutes », live retiré.
- [x] README FFmpeg « requis pour la musique » : aucun module musique. → étape FFmpeg retirée du setup.
- [x] Filtres `/history` (`trades`, `captures`, `duels`) ne correspondent à aucun `kind` réel en base. → `get_user_transactions` (`db_helpers.py`) matche désormais par préfixe (`kind LIKE ? || '%'`). Testé.
- [x] Résolution du chemin DB divergente : `database.py:17-23` vs `xp_system.py:37`, `xp_voice.py`, `count.py`, `init_youtube_ids.py:17`. → tous passent par `database.DB_PATH` / `database.get_db_connection()` ; variable morte `main.py:151` retirée.
- [x] `commands/ping_bot.py:10` : pas de `@app_commands.guilds(...)`. → décorateur ajouté (cohérent avec les autres commandes).
- [x] `commands/reload.py:34-40` ne synchronise pas les commandes globales. → sync globale + guilde, comme au démarrage (`main.py`).
- [x] Définitions de niveau XP dupliquées : `xp_system.py:24`, `xp_voice.py:22`, `db_helpers.py:18`. → module partagé `utils/xp.py` ; `db_helpers` réexporte pour compatibilité.
- [x] `commands/count.py:39-45` valide `DB_PATH` avec une sémantique différente. → utilise `database.DB_PATH`.
- [x] `moderation.py:57` stocke la raison échappée en base mais affiche l'originale. → raison brute stockée ; échappement au moment de l'affichage (`create_warning_embed`/`create_mute_embed`, `warns`, `modlog`).

## 🟡 Optimisations

- [x] Appels SQLite bloquants dans du code async : `xp_system.py`, `xp_voice.py:185`, `youtube.py`, `stream.py`, `count.py`, `ai_moderation.py`. → `asyncio.to_thread` sur les appels bloquants (open/query/commit/close dans le thread).
- [x] Sessions HTTP dupliquées : `youtube.py:99` (réutiliser `bot.session`, `main.py:234`). → contexte `_http_session(bot)`.
- [x] N+1 API YouTube : `youtube.py:148-171` (`videos.list` multi-IDs). → `get_video_details_batch`.
- [x] Token OAuth Twitch non mis en cache : `stream.py:320`. → cache classe `GetTwitchOAuth._cached_token` (marge 60 s).
- [x] Dictionnaires non bornés / fuites mémoire : `xp_system.py:30`, `commands/minigame.py:917-983`, `main.py:214`. → purge opportuniste des entrées expirées (cooldowns, confirmations XP, locks non verrouillés).
- [x] `datetime.utcnow()` déprécié (3.12) : `db_helpers.py`, `trades.py`, `shop.py`, `quests.py`, `commands/minigame.py:914`. → `utils/time_utils.utcnow()`.
- [x] `trades.py:399` : `.seconds` au lieu de `.total_seconds()` (corrigé dans `complete_trade`, avec garde `escrow_release_at` vide).
- [x] `commands/ai.py:190` : `asyncio.get_event_loop()` déprécié. → `get_running_loop()`.
- [x] Code mort/dupliqué : `stream.py:118,285-304`, `import re` inutile `youtube.py:553`, embed dupliqué `minigame.py:936-983`, stats dupliquées `minigame_engine.py`. → `_build_xp_warning_embed`, `_get_game_stats` partagé (1 requête au lieu de 4).
- [x] Valeurs codées en dur (odds, mises, taxes, durées, seuils XP, limite IA) à externaliser. → constantes nommées (`CAPTURE_*`, `DUEL_*`) ; limites IA via env (`AI_MAX_*`) ; taxes déjà dans `settings`.
- [x] Chemins : `reload.py:47` et `main.py:264` utilisent `os.getcwd()`. → chemins basés sur `__file__`/`_SCRIPT_DIR`.
- [x] Erreurs silencieuses : `youtube.py:348-378`, `shop.py:375`, `ai.py:179`. → logs de niveau warning/debug ajoutés (`json.JSONDecodeError`, fallbacks YouTube).
- [x] Blocklist IA par mots-clés contournable (`ai.py:24-66`). → normalisation (accents NFKD, leetspeak, caractères invisibles) + motifs tolérant répétitions et séparateurs de ponctuation.

## 🔵 Tests / hygiène

- [x] Pas de CI ni lint appliqué malgré `pyproject.toml` (black/isort configurés ; `target-version` passé à `py39`). → workflow `.github/workflows/ci.yml` (black `--check`, isort `--check-only`, pytest) ; codebase reformatée via `isort .` + `black .` (29 fichiers) ; tests/imports/cogs revérifiés.
- [x] `init_youtube_ids.py:15` : `exit(1)` au lieu de `sys.exit(1)` ; pas de garde `__main__`. → code encapsulé dans `main()`, `sys.exit(main())` sous `if __name__ == "__main__"`.
- [x] `requirements.txt` non épinglé. → versions exactes (`discord.py==2.7.1`, `python-dotenv==1.2.4`, `aiohttp==3.14.5`, `PyNaCl==1.6.2`, `ollama==0.6.3`), installées et validées.

## 🟢 Dette technique / qualité

- [x] Vérifier les doublons de fonctionnalité et de code à travers le projet (helpers/interactions dupliqués, logiques de jeu recopiées, formats d'embed récurrents, requêtes SQL similaires) et factoriser ce qui peut l'être. → `apply_mute` factorisé dans `utils/moderation_utils.py` ; autres candidats évalués et écartés (`_parse_bool_env`, `check_cooldown`, wrappers `get_db_connection`).

## 🟢 Internationalisation (i18n)

- [x] Vérifier qu'il ne reste aucun texte codé en dur (embeds, messages d'erreur/confirmation, contenus des commandes, paramètres) et que tout passe par des variables/constantes de traduction, afin de permettre au bot de fonctionner dans plusieurs langues. → système `utils/i18n.py` (`t`, `get_locale`, `tr`, `JsonTranslator`) + `locales/fr.json` / `locales/en.json` (570 clés chacune, parité fr/en) ; translator branché dans `main.py` (détection via `interaction.locale`). Toutes les commandes et helpers convertis : descriptions/paramètres via `tr()`, textes via `t()`, views/modals localisés, `utils/error_handlers.py` (`errors.*`), `utils/security.py` (rate-limit/cooldown), libellés de fonctionnalités (`feature.*`) dans `reload.py`/`feature_toggles.py`. Locale par défaut `fr` pour les événements sans interaction (level-up DM, expiration warn/mute, jeu du compteur, présence, décay).

## 🟢 Nouvelles fonctionnalités

- [x] Ajouter la récupération des posts Bluesky d'un compte et leur affichage/annonce dans un salon, sur le même modèle que les intégrations Twitch (`commands/stream.py`) et YouTube (`commands/youtube.py`). → cog `commands/bluesky.py` (API publique `public.api.bsky.app` : `app.bsky.actor.getProfile` + `app.bsky.feed.getAuthorFeed`, sans clé) ; commandes `/bluesky_add`, `/bluesky_remove`, `/bluesky_list` ; table `bluesky_accounts` (+ migration colonnes) ; boucle `check_bluesky_loop` dans `main.py` (toutes les 5 min, ignore les reposts, annonce dans l'ordre chronologique, initialise le dernier post à l'ajout, marqueur avancé post par post pour réessayer les envois échoués sans doublon) ; toggle `bluesky` (`COG_BLUESKY_ENABLED`) ; textes i18n `bluesky.*`.
- [x] Permettre aux fonctionnalités IA (`commands/ai.py`, `utils/ai_moderation.py`) de fonctionner avec des providers externes en plus d'Ollama, par exemple OpenRouter (configuration du provider, clés API, sélection du modèle). → couche d'abstraction `utils/ai_provider.py` (`chat`, `get_provider`, `get_active_model` + exceptions `AIProvider*`) ; provider sélectionné via `AI_PROVIDER` (`ollama` par défaut ou `openai` pour toute API compatible OpenAI : OpenRouter/OpenAI/Mistral via `openai_base_url`, `openai_api_key`, `openai_model`) ; `commands/ai.py` et `utils/ai_moderation.py` utilisent l'abstraction (transport `aiohttp` unifié, dépendance `ollama` retirée) ; clé `ai.config_error` (fr/en) ; tests `tests/test_ai_provider.py`.
