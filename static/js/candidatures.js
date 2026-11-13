/* Logique de la page « Candidatures » (extraite de templates/candidatures.html).
 * Configuration injectée par le template : window.CAND_CONFIG = { userId }.
 */
let showClosed = false;
let currentCvPreviewJobId = null;
let currentCvPreviewJobName = '';
let currentCvPreviewCompany = '';
let currentCvSavedUrl = null;
let currentCvSavedFilename = null;
let currentCvAutoSkillSuggestionsApplied = false;

let currentLmAiJobId = null;
let currentLmAiText = '';

function toggleExpired(jobId) {
	fetch('/toggle_expired/' + jobId, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		}
	}).then(() => {
		location.reload();
	});
}

function deleteJob(jobId) {
	if (confirm('Êtes-vous sûr de vouloir supprimer cette candidature ?')) {
		window.location.href = '/delete/' + jobId;
	}
}

function showLM(id) {
	// prefer desktop element, fallback to mobile
	const elt = document.getElementById('lm-content-desktop-' + id) || document.getElementById('lm-content-mobile-' + id);
	const modalBody = document.getElementById('lmModalBody');
	if (elt && modalBody) {
		// use textContent to avoid interpreting HTML
		modalBody.textContent = elt.textContent || elt.innerText || '';
		var myModal = new bootstrap.Modal(document.getElementById('lmModal'));
		myModal.show();
	}
}

function _getCheckedSections(prefix) {
	/* Retourne la liste des sections activées (et uniquement elles) */
	const boxes = document.querySelectorAll('input[data-section-prefix="' + prefix + '"][data-selection-role="section"]:checked');
	return Array.from(boxes).map(b => b.value);
}

function _getCheckedValues(selector) {
	return Array.from(document.querySelectorAll(selector + ':checked')).map(b => b.value);
}

function _getSelectedEducation(prefix = 'cv') {
	/* Indices (int) des formations cochées pour le CV */
	return Array.from(document.querySelectorAll('.' + prefix + '-education-check:checked'))
		.map(b => parseInt(b.value));
}

function _getSelectedCertificates(prefix = 'cv') {
	/* Noms des certifications cochées pour le CV */
	return Array.from(document.querySelectorAll('.' + prefix + '-cert-check:checked'))
		.map(b => b.value);
}

function _getSelectedSkills(prefix) {
	return _getCheckedValues('.' + prefix + '-skill-check');
}

function _getSelectedReferences(prefix) {
	return _getCheckedValues('.' + prefix + '-ref-check');
}

function _getSelectedProjects(prefix) {
	return _getCheckedValues('.' + prefix + '-project-check');
}

function _setGroupChecked(itemSelector, sectionCheckboxId, checked) {
	document.querySelectorAll(itemSelector).forEach(cb => {
		cb.checked = checked;
	});
	if (sectionCheckboxId) {
		const sec = document.getElementById(sectionCheckboxId);
		if (sec) sec.checked = checked;
	}
}

function _syncSectionFromItems(itemSelector, sectionCheckboxId) {
	if (!sectionCheckboxId) return;
	const sec = document.getElementById(sectionCheckboxId);
	if (!sec) return;
	const boxes = document.querySelectorAll(itemSelector);
	const anyChecked = Array.from(boxes).some(cb => cb.checked);
	sec.checked = anyChecked;
}

function _applySuggestedSkillSelections(prefix, skillNames) {
	const wanted = new Set(skillNames || []);
	if (!wanted.size) return false;
	const boxes = document.querySelectorAll('.' + prefix + '-skill-check');
	let changed = false;
	boxes.forEach(cb => {
		if (wanted.has(cb.value) && !cb.checked) {
			cb.checked = true;
			changed = true;
		}
	});
	if (changed) {
		_syncSectionFromItems('.' + prefix + '-skill-check', prefix + '-sec-skills-rating');
	}
	return changed;
}

