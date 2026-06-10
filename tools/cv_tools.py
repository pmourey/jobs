"""
Outils de génération de CV personnalisé via l'API GitHub Models (IA) et ReportLab.
"""
from __future__ import annotations

import json as _json
import re
from io import BytesIO
from pathlib import Path

from Model import Job


def build_cv_pdf_filename(job: Job) -> str:
    from tools.document_tools import sanitize_filename_part
    company = sanitize_filename_part(job.company)
    title = sanitize_filename_part(job.name)
    return f'CV Philippe Mourey - {company} - {title}.pdf'


def load_cv_data(static_folder) -> dict:
    """Charge cv.json depuis le dossier static."""
    cv_path = Path(static_folder) / 'cv.json'
    if not cv_path.exists():
        raise FileNotFoundError(f'cv.json introuvable : {cv_path}')
    with open(cv_path, 'r', encoding='utf-8') as f:
        return _json.load(f)


def _default_cv_suggestions(cv_data: dict) -> dict:
    skills = cv_data.get('skills', [])
    return {
        'cv_title': cv_data.get('basics', {}).get('label', 'Développeur / Consultant IT'),
        'summary': cv_data.get('basics', {}).get('summary', ''),
        'highlighted_work_indices': list(range(min(4, len(cv_data.get('work', []))))),
        'highlighted_skill_names': [s['name'] for s in skills[:6]],
        'warning': "Aperçu généré sans IA à cause d'une indisponibilité réseau/API.",
        'source': 'fallback',
    }


# Sections optionnelles disponibles pour le mode avancé
ADVANCED_SECTIONS = {
    'education':      'Formations',
    'certificates':   'Certifications',
    'skills_rating':  'Compétences avec niveau/rating',
    'references':     'Références professionnelles',
    'github_projects': 'Projets GitHub personnels',
}


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc)
    if '429' in text or 'Too Many Requests' in text:
        return True
    response = getattr(exc, 'response', None)
    if response is not None and getattr(response, 'status_code', None) == 429:
        return True
    return getattr(exc, 'status_code', None) == 429


def _build_optional_sections_text(cv_data: dict, include_sections: list,
                                   selected_education: list | None = None,
                                   selected_certificates: list | None = None,
                                   selected_skills: list | None = None,
                                   selected_references: list | None = None,
                                   selected_projects: list | None = None) -> str:
    """Construit le texte des sections optionnelles à injecter dans le prompt IA."""
    has_any = (include_sections or selected_education is not None or selected_certificates is not None
               or selected_skills is not None or selected_references is not None
               or selected_projects is not None)
    if not has_any:
        return ''
    parts = []

    # Formations : filtrées par sélection individuelle si fournie
    if 'education' in include_sections or selected_education is not None:
        education = cv_data.get('education', [])
        if selected_education is not None:
            education = [e for i, e in enumerate(education) if i in selected_education]
        if education:
            lines = []
            for e in education:
                tp = ' - '.join(p for p in [e.get('studyType', ''), e.get('area', '')] if p)
                inst = e.get('institution', '')
                ey = (e.get('endDate') or '')[:4]
                label = tp or inst
                suffix = f' ({inst}, {ey})' if (tp and inst) else (f' ({ey})' if ey else '')
                lines.append(f'  - {label}{suffix}')
            parts.append('Formations :\n' + '\n'.join(lines))

    # Certifications : filtrées par sélection individuelle si fournie
    if 'certificates' in include_sections or selected_certificates is not None:
        certs = cv_data.get('certificates', [])
        if selected_certificates is not None:
            certs = [c for c in certs if c['name'] in selected_certificates]
        if certs:
            lines = [
                f"  - {c['name']} ({c.get('issuer', '')}, {(c.get('date') or '')[:4]})"
                for c in certs
            ]
            parts.append('Certifications :\n' + '\n'.join(lines))

    # Compétences avec niveau, filtrées si sélection individuelle
    if 'skills_rating' in include_sections or selected_skills is not None:
        skills = cv_data.get('skills', [])
        if selected_skills is not None:
            skills = [s for s in skills if s['name'] in selected_skills]
        if skills:
            rating_label = {1: 'Débutant', 2: 'Intermédiaire', 3: 'Avancé', 4: 'Expert'}
            lines = [
                f"  - {s['name']} : {rating_label.get(s.get('rating', 0), s.get('level', 'N/A'))}"
                for s in skills
            ]
            parts.append('Compétences avec niveau :\n' + '\n'.join(lines))

    # Références, filtrées si sélection individuelle
    if 'references' in include_sections or selected_references is not None:
        refs = cv_data.get('references', [])
        if selected_references is not None:
            refs = [r for r in refs if r['name'] in selected_references]
        if refs:
            lines = [
                f"  - {r['name']} : \"{(r.get('reference') or '')[:220].rstrip()}…\""
                for r in refs
            ]
            parts.append('Références professionnelles :\n' + '\n'.join(lines))

    # Projets GitHub, filtrés si sélection individuelle
    if 'github_projects' in include_sections or selected_projects is not None:
        projects = cv_data.get('projects', [])
        if selected_projects is not None:
            projects = [p for p in projects if p['name'] in selected_projects]
        if projects:
            lines = []
            for p in projects[:8]:
                desc = p.get('summary') or p.get('description') or ''
                lang = p.get('primaryLanguage', '')
                lines.append(f"  - {p['name']} [{lang}]{' : ' + desc if desc else ''}")
            parts.append('Projets GitHub personnels :\n' + '\n'.join(lines))

    return ('\n\n' + '\n\n'.join(parts)) if parts else ''


