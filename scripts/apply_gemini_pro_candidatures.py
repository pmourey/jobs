#!/usr/bin/env python3
"""Génération haut niveau (Gemini Pro) des lettres de motivation et CV personnalisés.

Titres de CV réalistes (adaptés à l'expérience réelle de Philippe Mourey sans copier servilement l'offre),
résumés percutants et lettres de motivation soignées de niveau professionnel en 3-4 paragraphes.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask_app import app, db
from Model import Job
from tools.cv_tools import (
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
logger = logging.getLogger("gemini_pro_candidatures")

# Définition des profils et lettres de motivation haute qualité (Gemini Pro)
CANDIDATURES_DATA = {
    712: {
        "company": "Experis France",
        "zipCode": "Mougins (06)",
        "cv_title": "Administrateur Systèmes Linux & Supervision Applicative",
        "cv_summary": (
            "Fort de plus de vingt ans d'expérience dans l'ingénierie logicielle et les infrastructures système, "
            "j'interviens sur le maintien en conditions opérationnelles, la surveillance temps réel et l'optimisation "
            "d'environnements Linux à forte criticité. Spécialiste de l'automatisation (Python, Bash) et du monitoring (Grafana, Nagios), "
            "je veille à la disponibilité continue des applications métiers et à la détection proactive des incidents."
        ),
        "highlighted_work_indices": [0, 1, 2, 3],
        "highlighted_skills": ["Linux", "Grafana", "Python", "Bash", "Supervision / Monitoring", "Gestion d'incidents"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "C’est avec un vif intérêt que je vous présente ma candidature au poste d’Administrateur supervision Linux "
            "au sein d'Experis France à Mougins. Fort d'une expérience de plus de vingt ans dans les domaines du développement "
            "logiciel, de la production et de la sécurité des systèmes d’information, je souhaite apporter mon expertise "
            "technique et ma rigueur au maintien en conditions opérationnelles de votre parc applicatif critique.\n\n"
            "Évoluer dans un environnement où la disponibilité permanente des services est primordiale correspond parfaitement "
            "à mon parcours. J'ai acquis une solide maîtrise de l'administration sous Linux ainsi que de l'outillage de surveillance "
            "et de métrologie. Capable de concevoir et d'optimiser des tableaux de bord pertinents avec Grafana, je sais définir "
            "les indicateurs clés de performance et isoler rapidement les causes racines d'incidents complexes pour prévenir "
            "les indisponibilités de service.\n\n"
            "Ma culture du scripting en Python et Bash me permet d'industrialiser les tâches récurrentes d'exploitation et de "
            "documenter méthodiquement chaque procédure, facilitant ainsi l’intégration continue de nouveaux services et la "
            "transmission des savoirs au sein de l'équipe.\n\n"
            "Reconnu pour mon esprit d'équipe, mon calme dans la gestion des alertes critiques et mon sens du service, je serais "
            "ravi d'échanger avec vous sur vos enjeux actuels lors d'un prochain entretien.\n\n"
            "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.\n\n"
            "Philippe Mourey"
        )
    },
    713: {
        "company": "UCANSS",
        "zipCode": "Valbonne Sophia-Antipolis (06)",
        "cv_title": "Technicien Supérieur d'Exploitation & Supervision Systèmes",
        "cv_summary": (
            "Professionnel de l'informatique combinant une solide expérience en administration systèmes et en développement logiciel, "
            "j'assure le pilotage opérationnel et la surveillance préventive des infrastructures complexes. Rompu aux environnements "
            "Linux/Windows, aux outils de supervision comme Nagios et aux bonnes pratiques ITIL, j'apporte réactivité, sens du service "
            "et rigueur pour garantir la continuité des services de la branche Famille."
        ),
        "highlighted_work_indices": [0, 1, 2, 4],
        "highlighted_skills": ["Supervision Nagios", "Linux", "Windows Server", "Virtualisation", "ITIL", "Diagnostic réseau"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "Je vous adresse ma candidature pour le poste de Technicien de supervision au sein de la Direction des Opérations "
            "de la DSI de la branche Famille à Sophia-Antipolis. Doté d'une expérience approfondie en administration des systèmes "
            "informatiques et en maintien opérationnel, je souhaite mettre ma réactivité et mon professionnalisme au service de la "
            "continuité de vos plateformes techniques.\n\n"
            "Habitué à monitorer des parcs hétérogènes sous Linux et Windows, j'utilise régulièrement les outils de supervision tels "
            "que Nagios pour qualifier et traiter les événements avant qu'ils n'impactent les utilisateurs finaux. Ma rigueur "
            "méthodologique, alignée sur les référentiels ITIL, me permet d'établir des diagnostics rapides, de participer aux "
            "analyses post-mortem et de contribuer activement à la documentation et à l'automatisation des procédures techniques.\n\n"
            "Parfaitement disponible pour travailler en horaires postés de 6h à 18h selon les plannings en deux shifts définis, "
            "j'apprécie le travail collaboratif en centre de supervision où la communication et le sens des priorités sont essentiels.\n\n"
            "Espérant avoir l’opportunité de vous détailler ma motivation de vive voix, je vous prie d'agréer, Madame, Monsieur, "
            "mes salutations respectueuses.\n\n"
            "Philippe Mourey"
        )
    },
    714: {
        "company": "CENTRE TECHNIQUE NATIONAL",
        "zipCode": "Cagnes-sur-Mer (06)",
        "cv_title": "Concepteur Développeur — Intégration Logicielle & Flux de Données",
        "cv_summary": (
            "Concepteur développeur expérimenté avec un riche parcours en ingénierie logicielle, modélisation de données et "
            "interfaçage d'architectures d'entreprise. Spécialisé dans la modernisation de systèmes d'information, le développement "
            "applicatif (Python, SQL, Delphi) et l'intégration de progiciels métiers, j'interviens avec rigueur depuis l'analyse des "
            "besoins jusqu'à la mise en production de solutions fiables et performantes."
        ),
        "highlighted_work_indices": [0, 1, 3, 5],
        "highlighted_skills": ["Conception logicielle", "Bases de données SQL", "Python", "Intégration d'API & Progiciels", "Synchronisation de données", "Méthodologie Agile"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "C’est avec beaucoup d'intérêt que je postule au rôle de Concepteur développeur au sein de votre DSI à Cagnes-sur-Mer, "
            "dans le cadre du projet stratégique STELLA de modernisation du SI Assurance de Personnes et d'intégration du progiciel CLEVA. "
            "Mon solide parcours en ingénierie logicielle et en gestion des données me permettra d'être immédiatement force de proposition "
            "au sein de la Direction de la Rénovation Informatique.\n\n"
            "Au cours de mes différentes réalisations professionnelles, j'ai conçu et déployé de multiples modules de traitement, "
            "de contrôle et d'enrichissement de données transactionnelles. Qu'il s'agisse de concevoir des mécanismes de synchronisation "
            "robustes, d'assurer la cohérence entre un référentiel central et des progiciels métiers, ou d'optimiser les requêtes SQL "
            "complexes, je veille toujours à livrer un code pérenne, testé et documenté.\n\n"
            "Habitué à collaborer étroitement avec les Product Owners et les équipes d'intégration, je partage votre engagement vers "
            "l'agilité et l'excellence technique. Je serais fier de contribuer à la réussite de la modernisation de vos outils au profit "
            "du Groupe PRO BTP.\n\n"
            "Je reste à votre entière disposition pour convenir d'une date d'entretien à votre convenance.\n\n"
            "Je vous prie d'agréer, Madame, Monsieur, l'expression de ma considération distinguée.\n\n"
            "Philippe Mourey"
        )
    },
    715: {
        "company": "Randstad professional",
        "zipCode": "Biot Sophia-Antipolis (06)",
        "cv_title": "Ingénieur Systèmes, Réseaux & Automatisation Linux",
        "cv_summary": (
            "Ingénieur système et infrastructure cumulant une expertise approfondie de l'écosystème Linux/BSD, de la virtualisation "
            "(Proxmox, VMware) et de l'automatisation logicielle (Python, Bash). Spécialiste de la gestion des accès, de la sécurisation "
            "multi-sites et de la conformité des données, j'assure avec autonomie le support technique, la supervision continue et "
            "l'évolution maîtrisée des parcs informatiques critiques."
        ),
        "highlighted_work_indices": [0, 1, 2, 4],
        "highlighted_skills": ["Linux / BSD (Debian, Ubuntu, pfSense)", "Virtualisation (Proxmox, VMware, Docker)", "Scripting Python / Bash", "Sécurité réseau & RGPD", "Support N1/N2", "Anglais technique"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "Je vous soumets ma candidature au poste d'Ingénieur Développement Systèmes et Réseaux Linux pour le compte de Randstad "
            "professional à Biot. Doté d'une expérience polyvalente de plus de vingt ans dans les infrastructures informatiques, la "
            "sécurité et l'automatisation, je réponds de manière ciblée aux responsabilités techniques et humaines de cette opportunité.\n\n"
            "Ma pratique quotidienne des systèmes Linux et BSD (Debian, Ubuntu, CentOS, pfSense) ainsi que des environnements de "
            "virtualisation (Proxmox, VMware) et de conteneurisation (Docker) me permet de piloter la supervision, la gestion des accès "
            "et le maintien opérationnel d'infrastructures multi-sites. Rompu au scripting en Python et Bash, j'automatise les sauvegardes, "
            "fiabilise la protection des données sensibles (dans le strict respect du RGPD) et optimise la réponse aux sollicitations "
            "des collaborateurs.\n\n"
            "Capable d'assurer un support technique de niveaux 1 et 2 avec pédagogie et réactivité, je formalise avec aisance l'ensemble "
            "des procédures et architectures techniques en anglais selon les standards professionnels requis.\n\n"
            "Dans l'attente d'une rencontre où nous pourrons évoquer concrètement les attentes de la mission, je vous prie de recevoir, "
            "Madame, Monsieur, l'expression de mes salutations distinguées.\n\n"
            "Philippe Mourey"
        )
    },
    716: {
        "company": "CALL TO ACTION",
        "zipCode": "Nice (06)",
        "cv_title": "Chargé d'Exploitation Applicative & Gestionnaire de Données SQL",
        "cv_summary": (
            "Spécialiste de la manipulation de données et de l'exploitation applicative, j'allie une maîtrise rigoureuse du langage "
            "SQL et de la programmation de scripts (Python, JavaScript) à une solide expérience en suivi de production. Précis, autonome "
            "et orienté résultats, j'assure l'intégration, le contrôle qualité des fichiers, le reporting statistique et l'optimisation "
            "des campagnes métiers au service de projets solidaires."
        ),
        "highlighted_work_indices": [0, 1, 3, 4],
        "highlighted_skills": ["Requêtes & Bases SQL", "Scripts Python & Automatisation", "Exploitation & Paramétrage applicatif", "Reporting & Contrôle qualité", "Gestion de fichiers volumineux", "Rigueur de production"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "C’est avec un enthousiasme particulier que je candidate au poste de Chargé d'exploitation de données et applications métiers "
            "au sein de CALL TO ACTION à Nice. Mettre mes compétences techniques au profit de campagnes d'envergure menées pour de grandes "
            "organisations solidaires telles que Médecins Sans Frontières ou Amnesty International donne un sens stimulant à mon engagement "
            "professionnel.\n\n"
            "Disposant d'une pratique avancée des bases de données relationnelles et du langage SQL, je prends en charge avec rigueur "
            "l'intégration, la fiabilisation et l'extraction de volumes de données hétérogènes. Mes compétences en programmation Python et "
            "JavaScript constituent un atout concret pour développer des scripts d'automatisation, fluidifier les flux de production "
            "récurrents et fiabiliser la génération des tableaux de bord statistiques.\n\n"
            "Pragmatique, rigoureux et autonome, j'apprends rapidement le fonctionnement de nouveaux progiciels métiers tels que Nixxis "
            "et j'ai à cœur de collaborer de façon constructive avec l'ensemble des équipes opérationnelles.\n\n"
            "Je serais très heureux d'échanger avec vous lors d'un entretien à Nice pour vous exprimer ma pleine motivation.\n\n"
            "Je vous prie d'agréer, Madame, Monsieur, mes salutations les plus chaleureuses.\n\n"
            "Philippe Mourey"
        )
    },
    717: {
        "company": "SITE CNAF SOPHIA-ANTIPOLIS DOLINES",
        "zipCode": "Valbonne Sophia-Antipolis (06)",
        "cv_title": "Technicien Référent Supervision & Exploitation des Systèmes",
        "cv_summary": (
            "Spécialiste du maintien en conditions opérationnelles et de la surveillance temps réel des systèmes informatiques, "
            "j'interviens sur la détection, la qualification et la résolution préventive des incidents d'exploitation. Expert des "
            "environnements Linux, des plateformes virtualisées et du monitoring Nagios, j'applique les bonnes pratiques ITIL pour sécuriser "
            "la continuité de service des architectures sensibles."
        ),
        "highlighted_work_indices": [0, 1, 2, 4],
        "highlighted_skills": ["Supervision Nagios", "Administration Linux & Windows", "Virtualisation & Réseaux", "Gestion d'incidents ITIL", "Rédaction de procédures", "Horaires décalés & Shifts"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "Je vous présente ma candidature au poste de Technicien de supervision au sein du site CNAF Sophia-Antipolis Dolines, rattaché "
            "à la Direction des Opérations de la DSI de la branche Famille. Fort d’un parcours éprouvé en exploitation de systèmes et d’infrastructures "
            "critiques, je souhaite apporter ma rigueur opérationnelle et ma réactivité au service de la continuité de vos applications.\n\n"
            "Familier des environnements mixtes Linux et Windows ainsi que des solutions de virtualisation, j'utilise les outils de supervision "
            "(Nagios) pour analyser en temps réel les alertes et neutraliser les dysfonctionnements avant toute indisponibilité majeure. Ma démarche "
            "méthodique s'appuie sur le respect des standards ITIL, la clarté du reporting et la rédaction scrupuleuse des procédures d'exploitation.\n\n"
            "Motivé par la dynamique d'équipe propre au centre de supervision et parfaitement disponible pour le rythme en shifts de 6h à 18h, "
            "je suis prêt à m’investir pleinement dans vos missions et à faire évoluer mes compétences au sein de votre DSI.\n\n"
            "Je me tiens à votre disposition pour vous exposer de vive voix mon parcours lors d'un entretien.\n\n"
            "Veuillez agréer, Madame, Monsieur, l’expression de mes salutations distinguées.\n\n"
            "Philippe Mourey"
        )
    },
    718: {
        "company": "Experis France",
        "zipCode": "Mougins (06)",
        "cv_title": "Administrateur Systèmes Linux Senior — Infrastructures & Production",
        "cv_summary": (
            "Ingénieur système Linux senior fort de plus de vingt ans d'expérience dans l'exploitation, l'automatisation et l'industrialisation "
            "d'infrastructures de production à haute criticité. Spécialiste des environnements DATA et des bases de données volumineuses, "
            "j'assure le support expert N2/N3, l'automatisation via Ansible et le pilotage des migrations de plateformes avec une exigence "
            "constante de résilience et de sécurité."
        ),
        "highlighted_work_indices": [0, 1, 2, 3],
        "highlighted_skills": ["Linux RedHat / Debian / CentOS", "Infrastructures DATA volumineuses", "Automatisation Ansible & Scripts", "Support expert N2 / N3", "Migrations & Maintien opérationnel", "Gestion de crise & Astreintes"],
        "cover_letter": (
            "Madame, Monsieur,\n\n"
            "C’est avec un vif intérêt que je candidate au poste d’Administrateur Système Linux Senior au sein d'Experis France à Mougins, "
            "afin de renforcer vos équipes d’infrastructures DATA sur des environnements de production à haute criticité. Avec plus de vingt "
            "ans d'expérience en ingénierie informatique, systèmes Linux et production logicielle, je dispose de la maturité et des compétences "
            "techniques requises pour ce rôle clé.\n\n"
            "Tout au long de ma carrière, j’ai assuré l’administration avancée, la sécurisation et la maintenance d’infrastructures supportant "
            "des charges élevées et des bases de données à forte volumétrie. Rompu au support expert de niveaux 2 et 3, je sais résoudre rapidement "
            "des incidents complexes tout en pilotant l'industrialisation des pratiques grâce à des outils d'automatisation tels qu'Ansible "
            "et des scripts adaptés.\n\n"
            "Habitué aux contraintes de continuité d'activité, aux migrations de datacenters planifiées et aux rotations d'astreinte hors "
            "heures ouvrées, je veille scrupuleusement à la qualité documentaire et à la robustesse des déploiements.\n\n"
            "Dans l'attente d'un échange constructif sur les défis techniques de vos clients partenaires, je vous prie d'agréer, Madame, "
            "Monsieur, mes salutations distinguées.\n\n"
            "Philippe Mourey"
        )
    },
}

def run():
    with app.app_context():
        template_path = resolve_cover_letter_template_path(app.static_folder)
        cv_data_base = load_cv_data(app.static_folder)
        user_gen_dir = Path(app.static_folder) / "uploads" / "users" / "1" / "generated"
        user_gen_dir.mkdir(parents=True, exist_ok=True)

        for job_id, data in CANDIDATURES_DATA.items():
            job = Job.query.get(job_id)
            if not job:
                logger.warning(f"Offre #{job_id} introuvable en BDD.")
                continue

            logger.info("=" * 60)
            logger.info(f"Mise à niveau Haute Qualité pour #{job.id} : {job.name}")

            # 1. Mise à jour des métadonnées du Job
            job.company = data["company"]
            job.zipCode = data["zipCode"]
            job.cover_letter_text = data["cover_letter"]
            db.session.commit()
            logger.info(f"Base de données mise à jour : {job.company} - {job.zipCode} - LM ({len(data['cover_letter'])} car.)")

            # 2. Génération PDF de la Lettre de motivation
            lm_pdf_bytes = generate_cover_letter_pdf_bytes(
                job=job,
                template_path=template_path,
                letter_date=job.applicationDate or datetime.now(),
            )
            lm_pdf_filename = build_cover_letter_pdf_filename(job)
            lm_pdf_safe_name = sanitize_filename_part(Path(lm_pdf_filename).stem) + ".pdf"
            (user_gen_dir / lm_pdf_safe_name).write_bytes(lm_pdf_bytes)
            logger.info(f"PDF Lettre de motivation régénéré : {lm_pdf_safe_name}")

            # 3. Préparation des suggestions CV réalistes
            cv_suggestions = {
                "cv_title": data["cv_title"],
                "summary": data["cv_summary"],
                "highlighted_work_indices": data["highlighted_work_indices"],
                "highlighted_skill_names": data["highlighted_skills"],
                "source": "gemini-pro-tailored",
            }

            # 4. Génération PDF du CV sur-mesure
            cv_pdf_bytes = generate_tailored_cv_pdf_bytes(
                job=job,
                cv_data=cv_data_base,
                suggestions=cv_suggestions,
            )
            pretty_cv_name = build_cv_pdf_filename(job)
            cv_safe_name = sanitize_filename_part(Path(pretty_cv_name).stem) + ".pdf"
            (user_gen_dir / cv_safe_name).write_bytes(cv_pdf_bytes)
            logger.info(f"PDF CV sur-mesure régénéré : {cv_safe_name} (Titre : {data['cv_title']})")

        logger.info("=" * 60)
        logger.info("Régénération Gemini Pro terminée avec succès pour les 7 offres.")

if __name__ == "__main__":
    run()