function _applyDefaultEducationAndCertSelections(prefix) {
	const educationSelector = '.' + prefix + '-education-check';
	const certSelector = '.' + prefix + '-cert-check';
	const educationBoxes = Array.from(document.querySelectorAll(educationSelector));
	const certBoxes = Array.from(document.querySelectorAll(certSelector));
	let changed = false;

	if (educationBoxes.length > 0 && !educationBoxes.some(cb => cb.checked)) {
		educationBoxes.forEach(cb => { cb.checked = true; });
		changed = true;
		_syncSectionFromItems(educationSelector, prefix + '-sec-education');
	}
	if (certBoxes.length > 0 && !certBoxes.some(cb => cb.checked)) {
		certBoxes.forEach(cb => { cb.checked = true; });
		changed = true;
		_syncSectionFromItems(certSelector, prefix + '-sec-certificates');
	}

	return changed;
}

function toggleAdvancedSections(prefix, checked) {
	const sectionSelector = 'input[data-section-prefix="' + prefix + '"][data-selection-role="section"]';
	document.querySelectorAll(sectionSelector).forEach(cb => {
		cb.checked = checked;
	});

	if (prefix === 'cv') {
		_setGroupChecked('.cv-education-check', null, checked);
		_setGroupChecked('.cv-cert-check', null, checked);
		_setGroupChecked('.cv-skill-check', null, checked);
		_setGroupChecked('.cv-ref-check', null, checked);
		_setGroupChecked('.cv-project-check', null, checked);
	}
	if (prefix === 'lm') {
		_setGroupChecked('.lm-education-check', null, checked);
		_setGroupChecked('.lm-cert-check', null, checked);
		_setGroupChecked('.lm-skill-check', null, checked);
		_setGroupChecked('.lm-ref-check', null, checked);
		_setGroupChecked('.lm-project-check', null, checked);
	}
}

function initAdvancedSelectionSync() {
	const groupLinks = [
		{ item: '.cv-education-check', sectionId: 'cv-sec-education' },
		{ item: '.cv-cert-check', sectionId: 'cv-sec-certificates' },
		{ item: '.cv-skill-check', sectionId: 'cv-sec-skills-rating' },
		{ item: '.cv-ref-check', sectionId: 'cv-sec-references' },
		{ item: '.cv-project-check', sectionId: 'cv-sec-github' },
		{ item: '.lm-education-check', sectionId: 'lm-sec-education' },
		{ item: '.lm-cert-check', sectionId: 'lm-sec-certificates' },
		{ item: '.lm-skill-check', sectionId: 'lm-sec-skills-rating' },
		{ item: '.lm-ref-check', sectionId: 'lm-sec-references' },
		{ item: '.lm-project-check', sectionId: 'lm-sec-github' },
	];

	groupLinks.forEach(link => {
		document.querySelectorAll(link.item).forEach(cb => {
			cb.addEventListener('change', () => _syncSectionFromItems(link.item, link.sectionId));
		});
		_syncSectionFromItems(link.item, link.sectionId);
	});
}