def _build_premium_modules_text(cv_data: dict, selected_premium_modules: list | None = None) -> str:
    """Construit le texte des modules premium optionnels pour la LM."""
    modules = set(selected_premium_modules or [])
    if not modules:
        return ''

    parts = []

    if 'profiles' in modules:
        profiles = cv_data.get('basics', {}).get('profiles', [])
        if profiles:
            lines = []
            for p in profiles:
                network = p.get('network', '')
                url = p.get('url', '')
                username = p.get('username', '')
                lines.append(f"  - {network}: {username} {f'({url})' if url else ''}".strip())
            parts.append('Profils en ligne :\n' + '\n'.join(lines))

    if 'languages' in modules:
        languages = cv_data.get('languages', [])
        if languages:
            lines = [f"  - {lang.get('language', '')} : {lang.get('fluency', '')}" for lang in languages]
            parts.append('Langues :\n' + '\n'.join(lines))

    if 'volunteer' in modules:
        volunteer = cv_data.get('volunteer', [])
        if volunteer:
            lines = []
            for item in volunteer:
                title = ' - '.join(p for p in [item.get('position', ''), item.get('organization', '')] if p)
                summary = (item.get('summary') or '')[:180].replace('\n', ' ')
                lines.append(f'  - {title}{f" : {summary}" if summary else ""}')
            parts.append('Bénévolat :\n' + '\n'.join(lines))

    if 'awards' in modules:
        awards = cv_data.get('awards', [])
        if awards:
            lines = []
            for item in awards:
                name = item.get('title') or item.get('name', '')
                issuer = item.get('awarder') or item.get('issuer', '')
                date = (item.get('date') or '')[:4]
                suffix = ', '.join([p for p in [issuer, date] if p])
                lines.append(f'  - {name}{f" ({suffix})" if suffix else ""}')
            parts.append('Distinctions :\n' + '\n'.join(lines))

    if 'publications' in modules:
        publications = cv_data.get('publications', [])
        if publications:
            lines = []
            for item in publications:
                title = item.get('name') or item.get('title', '')
                publisher = item.get('publisher', '')
                lines.append(f"  - {title}{f' ({publisher})' if publisher else ''}")
            parts.append('Publications :\n' + '\n'.join(lines))

    return ('\n\n' + '\n\n'.join(parts)) if parts else ''


