#!/usr/bin/env python3
"""Script pour générer les lettres de motivation et CV personnalisés pour les offres de novembre 2026."""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask_app import app, db
from Model import Job, FtSearch, User
from tools.cv_tools import (
    get_ai_cover_letter_text,
    get_ai_cv_suggestions,
    generate_tailored_cv_pdf_bytes,
    load_cv_data,
    build_cv_pdf_filename,
)
from tools.document_tools import (
    generate_cover_letter_pdf_bytes,
    resolve_cover_letter_template_path,
    build_cover_letter_pdf_filename,
    sanitize_filename_part,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("november_candidatures")

def run():
    # Use llama3.2:3b for speed and quality
    app.config['GITHUB_MODELS_MODEL'] = 'llama3.2:3b'

    with app.app_context():
        # Identify November 2026 jobs
        jobs = Job.query.filter(Job.id >= 712, Job.id <= 718).order_by(Job.id.asc()).all()
        logger.info(f"Trouvé {len(jobs)} offres ajoutées en novembre 2026 (IDs {[j.id for j in jobs]})")

        # Load FtSearch cache
        searches = FtSearch.query.order_by(FtSearch.id.desc()).all()
        ft_offers_by_id = {}
        for s in searches:
            for off in (s.offers or []):
                oid = str(off.get('id', ''))
                if oid and oid not in ft_offers_by_id:
                    ft_offers_by_id[oid] = off

        # Company / Location corrections based on FT descriptions
        enrichments = {
            712: {"company": "Experis France", "zipCode": "Mougins (06)"},
            713: {"company": "UCANSS", "zipCode": "Valbonne Sophia-Antipolis (06)"},
            714: {"company": "CENTRE TECHNIQUE NATIONAL", "zipCode": "Cagnes-sur-Mer (06)"},
            715: {"company": "Randstad professional", "zipCode": "Biot Sophia-Antipolis (06)"},
            716: {"company": "CALL TO ACTION", "zipCode": "Nice (06)"},
            717: {"company": "SITE CNAF SOPHIA-ANTIPOLIS DOLINES", "zipCode": "Valbonne Sophia-Antipolis (06)"},
            718: {"company": "Experis France", "zipCode": "Mougins (06)"},
        }

        template_path = resolve_cover_letter_template_path(app.static_folder)
        results = []

        for job in jobs:
            logger.info("=" * 60)
            logger.info(f"Traitement Offre #{job.id} : {job.name} (FT: {job.ft_offer_id})")

            # Apply enrichment
            if job.id in enrichments:
                enr = enrichments[job.id]
                if not job.company or job.company.strip() == "":
                    job.company = enr["company"]
                if job.zipCode in ("06", "", None):
                    job.zipCode = enr["zipCode"]
                db.session.commit()

            # Retrieve FT description if available
            ft_info = ft_offers_by_id.get(str(job.ft_offer_id))
            ft_desc = ""
            if ft_info and ft_info.get("description"):
                ft_desc = ft_info["description"]
                logger.info(f"Description FT trouvée ({len(ft_desc)} caractères)")

            # Resolve candidate CV data for job user
            user_cvs_meta = Path(app.static_folder) / "uploads" / "users" / str(job.user_id) / "cvs" / "cvs_meta.json"
            cv_data = None
            if user_cvs_meta.exists():
                import json
                try:
                    meta = json.loads(user_cvs_meta.read_text(encoding="utf-8"))
                    def_cv = meta.get("_default")
                    if def_cv:
                        target = Path(app.static_folder) / "uploads" / "users" / str(job.user_id) / "cvs" / def_cv
                        if target.exists():
                            cv_data = json.loads(target.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"Impossible de lire le CV utilisateur spécifique : {e}")
            if not cv_data:
                cv_data = load_cv_data(app.static_folder)

            # Concise targeted prompt hint
            prompt_hint = f"Poste : {job.name} chez {job.company} à {job.zipCode}."
            if ft_desc:
                # pass first 600 chars of key requirements
                prompt_hint += f"\nMissions clés de l'offre :\n{ft_desc[:600]}"

            # 1. Génération de la lettre de motivation (LM)
            logger.info(f"Génération de la lettre de motivation pour #{job.id}...")
            try:
                lm_text = get_ai_cover_letter_text(
                    job=job,
                    github_token="ollama-local",
                    additional_prompt=prompt_hint,
                    cv_data=cv_data,
                )
                job.cover_letter_text = lm_text
                db.session.commit()
                logger.info(f"Lettre générée et enregistrée en BDD ({len(lm_text)} car.)")
            except Exception as e:
                logger.error(f"Erreur lors de la génération de la LM : {e}")
                if not job.cover_letter_text:
                    job.cover_letter_text = (
                        f"Madame, Monsieur,\n\n"
                        f"Je vous adresse ma candidature pour le poste de {job.name} au sein de {job.company}.\n\n"
                        f"Fort d'une solide expérience dans les domaines du développement logiciel, de la production et de l'administration système Linux, "
                        f"je souhaite mettre mes compétences techniques et mon adaptabilité au service de vos équipes.\n\n"
                        f"Je reste à votre entière disposition pour tout entretien à votre convenance.\n\n"
                        f"Cordialement,\nPhilippe Mourey"
                    )
                    db.session.commit()

            # 2. Génération du PDF de la lettre de motivation
            owner_id = job.user_id
            user_gen_dir = Path(app.static_folder) / "uploads" / "users" / str(owner_id) / "generated"
            user_gen_dir.mkdir(parents=True, exist_ok=True)

            lm_pdf_safe_name = None
            try:
                lm_pdf_bytes = generate_cover_letter_pdf_bytes(
                    job=job,
                    template_path=template_path,
                    letter_date=job.applicationDate or datetime.now(),
                )
                lm_pdf_filename = build_cover_letter_pdf_filename(job)
                lm_pdf_safe_name = sanitize_filename_part(Path(lm_pdf_filename).stem) + ".pdf"
                lm_pdf_path = user_gen_dir / lm_pdf_safe_name
                lm_pdf_path.write_bytes(lm_pdf_bytes)
                logger.info(f"PDF Lettre de motivation généré : {lm_pdf_path.name} ({len(lm_pdf_bytes)} octets)")
            except Exception as e:
                logger.error(f"Erreur génération PDF LM : {e}")

            # 3. Génération des suggestions et du CV personnalisé
            logger.info(f"Génération des suggestions CV pour #{job.id}...")
            try:
                suggestions = get_ai_cv_suggestions(
                    job=job,
                    cv_data=cv_data,
                    github_token="ollama-local",
                    additional_prompt=f"Cible : {job.name} chez {job.company}",
                )
                logger.info(f"Titre CV suggéré : {suggestions.get('cv_title')}")
            except Exception as e:
                logger.error(f"Erreur suggestions CV : {e}")
                suggestions = {
                    "cv_title": job.name or "Consultant IT / Administrateur Système",
                    "summary": cv_data.get("basics", {}).get("summary", ""),
                    "highlighted_work_indices": list(range(min(4, len(cv_data.get("work", []))))),
                    "highlighted_skill_names": [s["name"] for s in cv_data.get("skills", [])[:6]],
                    "source": "fallback",
                }

            # 4. Génération du PDF du CV personnalisé
            cv_safe_name = None
            try:
                cv_pdf_bytes = generate_tailored_cv_pdf_bytes(
                    job=job,
                    cv_data=cv_data,
                    suggestions=suggestions,
                )
                pretty_cv_name = build_cv_pdf_filename(job)
                cv_safe_name = sanitize_filename_part(Path(pretty_cv_name).stem) + ".pdf"
                cv_pdf_path = user_gen_dir / cv_safe_name
                cv_pdf_path.write_bytes(cv_pdf_bytes)
                logger.info(f"PDF CV généré : {cv_pdf_path.name} ({len(cv_pdf_bytes)} octets)")
            except Exception as e:
                logger.error(f"Erreur génération PDF CV : {e}")

            results.append({
                "job_id": job.id,
                "name": job.name,
                "company": job.company,
                "city": job.zipCode,
                "cv_title": suggestions.get("cv_title"),
                "cv_summary": suggestions.get("summary"),
                "highlighted_skills": suggestions.get("highlighted_skill_names"),
                "lm_preview": (job.cover_letter_text or "")[:250].replace("\n", " "),
                "cv_filename": cv_safe_name,
                "lm_filename": lm_pdf_safe_name,
            })

        logger.info("=" * 60)
        logger.info(f"Traitement terminé avec succès pour les {len(results)} offres.")
        return results

if __name__ == "__main__":
    run()