function openCvModal(jobId, jobName, company) {
	currentCvPreviewJobId = jobId;
	currentCvPreviewJobName = jobName || '';
	currentCvPreviewCompany = company || '';
	currentCvSavedUrl = null;
	currentCvSavedFilename = null;
	currentCvAutoSkillSuggestionsApplied = false;
	document.getElementById('cvModalTitle').textContent = 'Génération du CV pour ' + (currentCvPreviewJobName || 'cette offre');
	document.getElementById('cvRetryBtn').classList.remove('d-none');
	document.getElementById('cvInsertBtn').classList.add('d-none');
	document.getElementById('cvInsertBtn').disabled = false;
	document.getElementById('cvInsertBtn').textContent = '📥 Insérer CV';
	document.getElementById('cvDownloadBtn').classList.add('d-none');
	document.getElementById('cvAdditionalPrompt').value = '';
	// Ne pas réinitialiser les checkboxes avancées : l'utilisateur garde ses choix d'une ouverture à l'autre
	// Afficher le placeholder et le bouton Générer (pas d'auto-exécution)
	document.getElementById('cvModalBody').innerHTML =
		'<div class="text-center py-4 text-muted">Cliquez sur <strong>🤖 Générer</strong> pour lancer l\'analyse IA.</div>';
	const retryBtnInit = document.getElementById('cvRetryBtn');
	retryBtnInit.classList.remove('d-none');
	retryBtnInit.textContent = '🤖 Générer';
	var modal = new bootstrap.Modal(document.getElementById('cvModal'));
	modal.show();
}

			async function loadCvPreview(jobId) {
					const body = document.getElementById('cvModalBody');
	const retryBtn = document.getElementById('cvRetryBtn');
	const insertBtn = document.getElementById('cvInsertBtn');
	const dlBtn = document.getElementById('cvDownloadBtn');
	const additionalPrompt = document.getElementById('cvAdditionalPrompt').value;
	body.innerHTML =
		'<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div>' +
		'<p class="mt-3 text-muted">Analyse IA de l\'offre en cours…</p></div>';
	insertBtn.classList.add('d-none');
	dlBtn.classList.add('d-none');
	retryBtn.disabled = true;

	try {
		// Show which CV source will be used in the modal (default user CV if present)
		// Ensure an element exists in the modal body to display this info
		if (!document.getElementById('cvDefaultInfo')) {
			const infoLine = document.createElement('div');
			infoLine.id = 'cvDefaultInfo';
			infoLine.className = 'small text-muted mb-2';
			body.parentNode.insertBefore(infoLine, body);
		}

		// Fetch user's default CV metadata and include it in the IA request so the server
		// can use the user's default (parsed JSON or PDF) when generating suggestions.
		let defaultCv = null;
		let ddata = null;
		try {
			const dresp = await fetch('/user_cv_default', { method: 'GET' });
			if (dresp.ok) {
				ddata = await dresp.json();
				defaultCv = ddata.default || null;
			}
		} catch (e) {
			// ignore, fallback handled server-side
		}

		// Update the small info line to show the CV filename or fallback notice
		const infoElt = document.getElementById('cvDefaultInfo');
		if (infoElt) {
			if (ddata && ddata.default_url) {
				infoElt.innerHTML = 'CV utilisé : <a href="' + ddata.default_url + '" target="_blank">' + escapeHtml(ddata.default) + '</a>';
			} else if (defaultCv && typeof defaultCv === 'string') {
				const url = '/static/uploads/users/' + window.CAND_CONFIG.userId + '/cvs/' + encodeURIComponent(defaultCv);
				infoElt.innerHTML = 'CV utilisé : <a href="' + url + '" target="_blank">' + escapeHtml(defaultCv) + '</a>';
			} else if (defaultCv && defaultCv.filename) {
				// backward-compatible object form
				const url = defaultCv.url || ('/static/uploads/' + defaultCv.filename);
				infoElt.innerHTML = 'CV utilisé : <a href="' + url + '" target="_blank">' + escapeHtml(defaultCv.filename) + '</a>';
			} else {
				infoElt.textContent = 'CV utilisé : profil parsé intégré (fallback si aucun CV uploadé)';
			}
		}
		const resp = await fetch('/preview_cv_data/' + jobId, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				additional_prompt: additionalPrompt,
				default_cv: defaultCv,
				ats_mode: document.getElementById('cvAtsMode') ? document.getElementById('cvAtsMode').checked : false,
				include_sections: _getCheckedSections('cv'),
				selected_education: _getSelectedEducation('cv'),
				selected_certificates: _getSelectedCertificates('cv'),
				selected_skills: _getSelectedSkills('cv'),
				selected_references: _getSelectedReferences('cv'),
				selected_projects: _getSelectedProjects('cv'),
			}),
		});
		const data = await readResponseJson(resp);
		if (!resp.ok) {
			if (data.profile_incomplete) {
				body.innerHTML =
					'<div class="alert alert-warning"><strong>⚠️ Profil incomplet :</strong> ' + escapeHtml(data.error) +
					'<div class="mt-3"><a href="/update_account/' + window.CAND_CONFIG.userId + '" class="btn btn-warning btn-sm">⚙️ Renseigner mes coordonnées</a></div></div>';
			} else {
				body.innerHTML =
					'<div class="alert alert-danger"><strong>Erreur :</strong> ' + (data.error || resp.statusText) + '</div>';
			}
			retryBtn.disabled = false;
			return;
		}

		if (!currentCvAutoSkillSuggestionsApplied) {
			const currentSkillSelections = _getSelectedSkills('cv');
			let applied = false;
			if ((!currentSkillSelections || currentSkillSelections.length === 0) && data.highlighted_skill_names && data.highlighted_skill_names.length > 0) {
				applied = _applySuggestedSkillSelections('cv', data.highlighted_skill_names) || applied;
			}
			applied = _applyDefaultEducationAndCertSelections('cv') || applied;
			if (applied) {
				currentCvAutoSkillSuggestionsApplied = true;
				await loadCvPreview(jobId);
				return;
			}
		}

		let html = '';
		if (_getCheckedSections('cv').length || _getSelectedEducation('cv').length || _getSelectedCertificates('cv').length || _getSelectedSkills('cv').length || _getSelectedReferences('cv').length || _getSelectedProjects('cv').length) {
			html += '<div class="alert alert-light border py-2 small mb-2">Sélections manuelles prises en compte pour adapter le CV.</div>';
		}
		if (data.cv_title) {
			html += '<h6 class="text-primary fw-bold">' + escapeHtml(data.cv_title) + '</h6>';
		}
		// Afficher le résumé seulement s'il contient du texte non vide (trim) — sinon ne rien afficher
		if (data.summary && String(data.summary).trim().length > 0) {
			html += '<p class="small mt-2">' + escapeHtml(data.summary) + '</p>';
		}
		if (data.warning) {
			html += '<div class="alert alert-warning py-2 small mb-2">' + escapeHtml(data.warning) + '</div>';
		}
		if (data.highlighted_work_details && data.highlighted_work_details.length > 0) {
			html += '<hr><strong class="small">Expériences mises en avant :</strong><ul class="small mt-1">';
			data.highlighted_work_details.forEach(w => {
				html += '<li><b>' + escapeHtml(w.position) + '</b> chez ' + escapeHtml(w.company) + ' <span class="text-muted">(' + escapeHtml(w.dates) + ')</span></li>';
			});
			html += '</ul>';
		}
		if (data.highlighted_skill_names && data.highlighted_skill_names.length > 0) {
			html += '<hr><strong class="small">Compétences mises en avant :</strong>';
			html += '<div class="mt-1">';
			data.highlighted_skill_names.forEach(sk => {
				html += '<span class="badge bg-primary me-1 mb-1">' + escapeHtml(sk) + '</span>';
			});
			html += '</div>';
		}
		body.innerHTML = html;
		insertBtn.classList.remove('d-none');
		retryBtn.textContent = '↻ Régénérer';
		// Si un CV a déjà été inséré pour cette session, ré-afficher le bouton télécharger
		if (currentCvSavedUrl) {
			_showCvDownloadButton(currentCvSavedUrl, currentCvSavedFilename);
		}
	} catch (err) {
		body.innerHTML = '<div class="alert alert-danger"><strong>Erreur réseau :</strong> ' + escapeHtml(err.message) + '</div>';
	} finally {
		retryBtn.disabled = false;
	}
}