def get_ai_cv_suggestions(job: Job, cv_data: dict, github_token: str,
                          additional_prompt: str = '',
                          include_sections: list | None = None,
                          selected_education: list | None = None,
                          selected_certificates: list | None = None,
                          selected_skills: list | None = None,
                          selected_references: list | None = None,
                          selected_projects: list | None = None) -> dict:
    """Appelle l'API GitHub Models pour obtenir des suggestions de personnalisation du CV."""
    from tools.github_models_client import chat_completion
    try:
        from flask import current_app
        base_url = current_app.config.get('GITHUB_MODELS_BASE_URL', 'https://models.github.ai/inference')
        model_name = current_app.config.get('GITHUB_MODELS_MODEL', 'openai/gpt-4.1')
    except Exception:
        base_url = 'https://models.github.ai/inference'
        model_name = 'openai/gpt-4.1'

    inc = list(include_sections or [])
    # Ajouter implicitement 'education'/'certificates' si une sélection individuelle non vide est fournie
    if selected_education and 'education' not in inc:
        inc.append('education')
    if selected_certificates and 'certificates' not in inc:
        inc.append('certificates')
    if selected_skills and 'skills_rating' not in inc:
        inc.append('skills_rating')
    if selected_references and 'references' not in inc:
        inc.append('references')
    if selected_projects and 'github_projects' not in inc:
        inc.append('github_projects')

    work_summary = '\n'.join(
        '[{i}] {pos} chez {co} ({start} - {end}): {summary}'.format(
            i=i,
            pos=w.get('position', ''),
            co=w.get('name', ''),
            start=(w.get('startDate') or '?')[:4],
            end=(w.get('endDate') or 'present')[:4],
            summary=(w.get('summary') or '')[:150].replace('\n', ' '),
        )
        for i, w in enumerate(cv_data.get('work', []))
    )
    skills_summary = ', '.join(s['name'] for s in cv_data.get('skills', []))

    # Sections optionnelles (mode avancé)
    optional_text = _build_optional_sections_text(
        cv_data, inc,
        selected_education=selected_education,
        selected_certificates=selected_certificates,
        selected_skills=selected_skills,
        selected_references=selected_references,
        selected_projects=selected_projects,
    )

    # Instruction spécifique sur l'utilisation des sections additionnelles
    use_optional_instruction = ''
    if inc:
        use_optional_instruction = (
            "IMPORTANT : des données complémentaires ont été fournies ci-dessous. "
            "Utilise-les uniquement comme matière de fond pour adapter le résumé au poste, "
            "sans reprendre les intitulés des rubriques ni énumérer les éléments un par un. "
            "Le résultat doit rester synthétique, naturel et orienté valeur ajoutée.\n\n"
        )

    system_prompt = (
        "Tu es un expert en ressources humaines et en optimisation de CV. "
        "Analyse l offre d emploi et le profil complet du candidat, puis retourne tes recommandations "
        "uniquement sous forme de JSON valide, sans texte supplementaire."
    )
    user_prompt = (
        "{use_optional}"
        "Offre d emploi :\n"
        "- Intitule : {name}\n"
        "- Entreprise : {company}\n"
        "- Localisation : {loc}\n"
        "- LM existante : {lm}\n\n"
        "Experiences du candidat (index entre crochets) :\n{work}\n\n"
        "Competences disponibles : {skills}"
        "{optional}"
        "\n\n{extra}"
        'Retourne un objet JSON avec exactement ces champs :\n'
        '{{\n'
        '  "cv_title": "titre de CV personnalise en francais (max 80 caracteres)",\n'
        '  "summary": "resume professionnel personnalise en francais (3-4 phrases max 600 caracteres) — intègre les éléments sélectionnés de manière naturelle si pertinents",\n'
        '  "highlighted_work_indices": [liste d entiers : indices des 3-5 experiences les plus pertinentes],\n'
        '  "highlighted_skill_names": [liste de noms de competences les plus pertinentes pour ce poste]\n'
        '}}'
    ).format(
        use_optional=use_optional_instruction,
        name=job.name or 'N/A',
        company=job.company or 'N/A',
        loc=job.zipCode or 'N/A',
        lm=job.cover_letter_text or 'Non precise',
        work=work_summary,
        skills=skills_summary,
        optional=optional_text,
        extra=f"Instructions supplementaires : {additional_prompt}\n\n" if additional_prompt else '',
    )

    # Augmenter max_tokens si des sections avancées sont incluses
    max_tokens = 1200 if inc else 900

    try:
        raw = chat_completion(
            messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
            model=model_name,
            base_url=base_url,
            api_key=github_token,
            response_format={'type': 'json_object'},
            temperature=0.3,
            max_tokens=max_tokens,
            cache_ttl=45,
        )
    except Exception as exc:
        fallback = _default_cv_suggestions(cv_data)
        fallback['warning'] = (
            'Trop de requêtes vers GitHub Models. Réessayez dans une minute.' if _is_rate_limit_error(exc)
            else f"Aperçu généré sans IA : {exc}"
        )
        return fallback

    if raw:
        raw = raw.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
    try:
        result = _json.loads(raw or '{}')
        # Conserver la liste des sections actives pour affichage dans la modale
        result['_active_sections'] = inc
        return result
    except Exception:
        return _default_cv_suggestions(cv_data)


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extrait le texte d'un PDF si une bibliothèque appropriée est disponible."""
    try:
        import pdfminer.high_level
        return pdfminer.high_level.extract_text(str(pdf_path)) or ''
    except Exception:
        pass
    try:
        import PyPDF2
        text = ''
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ''
        return text
    except Exception:
        return ''


