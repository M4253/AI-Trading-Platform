"""Phase 10 coverage for providers, caching, watchlists, scanner, and AI bridge."""
import inspect
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.db import db as db_module
from backend.db.ai_db import get_ai_decision, init_ai_db
from backend.main import app
from backend.market_data import routes as market_routes
from backend.market_data.market_data_service import (
    EmptyEconomicCalendarFallback,
    FederalReserveCalendarProvider,
    FinancialNewsSentimentAnalyzer,
    GoogleNewsRssProvider,
    MarketIntelligenceService,
    ProviderUnavailable,
    StooqMarketDataProvider,
)
from backend.market_data import market_data_service
from backend.market_data.watchlists import (
    add_symbol,
    create_watchlist,
    delete_watchlist,
    list_watchlists,
    remove_symbol,
    rename_watchlist,
)
from backend.paper_trading.paper_engine import PaperTradingEngine


class FailingMarketProvider:
    name = 'failing_market'
    is_free = True

    def get_daily_bars(self, symbol):
        raise ProviderUnavailable('public market source unavailable')


class FixtureMarketProvider:
    name = 'fixture_market'
    is_free = True

    def __init__(self):
        self.calls = 0

    def get_daily_bars(self, symbol):
        self.calls += 1
        start = date(2026, 7, 1)
        return [
            {
                'date': (start + timedelta(days=index)).isoformat(),
                'open': 100 + index,
                'high': 101 + index,
                'low': 99 + index,
                'close': 100.5 + index,
                'volume': 1_000_000 + index,
            }
            for index in range(25)
        ]


class FixtureNewsProvider:
    name = 'fixture_news'
    is_free = True

    def __init__(self):
        self.calls = 0

    def get_headlines(self, symbol, limit=10):
        self.calls += 1
        return [
            {'headline': f'{symbol} reports record profit growth and receives an upgrade', 'source': self.name},
            {'headline': f'{symbol} maintains guidance', 'source': self.name},
        ]


class FixtureCalendarProvider:
    name = 'fixture_calendar'
    is_free = True

    def __init__(self):
        self.calls = 0

    def get_events(self, days=14):
        self.calls += 1
        return [{'event': 'Central bank decision', 'date': '2026-07-22', 'impact': 'high', 'source': self.name}]


@pytest.fixture
def intelligence():
    return MarketIntelligenceService(
        market_providers=[FailingMarketProvider(), FixtureMarketProvider()],
        news_providers=[FixtureNewsProvider()],
        calendar_providers=[FixtureCalendarProvider(), EmptyEconomicCalendarFallback()],
    )


def test_public_provider_csv_and_calendar_adapters_are_replaceable_without_keys():
    csv_text = 'Date,Open,High,Low,Close,Volume\n2026-07-01,100,105,99,104,1200\n'
    bars = StooqMarketDataProvider(fetch_text=lambda _: csv_text).get_daily_bars('AAPL')
    assert bars == [{'date': '2026-07-01', 'open': 100.0, 'high': 105.0, 'low': 99.0, 'close': 104.0, 'volume': 1200.0}]
    headlines = GoogleNewsRssProvider(
        fetch_text=lambda _: '<rss><channel><item><title>AAPL profit growth</title><link>https://example.test/aapl</link></item></channel></rss>'
    ).get_headlines('AAPL')
    assert headlines[0]['headline'] == 'AAPL profit growth'

    events = FederalReserveCalendarProvider(
        fetch_text=lambda _: '<p>January 27-28, 2026</p><p>March 17–18, 2026</p>'
    ).get_events()
    assert events[0]['event'] == 'Federal Reserve FOMC meeting'
    assert events[0]['impact'] == 'high'
    rendered_events = FederalReserveCalendarProvider(
        fetch_text=lambda _: '<h4>2026 FOMC Meetings</h4><p>July</p><p>28-29</p><p>Statement:</p>'
    ).get_events()
    assert rendered_events[0]['date'] == 'July 28-29, 2026'