async function showCVPreview(jobId, jobName, company) {
	openCvModal(jobId, jobName, company);
}

function retryCvPreview() {
	if (currentCvPreviewJobId !== null) {
		loadCvPreview(currentCvPreviewJobId);
	}
}

function resetCvPrompt() {
	document.getElementById('cvAdditionalPrompt').value = '';
}

function _showCvDownloadButton(url, filename) {
	const dlBtn = document.getElementById('cvDownloadBtn');
	dlBtn.href = url;
	dlBtn.setAttribute('data-filename', filename || 'CV.pdf');
	dlBtn.classList.remove('d-none');
}

// Force download via fetch to ensure the PDF is downloaded (not opened inline)
document.addEventListener('DOMContentLoaded', () => {
	const dl = document.getElementById('cvDownloadBtn');
	if (!dl) return;
	dl.addEventListener('click', async (e) => {
		e.preventDefault();
		const url = dl.href;
			// Use the pretty filename provided on the element (data-filename) when available
			const filename = dl.getAttribute('data-filename') || dl.dataset.filename || ('cv_' + Date.now() + '.pdf');
		try {
			const resp = await fetch(url, { credentials: 'same-origin' });
			if (!resp.ok) throw new Error('Téléchargement échoué: ' + resp.statusText);
			const blob = await resp.blob();
			const blobUrl = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = blobUrl;
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(blobUrl);
		} catch (err) {
			alert('Erreur lors du téléchargement : ' + err.message);
		}
	});

	// Attach handlers to any CV PDF links in lists so they download instead of opening
	document.querySelectorAll('.cv-download-link').forEach(link => {
		link.addEventListener('click', async (e) => {
			e.preventDefault();
			const url = link.href;
						// Use the pretty filename provided on the link (data-filename) when available
						const filename = link.getAttribute('data-filename') || link.dataset.filename || ('cv_' + Date.now() + '.pdf');
			try {
				const resp = await fetch(url, { credentials: 'same-origin' });
				if (!resp.ok) throw new Error('Téléchargement échoué: ' + resp.statusText);
				const blob = await resp.blob();
				const blobUrl = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = blobUrl;
				a.download = filename;
				document.body.appendChild(a);
				a.click();
				a.remove();
				URL.revokeObjectURL(blobUrl);
			} catch (err) {
				alert('Erreur lors du téléchargement : ' + err.message);
			}
		});
	});
});