def get_ai_cover_letter_text(job: Job, github_token: str,
                             additional_prompt: str = '',
                             include_sections: list | None = None,
                             selected_education: list | None = None,
                             selected_certificates: list | None = None,
                             selected_skills: list | None = None,
                             selected_references: list | None = None,
                             selected_projects: list | None = None,
                             selected_premium_modules: list | None = None) -> str:
    """Génère une lettre de motivation personnalisée via l'API GitHub Models / OpenAI."""
    from openai import OpenAI

    try:
        from flask import current_app
        base_url = current_app.config.get('GITHUB_MODELS_BASE_URL', 'https://models.github.ai/inference')
        model_name = current_app.config.get('GITHUB_MODELS_MODEL', 'openai/gpt-4.1')
        static_folder = current_app.static_folder
        author_name = current_app.config.get('GMAIL_FULLNAME', 'Philippe Mourey')
    except Exception:
        base_url = 'https://models.github.ai/inference'
        model_name = 'openai/gpt-4.1'
        static_folder = str(Path(__file__).parent.parent / 'static')
        author_name = 'Philippe Mourey'

    # Charger cv_data pour les sections optionnelles
    cv_data: dict = {}
    try:
        cv_data = load_cv_data(static_folder)
    except Exception:
        pass

    # Extraire le texte du PDF de capture si disponible
    capture_text = ''
    capture_pdf_path = Path(static_folder) / 'images' / f'capture_{job.id}.pdf'
    if capture_pdf_path.exists():
        try:
            capture_text = _extract_pdf_text(capture_pdf_path)
        except Exception:
            pass

    system_prompt = (
        "Tu es un expert en ressources humaines et en rédaction de lettres de motivation. "
        "Rédige une lettre de motivation professionnelle et personnalisée en français, "
        "structurée en 3 à 4 paragraphes complets. Utilise la première personne du singulier (je/j'), "
        "emploie des phrases complètes et un style soutenu mais naturel. Évite les fragments et les listes à puces. "
        "Corrige les accords et verbes — écris des phrases bien conjuguées (ex. 'J'ai développé', 'J'ai conçu').\n\n"
        # "Inclue en fin de texte une formule de politesse courante et une signature courte (prénom et nom de l'auteur). "
        # "Réponds uniquement avec le corps de la lettre, comprenant la formule de politesse et la signature (pas d'en-tête ni de salutation initiale)."
    )

    # Renforcer le system prompt si des sections avancées sont incluses
    inc = list(include_sections or [])
    if selected_education and 'education' not in inc:
        inc.append('education')
    if selected_certificates and 'certificates' not in inc:
        inc.append('certificates')
    if selected_skills and 'skills_rating' not in inc:
        inc.append('skills_rating')
    if selected_references and 'references' not in inc:
        inc.append('references')
    if selected_projects and 'github_projects' not in inc:
        inc.append('github_projects')

    premium_modules = list(selected_premium_modules or [])

    if inc:
        system_prompt += (
            "\n\nIMPORTANT : des données complémentaires ont été fournies. "
            "Utilise uniquement les éléments explicitement sélectionnés et reformule-les de façon naturelle. "
            "N'énumère pas les rubriques, n'emploie pas leurs intitulés exacts et évite les citations trop littérales. "
            "La lettre doit rester fluide, générale et orientée sur la valeur apportée au poste."
        )

    # Augmenter max_tokens si des sections avancées sont incluses
    max_tokens = 1800 if inc else 1400

    context_parts = [
        f"Poste : {job.name or 'N/A'}",
        f"Entreprise : {job.company or 'N/A'}",
        f"Localisation : {job.zipCode or 'N/A'}",
    ]
    if job.url:
        context_parts.append(f"Lien de l'offre : {job.url}")
    if capture_text.strip():
        context_parts.append(
            f"Texte extrait de l'offre (capture PDF) :\n{capture_text.strip()[:2500]}"
        )
    elif job.is_capture:
        context_parts.append("Note : une capture PDF de l'offre est disponible (texte non extractible).")
    if job.cover_letter_text:
        context_parts.append(
            f"Lettre de motivation existante (à améliorer ou à utiliser comme base) :\n{job.cover_letter_text[:1200]}"
        )

    # Sections optionnelles (mode avancé)
    optional_text = _build_optional_sections_text(
        cv_data, inc,
        selected_education=selected_education,
        selected_certificates=selected_certificates,
        selected_skills=selected_skills,
        selected_references=selected_references,
        selected_projects=selected_projects,
    )
    premium_text = _build_premium_modules_text(cv_data, premium_modules)
    if optional_text.strip():
        context_parts.append("Données complémentaires du profil :" + optional_text)
    if premium_text.strip():
        context_parts.append("Modules premium complémentaires :" + premium_text)

    if additional_prompt:
        context_parts.append(f"Instructions supplémentaires / corrections : {additional_prompt}")

    user_prompt = "Génère la lettre de motivation pour ce poste :\n\n" + "\n\n".join(context_parts)

    if not github_token:
        title = job.name or 'ce poste'
        company = job.company or 'votre entreprise'
        return (
            f"Je vous adresse ma candidature pour le poste de {title} au sein de {company}.\n\n"
            "Fort de mon expérience dans le développement logiciel et la gestion de projets IT, "
            "je suis convaincu de pouvoir apporter une réelle valeur ajoutée à votre équipe.\n\n"
            "Je reste à votre disposition pour un entretien afin de vous présenter "
            "plus en détail mon parcours et mes motivations.\n\n"
            # "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.\n\n"
            # f"{author_name}\n\n"
            "[GITHUB_TOKEN non configuré : texte généré sans IA]"
        )

    try:
        raw = chat_completion(
            messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
            model=model_name,
            base_url=base_url,
            api_key=github_token,
            temperature=0.5,
            max_tokens=max_tokens,
            cache_ttl=45,
        )
        return raw.strip()
    except Exception as exc:
        if _is_rate_limit_error(exc):
            raise RuntimeError('Trop de requêtes vers GitHub Models. Réessayez dans une minute.') from exc
        raise RuntimeError(f"Erreur API IA lors de la génération de la LM : {exc}") from exc