def test_provider_fallback_cache_and_market_context(intelligence):
    fixture_market = intelligence.market_providers[1]
    fixture_news = intelligence.news_providers[0]
    first = intelligence.get_market_context('AAPL')
    second = intelligence.get_market_context('AAPL')

    assert first['market_health']['market_data_provider'] == 'fixture_market'
    assert first['news_sentiment']['label'] == 'positive'
    assert first['economic_calendar']['events'][0]['impact'] == 'high'
    assert first['ai_context']['indicators']['rsi'] > 50
    assert second['cached'] is True
    assert fixture_market.calls == 1
    assert fixture_news.calls == 1
    health = intelligence.health()
    assert any(provider['name'] == 'failing_market' and provider['status'] == 'unavailable' for provider in health['providers'])
    assert health['cache']['hits'] >= 1


def test_financial_sentiment_handles_positive_negative_and_neutral_headlines():
    analyzer = FinancialNewsSentimentAnalyzer()
    positive = analyzer.analyze({'headline': 'Record profit growth leads to an upgrade'})
    negative = analyzer.analyze({'headline': 'Earnings miss prompts downgrade and loss warning'})
    neutral = analyzer.analyze({'headline': 'Company hosts investor presentation'})

    assert positive['sentiment'] == 'positive'
    assert negative['sentiment'] == 'negative'
    assert neutral['sentiment'] == 'neutral'


def test_market_intelligence_has_no_broker_or_paid_key_dependency():
    source = inspect.getsource(market_data_service)
    assert 'IBKRBroker' not in source
    assert 'ib_insync' not in source
    assert 'BrokerService' not in source
    assert 'api_key=' not in source


def test_watchlist_and_symbol_management_is_persistent_and_validated(tmp_path):
    db_path = str(tmp_path / 'watchlists.db')
    default = list_watchlists(db_path)
    assert default[0]['name'] == 'Default Watchlist'

    created = create_watchlist('Technology', db_path)
    assert add_symbol(created['id'], 'aapl', db_path)['symbols'] == ['AAPL']
    assert add_symbol(created['id'], 'MSFT', db_path)['symbols'] == ['AAPL', 'MSFT']
    assert remove_symbol(created['id'], 'AAPL', db_path)['symbols'] == ['MSFT']
    assert rename_watchlist(created['id'], 'Large Cap', db_path)['name'] == 'Large Cap'
    assert delete_watchlist(created['id'], db_path) is True
    with pytest.raises(ValueError, match='Symbol'):
        add_symbol(default[0]['id'], 'bad symbol!', db_path)


def test_scanner_ranks_fixture_context_and_marks_paper_only(intelligence):
    scan = intelligence.scan(['MSFT', 'AAPL'])

    assert scan['count'] == 2
    assert scan['paper_only'] is True
    assert all('scanner_score' in result for result in scan['results'])
    assert scan['results'][0]['scanner_score'] >= scan['results'][1]['scanner_score']


def test_market_routes_watchlists_scanner_and_ai_context_bridge(monkeypatch, tmp_path, intelligence):
    db_path = str(tmp_path / 'market_routes.db')
    monkeypatch.setattr(db_module, 'DEFAULT_DB', db_path)
    monkeypatch.setattr(market_routes, '_market_intelligence', intelligence)
    init_ai_db(db_path)
    PaperTradingEngine(db_path=db_path).start_trading()
    client = TestClient(app)

    watchlists = client.get('/market/watchlists')
    assert watchlists.status_code == 200
    watchlist_id = watchlists.json()['watchlists'][0]['id']
    assert client.post(f'/market/watchlists/{watchlist_id}/symbols', json={'symbol': 'AAPL'}).status_code == 200

    context = client.get('/market/context/AAPL')
    assert context.status_code == 200
    assert context.json()['ai_context']['market_data']['economic_events']
    assert context.json()['news'][0]['sentiment_score'] > 0

    scanner = client.post('/market/scanner', json={'watchlist_id': watchlist_id})
    assert scanner.status_code == 200
    assert scanner.json()['results'][0]['symbol'] == 'AAPL'

    decision_response = client.post('/market/ai-decisions/AAPL')
    assert decision_response.status_code == 201
    decision = decision_response.json()['decision']
    stored = get_ai_decision(decision['id'], db_path)
    assert stored['decision_type'] == 'market_intelligence'
    assert stored['context']['market_data']['economic_events']
    assert stored['context']['news'][0]['sentiment_score'] > 0
    assert 'economic signal' in decision['rationale']
    assert decision_response.json()['paper_only'] is True