async function insertCvPdf() {
	if (!currentCvPreviewJobId) return;
	const insertBtn = document.getElementById('cvInsertBtn');
	const additionalPrompt = document.getElementById('cvAdditionalPrompt').value;
	insertBtn.disabled = true;
	insertBtn.textContent = '⏳ Génération…';
	try {
		const resp = await fetch('/save_cv_pdf/' + currentCvPreviewJobId, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				additional_prompt: additionalPrompt,
				include_sections: _getCheckedSections('cv'),
				selected_education: _getSelectedEducation('cv'),
				selected_certificates: _getSelectedCertificates('cv'),
				selected_skills: _getSelectedSkills('cv'),
				selected_references: _getSelectedReferences('cv'),
				selected_projects: _getSelectedProjects('cv'),
			}),
		});
		const data = await readResponseJson(resp);
		if (resp.ok) {
			currentCvSavedUrl = data.url;
			currentCvSavedFilename = data.filename || 'CV.pdf';
			insertBtn.textContent = '✅ CV inséré !';
			_showCvDownloadButton(currentCvSavedUrl, currentCvSavedFilename);
			setTimeout(() => location.reload(), 1800);
		} else {
			alert('Erreur lors de l\'insertion du CV : ' + (data.error || 'inconnue'));
			insertBtn.disabled = false;
			insertBtn.textContent = '📥 Insérer CV';
		}
	} catch (err) {
		alert('Erreur réseau : ' + err.message);
		insertBtn.disabled = false;
		insertBtn.textContent = '📥 Insérer CV';
	}
}

/* ── LM IA ─────────────────────────────────────────────────────── */

function openLmAiModal(jobId, jobName, company) {
	currentLmAiJobId = jobId;
	// Try to preload an existing LM: prefer unsaved generated draft (localStorage), else saved LM in page
	const draftKey = 'lm_generated_' + jobId;
	const storedDraft = (window.localStorage && localStorage.getItem(draftKey)) || null;
	if (storedDraft) {
		currentLmAiText = storedDraft;
	} else {
		// look for hidden elements that contain saved LM text (desktop/mobile)
		const desk = document.getElementById('lm-content-desktop-' + jobId);
		const mob = document.getElementById('lm-content-mobile-' + jobId);
		if (desk && desk.textContent && desk.textContent.trim()) {
			currentLmAiText = desk.textContent.trim();
		} else if (mob && mob.textContent && mob.textContent.trim()) {
			currentLmAiText = mob.textContent.trim();
		} else {
			currentLmAiText = '';
		}
	}
	document.getElementById('lmAiModalTitle').textContent =
		'🤖 Génération LM pour ' + (jobName || 'cette offre');
	document.getElementById('lmAiInsertBtn').classList.add('d-none');
	document.getElementById('lmAiAdditionalPrompt').value = '';
	// If we have a preloaded LM text, show it so user can refine via prompt; otherwise show placeholder
	if (currentLmAiText) {
		document.getElementById('lmAiModalBody').innerHTML = '<div style="white-space:pre-wrap">' + escapeHtml(currentLmAiText) + '</div>';
		document.getElementById('lmAiInsertBtn').classList.remove('d-none');
	} else {
		document.getElementById('lmAiModalBody').innerHTML = '<div class="text-center py-4 text-muted">Cliquez sur <strong>🤖 Générer</strong> pour lancer la génération IA.</div>';
	}
	const lmRetryBtnInit = document.getElementById('lmAiRetryBtn');
	lmRetryBtnInit.textContent = '🤖 Générer';
	var modal = new bootstrap.Modal(document.getElementById('lmAiModal'));
	modal.show();
}

