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


def get_ai_cv_suggestions(job: Job, cv_data: dict, github_token: str) -> dict:
    """Appelle l'API GitHub Models pour obtenir des suggestions de personnalisation du CV."""
    from openai import OpenAI
    try:
        from flask import current_app
        base_url = current_app.config.get('GITHUB_MODELS_BASE_URL', 'https://models.github.ai/inference')
        model_name = current_app.config.get('GITHUB_MODELS_MODEL', 'openai/gpt-4o-mini')
    except Exception:
        base_url = 'https://models.github.ai/inference'
        model_name = 'openai/gpt-4o-mini'

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

    system_prompt = (
        "Tu es un expert en ressources humaines et en optimisation de CV. "
        "Analyse l offre d emploi et le profil du candidat, puis retourne tes recommandations "
        "uniquement sous forme de JSON valide, sans texte supplementaire."
    )
    user_prompt = (
        "Offre d emploi :\n"
        "- Intitule : {name}\n"
        "- Entreprise : {company}\n"
        "- Localisation : {loc}\n"
        "- Description / LM : {lm}\n\n"
        "Experiences du candidat (index entre crochets) :\n{work}\n\n"
        "Competences disponibles : {skills}\n\n"
        'Retourne un objet JSON avec exactement ces champs :\n'
        '{{\n'
        '  "cv_title": "titre de CV personnalise en francais (max 80 caracteres)",\n'
        '  "summary": "resume professionnel personnalise en francais (3-4 phrases, max 500 caracteres)",\n'
        '  "highlighted_work_indices": [liste d entiers : indices des 3-5 experiences les plus pertinentes],\n'
        '  "highlighted_skill_names": [liste de noms de competences les plus pertinentes pour ce poste]\n'
        '}}'
    ).format(
        name=job.name or 'N/A',
        company=job.company or 'N/A',
        loc=job.zipCode or 'N/A',
        lm=job.cover_letter_text or 'Non precise',
        work=work_summary,
        skills=skills_summary,
    )

    client = OpenAI(base_url=base_url, api_key=github_token)

    raw = None
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.3,
            max_tokens=900,
        )
        raw = response.choices[0].message.content
    except Exception:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.3,
                max_tokens=900,
            )
            raw = response.choices[0].message.content
        except Exception as exc:
            fallback = _default_cv_suggestions(cv_data)
            fallback['warning'] = f"Aperçu généré sans IA : {exc}"
            return fallback

    if raw:
        raw = raw.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
    try:
        return _json.loads(raw or '{}')
    except Exception:
        return _default_cv_suggestions(cv_data)


def generate_tailored_cv_pdf_bytes(job: Job, cv_data: dict, suggestions: dict) -> bytes:
    """Genere le PDF du CV personnalise avec ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image,
    )

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
    education = cv_data.get('education', [])
    if education:
        story.append(Paragraph('FORMATION', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        for edu in education[:4]:
            tp = [p for p in [edu.get('studyType', ''), edu.get('area', '')] if p]
            story.append(Paragraph(' - '.join(tp) or edu.get('institution', ''), st_edu))
            ey = (edu.get('endDate') or '')[:4]
            story.append(Paragraph(edu.get('institution', '') + (' (' + ey + ')' if ey else ''), st_edu_sub))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 9))

    # Certifications & Langues
    certs = cv_data.get('certificates', [])
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

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=lm, rightMargin=rm, topMargin=tm, bottomMargin=bm,
        title=build_cv_pdf_filename(job), author=SENDER_NAME,
    )
    doc.build(story)
    return buffer.getvalue()


