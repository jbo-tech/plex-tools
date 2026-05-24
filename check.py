"""Vérifie la connexion au serveur Plex et affiche un résumé."""

import requests
from config import load_credentials, plex_headers

base_url, token = load_credentials()
headers = plex_headers(token)

response = requests.get(f"{base_url}/", headers=headers)

if response.status_code != 200:
    print(f"Connexion échouée ({response.status_code}) : {response.text}")
    raise SystemExit(1)

server = response.json()["MediaContainer"]
print(f"Serveur : {server.get('friendlyName', '?')}")
print(f"Version : {server.get('version', '?')}")
print(f"Plateforme : {server.get('platform', '?')} ({server.get('platformVersion', '?')})")
print(f"URL : {base_url}")

libs = requests.get(f"{base_url}/library/sections", headers=headers)
if libs.status_code == 200:
    sections = libs.json()["MediaContainer"].get("Directory", [])
    print(f"\nBibliothèques : {len(sections)}")
    for s in sections:
        print(f"  - {s['title']} ({s['type']})")

pls = requests.get(f"{base_url}/playlists", headers=headers)
if pls.status_code == 200:
    playlists = pls.json()["MediaContainer"].get("Metadata", [])
    print(f"\nPlaylists : {len(playlists)}")
    for p in playlists:
        print(f"  - {p['title']} ({p.get('playlistType', '?')}, {p.get('leafCount', '?')} items)")