async function loadLmAiPreview(jobId) {
	const body = document.getElementById('lmAiModalBody');
	const retryBtn = document.getElementById('lmAiRetryBtn');
	const insertBtn = document.getElementById('lmAiInsertBtn');
	const additionalPrompt = document.getElementById('lmAiAdditionalPrompt').value;

	body.innerHTML =
		'<div class="text-center py-4"><div class="spinner-border text-success" role="status"></div>' +
		'<p class="mt-3 text-muted">Génération de la lettre de motivation en cours…</p></div>';
	insertBtn.classList.add('d-none');
	retryBtn.disabled = true;

	try {
		// Same behaviour as CV: include user's default CV (parsed JSON / pdf) so LM IA can reference it
		// Show a small info line about which CV will be used
		if (!document.getElementById('lmDefaultInfo')) {
			const infoLine = document.createElement('div');
			infoLine.id = 'lmDefaultInfo';
			infoLine.className = 'small text-muted mb-2';
			body.parentNode.insertBefore(infoLine, body);
		}
		let defaultCv = null;
		let ddata = null;
		try {
			const dresp = await fetch('/user_cv_default', { method: 'GET' });
			if (dresp.ok) {
				ddata = await dresp.json();
				defaultCv = ddata.default || null;
			}
		} catch (e) {
			// ignore
		}
		const infoElt = document.getElementById('lmDefaultInfo');
		if (infoElt) {
			if (ddata && ddata.default_url) {
				infoElt.innerHTML = 'CV utilisé : <a href="' + ddata.default_url + '" target="_blank">' + escapeHtml(ddata.default) + '</a>';
			} else if (defaultCv && typeof defaultCv === 'string') {
				const url = '/static/uploads/users/' + window.CAND_CONFIG.userId + '/cvs/' + encodeURIComponent(defaultCv);
				infoElt.innerHTML = 'CV utilisé : <a href="' + url + '" target="_blank">' + escapeHtml(defaultCv) + '</a>';
			} else if (defaultCv && defaultCv.filename) {
				const url = defaultCv.url || ('/static/uploads/' + defaultCv.filename);
				infoElt.innerHTML = 'CV utilisé : <a href="' + url + '" target="_blank">' + escapeHtml(defaultCv.filename) + '</a>';
			} else {
				infoElt.textContent = 'CV utilisé : profil parsé intégré (fallback si aucun CV uploadé)';
			}
		}
		const resp = await fetch('/preview_lm_ai/' + jobId, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				additional_prompt: additionalPrompt,
				default_cv: defaultCv,
				ats_mode: document.getElementById('lmAtsMode') ? document.getElementById('lmAtsMode').checked : false,
				include_sections: _getCheckedSections('lm'),
				selected_education: _getSelectedEducation('lm'),
				selected_certificates: _getSelectedCertificates('lm'),
				selected_skills: _getSelectedSkills('lm'),
				selected_references: _getSelectedReferences('lm'),
				selected_projects: _getSelectedProjects('lm'),
				selected_premium_modules: _getCheckedValues('.lm-premium-check'),
			}),
		});
		const data = await readResponseJson(resp);
		if (!resp.ok) {
			if (data.profile_incomplete) {
				body.innerHTML =
					'<div class="alert alert-warning"><strong>⚠️ Profil incomplet :</strong> ' + escapeHtml(data.error) +
					'<div class="mt-3"><a href="/update_account/' + window.CAND_CONFIG.userId + '" class="btn btn-warning btn-sm">⚙️ Renseigner mes coordonnées</a></div></div>';
			} else {
				body.innerHTML =
					'<div class="alert alert-danger"><strong>Erreur :</strong> ' +
					(data.error || resp.statusText) + '</div>';
			}
			retryBtn.disabled = false;
			return;
		}
		currentLmAiText = data.text || '';
		// persist unsaved generated draft in localStorage so user can re-open modal and continue editing
		try {
			if (window.localStorage) {
				localStorage.setItem('lm_generated_' + jobId, currentLmAiText);
			}
		} catch (e) {
			// ignore storage errors (quota/private mode)
		}
		let lmHtml = '';
		if (_getCheckedSections('lm').length || _getSelectedEducation('lm').length || _getSelectedCertificates('lm').length || _getSelectedSkills('lm').length || _getSelectedReferences('lm').length || _getSelectedProjects('lm').length || _getCheckedValues('.lm-premium-check').length) {
			lmHtml += '<div class="alert alert-light border py-2 small mb-2">Sélections manuelles prises en compte pour adapter la lettre.</div>';
		}
		lmHtml += '<div style="white-space:pre-wrap">' + escapeHtml(currentLmAiText) + '</div>';
		body.innerHTML = lmHtml;
		insertBtn.classList.remove('d-none');
		retryBtn.textContent = '↻ Régénérer';
	} catch (err) {
		body.innerHTML =
			'<div class="alert alert-danger"><strong>Erreur réseau :</strong> ' +
			escapeHtml(err.message) + '</div>';
	} finally {
		retryBtn.disabled = false;
	}
}

