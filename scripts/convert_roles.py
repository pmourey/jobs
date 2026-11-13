#!/usr/bin/env python3
"""Petit script de migration local pour normaliser les valeurs de role.

Objectifs:
- convertir les comptes ayant role=2 en role=1 (traiter les anciennes valeurs "Lecteur"/"is_reader" éventuelles)
- convertir les comptes "Editeur" si codés différemment en Utilisateur (USER=1)

Usage:
    python scripts/convert_roles.py

Le script crée une copie de sauvegarde de la base avant modification.
"""
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'instance' / 'jobs.sqlite3'


def backup(db_path: Path) -> Path:
    bak = db_path.with_suffix('.sqlite3.bak')
    shutil.copy2(db_path, bak)
    return bak


def run():
    if not DB_PATH.exists():
        print(f"Base introuvable: {DB_PATH}")
        return

    print(f"Fichier DB: {DB_PATH}")
    bak = backup(DB_PATH)
    print(f"Sauvegarde créée: {bak}")

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Montrer la distribution actuelle des roles
    cur.execute('SELECT role, COUNT(*) FROM user GROUP BY role')
    rows = cur.fetchall()
    print('Distribution des rôles avant migration:')
    for r, c in rows:
        print(f'  role={r} -> {c} comptes')

    # Conversion demandée: role=2 -> role=1
    cur.execute('UPDATE user SET role = 1 WHERE role = 2')
    updated = conn.total_changes
    conn.commit()

    cur.execute('SELECT role, COUNT(*) FROM user GROUP BY role')
    rows_after = cur.fetchall()
    print('\nDistribution des rôles après migration:')
    for r, c in rows_after:
        print(f'  role={r} -> {c} comptes')

    print(f"Nombre total de modifications appliquées (conn.total_changes): {updated}")
    conn.close()


if __name__ == '__main__':
    run()

