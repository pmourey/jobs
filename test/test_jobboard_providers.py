import pytest

from tools.jobboard_providers import JoobleProvider, ProviderError


def test_jooble_posts_documented_payload_and_normalizes_jobs(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'jobs': [{
                    'id': 'job-1',
                    'title': 'Ingénieur DevOps',
                    'company': 'Acme',
                    'location': 'Nice',
                    'link': 'https://example.test/job-1',
                    'snippet': 'Automatiser les déploiements',
                    'updated': '2026-11-15',
                }]
            }

    def fake_post(url, **kwargs):
        captured['url'] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr('tools.jobboard_providers.requests.post', fake_post)
    offers = JoobleProvider(api_key='secret', base_url='https://fr.jooble.org/api').search_offers(
        q='DevOps Python',
        location='Alpes-Maritimes',
        page=2,
    )

    assert captured['url'] == 'https://fr.jooble.org/api/secret'
    assert captured['json'] == {
        'keywords': 'DevOps Python',
        'location': 'Alpes-Maritimes',
        'page': 2,
    }
    assert captured['headers']['Content-Type'] == 'application/json'
    assert offers[0]['intitule'] == 'Ingénieur DevOps'
    assert offers[0]['description'] == 'Automatiser les déploiements'
    assert offers[0]['url'] == 'https://example.test/job-1'


def test_jooble_requires_api_key():
    with pytest.raises(ProviderError, match='JOOBLE_API_KEY'):
        JoobleProvider(api_key='').search_offers(q='python')


def test_jooble_uses_french_api_endpoint_by_default(monkeypatch):
    monkeypatch.delenv('JOOBLE_BASE_URL', raising=False)
    assert JoobleProvider(api_key='secret').base_url == 'https://fr.jooble.org/api'
    assert JoobleProvider(
        api_key='secret',
        base_url='https://jooble.org/api',
    ).base_url == 'https://fr.jooble.org/api'


def test_jooble_rejects_invalid_jobs_response(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {'jobs': {}}

    monkeypatch.setattr(
        'tools.jobboard_providers.requests.post',
        lambda *args, **kwargs: Response(),
    )

    with pytest.raises(ProviderError, match='invalid jobs list'):
        JoobleProvider(api_key='secret').search_offers(q='python')


def test_jooble_normalizes_fractional_second_timestamp(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {'jobs': [{'title': 'Python', 'updated': '2026-11-15T15:16:34.2900000'}]}

    monkeypatch.setattr(
        'tools.jobboard_providers.requests.post',
        lambda *args, **kwargs: Response(),
    )

    offers = JoobleProvider(api_key='secret').search_offers(q='python')
    assert offers[0]['dateCreation'] == '2026-11-15 15:16:34'