function retryLmAiPreview() {
	if (currentLmAiJobId !== null) {
		loadLmAiPreview(currentLmAiJobId);
	}
}

function resetLmAiPrompt() {
	document.getElementById('lmAiAdditionalPrompt').value = '';
}

async function insertLmText() {
	if (!currentLmAiJobId || !currentLmAiText) return;
	const insertBtn = document.getElementById('lmAiInsertBtn');
	insertBtn.disabled = true;
	try {
		const resp = await fetch('/save_lm_text/' + currentLmAiJobId, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ text: currentLmAiText }),
		});
		const data = await readResponseJson(resp);
		if (resp.ok) {
			insertBtn.textContent = '✅ LM insérée !';
			setTimeout(() => {
				var modal = bootstrap.Modal.getInstance(document.getElementById('lmAiModal'));
				if (modal) modal.hide();
				location.reload();
			}, 1200);
		} else {
			alert('Erreur lors de l\'insertion : ' + (data.error || 'inconnue'));
			insertBtn.disabled = false;
		}
	} catch (err) {
		alert('Erreur réseau : ' + err.message);
		insertBtn.disabled = false;
	}
}

function escapeHtml(text) {
	if (!text) return '';
	return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function readResponseJson(response) {
	const text = await response.text();
	try {
		return JSON.parse(text);
	} catch (error) {
		return {
			error: response.ok
				? 'Réponse inattendue du serveur.'
				: 'Le serveur a rencontré une erreur (HTTP ' + response.status + ').',
		};
	}
}

function applyClosedFilter() {
	showClosed = document.getElementById('showClosed').checked;
	document.querySelectorAll('[data-closed]').forEach(el => {
		const isClosed = el.getAttribute('data-closed') === '1';
		if (isClosed && !showClosed) {
			el.classList.add('d-none');
		} else {
			el.classList.remove('d-none');
		}
	});

	// Re-order table rows in tbody according to data-order to preserve original sort
	try {
		const tbody = document.querySelector('table.table tbody');
		if (tbody) {
			const rows = Array.from(tbody.querySelectorAll('tr'));
			// server order is DESC (most recent first), sort client-side accordingly
			rows.sort((a, b) => Number(b.getAttribute('data-order') || 0) - Number(a.getAttribute('data-order') || 0));
			rows.forEach(r => tbody.appendChild(r)); // appendChild moves existing nodes
		}
	} catch (e) {
		console.debug('applyClosedFilter: table reorder failed', e);
	}

	// Re-order mobile cards container
	try {
		const cardsContainer = document.querySelector('.cand-cards');
		if (cardsContainer) {
			const cards = Array.from(cardsContainer.children).filter(c => c.hasAttribute('data-order'));
			// preserve server-side descending order
			cards.sort((a, b) => Number(b.getAttribute('data-order') || 0) - Number(a.getAttribute('data-order') || 0));
			cards.forEach(c => cardsContainer.appendChild(c));
		}
	} catch (e) {
		console.debug('applyClosedFilter: cards reorder failed', e);
	}
}

document.addEventListener('DOMContentLoaded', () => {
	// initial state (checkbox checked by default)
	const cb = document.getElementById('showClosed');
	if (cb) {
		cb.checked = false;
	}
	applyClosedFilter();
	initAdvancedSelectionSync();
});
