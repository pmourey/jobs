import csv
import requests
from time import sleep

# ============================================================================
# CONFIGURATION
# ============================================================================

CLIENT_ID = "PAR_suividecandidatures_811d4b1274dedae374e02b16a464f05b72dfa4efd8c4adc20bbed5d448b5d386"
CLIENT_SECRET = "81bcec2e844f39e30941db484ff8ed6d3cdfbb46f8b30057a9cf196b05d95f2d"

# MOTS_CLES = "sécurité informatique"
MOTS_CLES = ""
DEPARTEMENT = "06"
TYPE_CONTRAT = ""

OUTPUT_CSV = f"offres_france_travail_{MOTS_CLES}_{DEPARTEMENT}_{TYPE_CONTRAT}.csv"

# ============================================================================
# AUTHENTIFICATION
# ============================================================================

def get_access_token():
    url = (
        "https://entreprise.francetravail.fr/"
        "connexion/oauth2/access_token?realm=/partenaire"
    )

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
		"scope": "api_offresdemploiv2 o2dsoffre"
    }


    response = requests.post(url, data=payload)
    response.raise_for_status()

    return response.json()["access_token"]


# ============================================================================
# RECHERCHE DES OFFRES
# ============================================================================

def search_offers(token, start=0, end=149):
    url = (
        "https://api.francetravail.io/"
        "partenaire/offresdemploi/v2/offres/search"
    )

    headers = {
        "Authorization": f"Bearer {token}"
    }

    params = {
        "motsCles": MOTS_CLES,
        "departement": DEPARTEMENT,
        "typeContrat": TYPE_CONTRAT,
        "range": f"{start}-{end}"
    }

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"Erreur lors de la requête : {e}")
        return response.json()

    return response.json()


# ============================================================================
# EXTRACTION DES CHAMPS
# ============================================================================

def extract_offer(offer):
    entreprise = offer.get("entreprise", {})

    return {
        "id": offer.get("id"),
        "intitule": offer.get("intitule"),
        "entreprise": entreprise.get("nom"),
        "ville": offer.get("lieuTravail", {}).get("libelle"),
        "contrat": offer.get("typeContrat"),
        "experience": offer.get("experienceLibelle"),
        "date_creation": offer.get("dateCreation"),
        "date_actualisation": offer.get("dateActualisation"),
        "description": (
            offer.get("description", "")
            .replace("\n", " ")
            .replace("\r", " ")
        ),
        "url": offer.get("origineOffre", {}).get("urlOrigine")
    }


# ============================================================================
# PAGINATION
# ============================================================================

def get_all_offers(token):
    all_offers = []

    page_size = 150
    start = 0

    while True:
        end = start + page_size - 1

        print(f"Récupération {start}-{end}")

        data = search_offers(token, start, end)

        offers = data.get("resultats", [])

        if not offers:
            break

        for offer in offers:
            all_offers.append(extract_offer(offer))

        if len(offers) < page_size:
            break

        start += page_size

        sleep(0.2)

    return all_offers


# ============================================================================
# EXPORT CSV
# ============================================================================

def export_csv(offers, filename):
    if not offers:
        print("Aucune offre trouvée.")
        return

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=offers[0].keys()
        )

        writer.writeheader()
        writer.writerows(offers)

    print(f"{len(offers)} offres exportées vers {filename}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("Authentification...")
    token = get_access_token()

    print("Recherche des offres...")
    offers = get_all_offers(token)

    print(f"{len(offers)} offres trouvées")

    export_csv(offers, OUTPUT_CSV)


if __name__ == "__main__":
    main()