def generate_tailored_cv_pdf_bytes(job: Job, cv_data: dict, suggestions: dict,
                                   include_sections: list | None = None,
                                   selected_education: list | None = None,
                                   selected_certificates: list | None = None,
                                   selected_skills: list | None = None,
                                   selected_references: list | None = None,
                                   selected_projects: list | None = None) -> bytes:
    """Genere le PDF du CV personnalise avec ReportLab."""
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (HRFlowable, Image, Paragraph,
                                    SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    try:
        from flask import current_app
        static_folder = current_app.static_folder
    except Exception:
        static_folder = str(Path(__file__).parent.parent / 'static')

    SENDER_NAME = 'PHILIPPE MOUREY'
    SENDER_STREET = '1880, route de Saint Jeannet'
    SENDER_CITY = '06700 Saint Laurent du Var'
    SENDER_PHONE = '06 89 15 08 56'
    SENDER_EMAIL = 'philippe.mourey@gmail.com'
    PHOTO_WIDTH = 2.5 * cm

    COLOR_DARK = rl_colors.HexColor('#1a1a2e')
    COLOR_BLUE = rl_colors.HexColor('#4a90d9')
    COLOR_GREY = rl_colors.HexColor('#555555')
    COLOR_LGREY = rl_colors.HexColor('#cccccc')

    page_w, page_h = A4
    lm = rm = 1.8 * cm
    tm = 0.8 * cm
    bm = 0.8 * cm
    avail_w = page_w - lm - rm

    _counter = [0]

    def _st(base_name, **kw):
        _counter[0] += 1
        name = f'{base_name}_{_counter[0]}'
        d = dict(fontName='Helvetica', fontSize=9.5, leading=13,
                 textColor=rl_colors.black, alignment=TA_LEFT)
        d.update(kw)
        return ParagraphStyle(name, **d)

    st_name = _st('nm', fontName='Helvetica-Bold', fontSize=15, leading=16, textColor=COLOR_DARK)
    st_title = _st('ti', fontName='Helvetica-Oblique', fontSize=10.5, leading=13, textColor=COLOR_BLUE)
    st_contact = _st('co', fontSize=8.5, leading=11, textColor=COLOR_GREY)
    st_icon = _st('ic', fontSize=10.5, leading=12, textColor=COLOR_GREY)
    st_section = _st('se', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=COLOR_BLUE)
    st_jt = _st('jt', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=COLOR_DARK)
    st_jc = _st('jc', fontSize=8.5, leading=11, textColor=COLOR_GREY)
    st_body = _st('bo', fontSize=9, leading=12, alignment=TA_JUSTIFY)
    st_hlblue = _st('hl', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=COLOR_BLUE)
    st_edu = _st('ed', fontName='Helvetica-Bold', fontSize=9, leading=12)
    st_edu_sub = _st('es', fontSize=8.5, leading=11, textColor=COLOR_GREY)

    story = []
    cv_title = suggestions.get('cv_title') or cv_data.get('basics', {}).get('label', '')

    photo_path = Path(static_folder) / 'Photo_CV.png'
    if not photo_path.exists():
        photo_path = Path(static_folder) / 'photo.jpg'

    name_cell = [
        Paragraph(SENDER_NAME, st_name),
        Spacer(1, 4),
        Paragraph(cv_title, st_title),
        Spacer(1, 6),
        Paragraph(SENDER_STREET, st_contact),
        Paragraph(SENDER_CITY, st_contact),
        Paragraph('\u260e ' + SENDER_PHONE, st_icon),
        Paragraph('\u2709 ' + SENDER_EMAIL, st_icon),
    ]

    if photo_path.exists():
        try:
            from PIL import Image as PILImage
            pil_img = PILImage.open(str(photo_path))
            orig_w, orig_h = pil_img.size
            photo_height = PHOTO_WIDTH * orig_h / orig_w
            photo_img = Image(str(photo_path), width=PHOTO_WIDTH, height=photo_height)
            hdr_data = [[name_cell, photo_img]]
            hdr_cols = [None, PHOTO_WIDTH + 0.2 * cm]
        except Exception:
            hdr_data = [[name_cell]]
            hdr_cols = [None]
    else:
        hdr_data = [[name_cell]]
        hdr_cols = [None]

    hdr_table = Table(hdr_data, colWidths=hdr_cols)
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width='100%', thickness=0.5, color=COLOR_LGREY))
    story.append(Spacer(1, 8))

    # Profil
    summary = suggestions.get('summary') or cv_data.get('basics', {}).get('summary', '')
    if summary:
        story.append(Paragraph('PROFIL', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        story.append(Paragraph(summary, st_body))
        story.append(Spacer(1, 9))

    # Experiences
    work_list = cv_data.get('work', [])
    hl_indices = set(suggestions.get('highlighted_work_indices') or [])
    hl_work = [w for i, w in enumerate(work_list) if i in hl_indices]
    other_work = [w for i, w in enumerate(work_list) if i not in hl_indices]
    sorted_work = hl_work + other_work

    if sorted_work:
        story.append(Paragraph('EXPERIENCES PROFESSIONNELLES', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        for idx, work in enumerate(sorted_work[:8]):
            is_hl = work in hl_work
            pos = work.get('position', '')
            co = work.get('name', '')
            start = (work.get('startDate') or '')[:7]
            end = (work.get('endDate') or '')[:7] or 'present'
            loc = work.get('location', '')
            story.append(Paragraph(pos, st_hlblue if is_hl else st_jt))
            parts = [p for p in [co, (start + ' - ' + end if start else ''), loc] if p]
            story.append(Paragraph(' | '.join(parts), st_jc))
            wtext = work.get('summary', '')
            if wtext:
                for line in [ln.strip() for ln in wtext.split('\n') if ln.strip()][:2]:
                    story.append(Paragraph('\u2022 ' + line, st_body))
            hls = work.get('highlights', [])
            if hls:
                story.append(Paragraph('<i>Techn. : ' + hls[0] + '</i>', st_edu_sub))
            if idx < len(sorted_work[:8]) - 1:
                story.append(Spacer(1, 5))
        story.append(Spacer(1, 9))

    # Competences
    skills = cv_data.get('skills', [])
    if selected_skills is not None:
        skills = [s for s in skills if s.get('name') in selected_skills]
    hl_skill_names = set(suggestions.get('highlighted_skill_names') or [])
    if skills:
        story.append(Paragraph('COMPETENCES', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        hl_sk = [s for s in skills if s['name'] in hl_skill_names]
        other_sk = [s for s in skills if s['name'] not in hl_skill_names]
        all_sk = hl_sk + other_sk
        n_cols = 3
        rows = []
        for j in range(0, len(all_sk), n_cols):
            cells = []
            for s in all_sk[j:j + n_cols]:
                if s['name'] in hl_skill_names:
                    cells.append(Paragraph(
                        '<b>\u2605 ' + s['name'] + '</b>',
                        _st('skh', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=COLOR_BLUE),
                    ))
                else:
                    cells.append(Paragraph(
                        '\u25cb ' + s['name'],
                        _st('skn', fontSize=9, leading=12),
                    ))
            while len(cells) < n_cols:
                cells.append(Paragraph('', st_body))
            rows.append(cells)
        if rows:
            sk_t = Table(rows, colWidths=[avail_w / n_cols] * n_cols)
            sk_t.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            story.append(sk_t)
        story.append(Spacer(1, 9))

    # Formation
    # Si selected_education est fourni : afficher uniquement les entrées sélectionnées
    # Sinon : afficher toutes les entrées (comportement original, sans limite de 4)
    all_education = cv_data.get('education', [])
    if selected_education is not None:
        education_to_show = [all_education[i] for i in selected_education if i < len(all_education)]
    else:
        education_to_show = all_education  # toutes les formations
    if education_to_show:
        story.append(Paragraph('FORMATION', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        for edu in education_to_show:
            tp = [p for p in [edu.get('studyType', ''), edu.get('area', '')] if p]
            story.append(Paragraph(' - '.join(tp) or edu.get('institution', ''), st_edu))
            ey = (edu.get('endDate') or '')[:4]
            story.append(Paragraph(edu.get('institution', '') + (' (' + ey + ')' if ey else ''), st_edu_sub))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 9))

    # Certifications & Langues
    # Si selected_certificates est fourni : afficher uniquement les certifications sélectionnées
    all_certs = cv_data.get('certificates', [])
    if selected_certificates is not None:
        certs = [c for c in all_certs if c['name'] in selected_certificates]
    else:
        certs = all_certs  # toutes les certifications
    languages = cv_data.get('languages', [])
    left_c: list = []
    right_c: list = []

    if certs:
        left_c.append(Paragraph('CERTIFICATIONS', st_section))
        left_c.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        left_c.append(Spacer(1, 4))
        for c in certs:
            yr = (c.get('date') or '')[:4]
            left_c.append(Paragraph(
                '\u2022 ' + c['name'] + ' (' + c.get('issuer', '') + ', ' + yr + ')',
                st_body,
            ))
    if languages:
        right_c.append(Paragraph('LANGUES', st_section))
        right_c.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        right_c.append(Spacer(1, 4))
        for lang in languages:
            right_c.append(Paragraph(
                '\u2022 ' + lang['language'] + ' - ' + lang.get('fluency', ''),
                st_body,
            ))

    if left_c or right_c:
        if not left_c:
            left_c = [Paragraph('', st_body)]
        if not right_c:
            right_c = [Paragraph('', st_body)]
        bot = Table([[left_c, right_c]], colWidths=[avail_w * 0.6, avail_w * 0.4])
        bot.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(bot)
        story.append(Spacer(1, 9))

    inc = include_sections or suggestions.get('_active_sections') or []

    # Section Projets GitHub (si cochée en mode avancé)
    if 'github_projects' in inc or selected_projects is not None:
        projects = cv_data.get('projects', [])
        if selected_projects is not None:
            projects = [p for p in projects if p.get('name') in selected_projects]
        if projects:
            story.append(Paragraph('PROJETS PERSONNELS', st_section))
            story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
            story.append(Spacer(1, 4))
            for p in projects[:6]:
                langs = p.get('languages') or ([p['primaryLanguage']] if p.get('primaryLanguage') else [])
                lang_str = ', '.join(langs[:4]) if langs else ''
                proj_url = p.get('url') or p.get('githubUrl') or ''
                title_line = p['name'] + (f' [{lang_str}]' if lang_str else '')
                story.append(Paragraph('\u2022 ' + title_line, st_jt))
                desc = p.get('summary') or p.get('description') or ''
                if desc:
                    story.append(Paragraph(desc[:180], st_body))
                if proj_url:
                    story.append(Paragraph(f'<link href="{proj_url}">{proj_url}</link>',
                                           _st('lk', fontSize=7.5, leading=10, textColor=COLOR_BLUE)))
                story.append(Spacer(1, 3))
            story.append(Spacer(1, 9))

    # Section Références (si cochée en mode avancé)
    if 'references' in inc or selected_references is not None:
        refs = cv_data.get('references', [])
        if selected_references is not None:
            refs = [r for r in refs if r.get('name') in selected_references]
        if refs:
            story.append(Paragraph('RÉFÉRENCES PROFESSIONNELLES', st_section))
            story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
            story.append(Spacer(1, 4))
            for ref in refs:
                story.append(Paragraph(ref.get('name', ''), st_jt))
                ref_text = (ref.get('reference') or '')[:350].rstrip()
                if len(ref.get('reference', '')) > 350:
                    ref_text += '\u2026'
                story.append(Paragraph(f'\u201c{ref_text}\u201d',
                                       _st('rf', fontSize=8.5, leading=11, textColor=COLOR_GREY,
                                           alignment=__import__('reportlab.lib.enums', fromlist=['TA_JUSTIFY']).TA_JUSTIFY)))
                story.append(Spacer(1, 6))
            story.append(Spacer(1, 9))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=lm, rightMargin=rm, topMargin=tm, bottomMargin=bm,
        title=build_cv_pdf_filename(job), author=SENDER_NAME,
    )
    doc.build(story)
    return buffer.getvalue()




