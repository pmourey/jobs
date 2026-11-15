import flask_app
from flask_app import _keywords_to_query


def test_keywords_query_deduplicates_and_uses_api_length_limit():
    assert _keywords_to_query([
        'Directeur de projet',
        'Manager Innovation',
        'Directeur de projet',
    ]) == 'Directeur de projet Manager Innovation'

    query = _keywords_to_query([
        'Directeur de projet',
        'Manager Innovation',
        'Knowledge Manager',
        'Directeur Général',
        'Chef de Projet',
        'Pilotage Stratégique',
        'Management Transition',
        'Directeur Opérationnel',
    ])
    assert len(query) <= 100
    assert query.endswith('Chef de Projet')


def test_provider_searches_each_keyword_separately_for_or(monkeypatch):
    calls = []

    def fake_search(provider, **kwargs):
        calls.append(kwargs['mots_cles'])
        return [{'id': kwargs['mots_cles'], 'intitule': kwargs['mots_cles']}]

    monkeypatch.setattr(flask_app, '_search_job_offer_provider', fake_search)
    offers = flask_app._search_job_offer_provider_or(
        'france_travail',
        client_id='id',
        client_secret='secret',
        keywords=['Directeur de projet', 'Manager Innovation'],
    )
    assert calls == ['Directeur de projet', 'Manager Innovation']
    assert [offer['id'] for offer in offers] == calls


def test_provider_groups_jooble_keywords_to_conserve_daily_quota(monkeypatch):
    calls = []

    def fake_search(provider, **kwargs):
        calls.append(kwargs['mots_cles'])
        return [{'id': 'job-1', 'intitule': 'DevOps'}]

    monkeypatch.setattr(flask_app, '_search_job_offer_provider', fake_search)
    offers = flask_app._search_job_offer_provider_or(
        'jooble',
        client_id='',
        client_secret='',
        keywords=['DevOps', 'Python', 'Kubernetes'],
    )

    assert calls == ['DevOps Python Kubernetes']
    assert len(offers) == 1
