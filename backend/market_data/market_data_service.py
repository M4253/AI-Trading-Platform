"""Modular, no-key market intelligence providers with safe local fallbacks.

The service deliberately gathers public market context only.  It has no broker
imports, no order capability, and no paid-provider dependency.  Providers use
small protocols so a premium provider can replace a public provider later
without changing the scanner, dashboard, or AI-decision integration.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import math
import re
import statistics
import threading
import time
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


class ProviderUnavailable(RuntimeError):
    """Raised when one provider cannot return usable public data."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not re.fullmatch(r'[A-Z0-9.\-]{1,15}', normalized):
        raise ValueError('Symbol must contain only letters, numbers, dots, or hyphens')
    return normalized


@dataclass
class _CachedValue:
    value: Any
    expires_at: float


class TTLCache:
    """Small threadsafe in-memory TTL cache used for public provider responses."""

    def __init__(self) -> None:
        self._values: Dict[str, _CachedValue] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any:
        now = time.monotonic()
        with self._lock:
            cached = self._values.get(key)
            if cached and cached.expires_at > now:
                self.hits += 1
                return cached.value
            if cached:
                self._values.pop(key, None)
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> Any:
        with self._lock:
            self._values[key] = _CachedValue(value=value, expires_at=time.monotonic() + ttl_seconds)
        return value

    def metrics(self) -> Dict[str, int]:
        with self._lock:
            return {'entries': len(self._values), 'hits': self.hits, 'misses': self.misses}


class MarketDataProvider(Protocol):
    name: str
    is_free: bool

    def get_daily_bars(self, symbol: str) -> List[Dict[str, Any]]:
        """Return ascending daily OHLCV bars for one symbol."""


class NewsProvider(Protocol):
    name: str
    is_free: bool

    def get_headlines(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent public headlines for one symbol."""


class EconomicCalendarProvider(Protocol):
    name: str
    is_free: bool

    def get_events(self, days: int = 14) -> List[Dict[str, Any]]:
        """Return upcoming economic events without requiring a provider key."""


def _public_http_text(url: str, timeout: float = 2.5) -> str:
    request = Request(url, headers={'User-Agent': 'AI-Trading-Platform/1.0 (public-data)'})
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed public provider URLs
            return response.read().decode('utf-8', errors='replace')
    except Exception as error:  # Public APIs should fall through to the next provider.
        raise ProviderUnavailable(str(error)) from error


class StooqMarketDataProvider:
    """No-key public daily-bar adapter for Stooq CSV data."""

    name = 'stooq_public'
    is_free = True

    def __init__(self, fetch_text: Callable[[str], str] = _public_http_text) -> None:
        self.fetch_text = fetch_text

    def get_daily_bars(self, symbol: str) -> List[Dict[str, Any]]:
        # Stooq's daily CSV endpoint is public and needs no token.  U.S.
        # equities use the conventional ``.us`` suffix.
        provider_symbol = f'{_symbol(symbol).lower()}.us'
        text = self.fetch_text(f'https://stooq.com/q/d/l/?s={quote_plus(provider_symbol)}&i=d')
        rows = list(csv.DictReader(io.StringIO(text)))
        bars = []
        for row in rows:
            close = _number(row.get('Close'), math.nan)
            if not math.isfinite(close):
                continue
            bars.append({
                'date': row.get('Date'),
                'open': _number(row.get('Open'), close),
                'high': _number(row.get('High'), close),
                'low': _number(row.get('Low'), close),
                'close': close,
                'volume': _number(row.get('Volume')),
            })
        if not bars:
            raise ProviderUnavailable('Stooq returned no usable daily bars')
        return sorted(bars, key=lambda bar: str(bar.get('date', '')))


class DeterministicMarketFallback:
    """Offline fallback that keeps UI and tests usable without claiming live data."""

    name = 'deterministic_local_fallback'
    is_free = True

    def get_daily_bars(self, symbol: str) -> List[Dict[str, Any]]:
        normalized = _symbol(symbol)
        digest = int(hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:8], 16)
        base_price = 40.0 + (digest % 26000) / 100.0
        trend = ((digest >> 8) % 9 - 4) / 1000.0
        bars: List[Dict[str, Any]] = []
        today = date.today()
        for offset in range(30):
            drift = trend * offset
            oscillation = math.sin((offset + digest % 7) / 3.0) * 0.006
            close = round(base_price * (1 + drift + oscillation), 2)
            opening = round(close * (1 - oscillation / 2), 2)
            bars.append({
                'date': (today - timedelta(days=29 - offset)).isoformat(),
                'open': opening,
                'high': round(max(opening, close) * 1.008, 2),
                'low': round(min(opening, close) * 0.992, 2),
                'close': close,
                'volume': 500_000 + (digest % 900_000),
                'is_fallback': True,
            })
        return bars


class GoogleNewsRssProvider:
    """No-key public RSS adapter for finance headlines."""

    name = 'google_news_rss'
    is_free = True

    def __init__(self, fetch_text: Callable[[str], str] = _public_http_text) -> None:
        self.fetch_text = fetch_text

    def get_headlines(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        normalized = _symbol(symbol)
        search_query = quote_plus(f'{normalized} stock')
        text = self.fetch_text(
            'https://news.google.com/rss/search?'
            f'q={search_query}&hl=en-US&gl=US&ceid=US:en'
        )
        try:
            root = element_tree.fromstring(text)
        except element_tree.ParseError as error:
            raise ProviderUnavailable('Google News RSS response was invalid') from error
        items = []
        for item in root.findall('.//item')[:max(1, min(limit, 25))]:
            title = (item.findtext('title') or '').strip()
            if title:
                items.append({
                    'headline': title,
                    'published_at': (item.findtext('pubDate') or '').strip() or None,
                    'url': (item.findtext('link') or '').strip() or None,
                    'source': self.name,
                })
        if not items:
            raise ProviderUnavailable('Google News RSS returned no headlines')
        return items


class NeutralNewsFallback:
    """Explicitly non-live fallback; avoids inventing bullish/bearish news."""

    name = 'neutral_local_fallback'
    is_free = True

    def get_headlines(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        return [{
            'headline': f'No live public news was available for {_symbol(symbol)}.',
            'source': self.name,
            'published_at': _now(),
            'is_fallback': True,
        }]


class FederalReserveCalendarProvider:
    """Best-effort, no-key adapter for the public FOMC meeting calendar page."""

    name = 'federal_reserve_fomc'
    is_free = True

    _MONTH_PATTERN = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'

    def __init__(self, fetch_text: Callable[[str], str] = _public_http_text) -> None:
        self.fetch_text = fetch_text

    def get_events(self, days: int = 14) -> List[Dict[str, Any]]:
        text = self.fetch_text('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm')
        plain_text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', text)))
        events = []
        sections = re.finditer(
            r'(20\d{2})\s+FOMC Meetings(.*?)(?=20\d{2}\s+FOMC Meetings|Future Year:|$)',
            plain_text,
            re.IGNORECASE,
        )
        for section in sections:
            year, schedule = section.group(1), section.group(2)
            meetings = re.findall(
                rf'({self._MONTH_PATTERN})\s+(\d{{1,2}}(?:[–-]\d{{1,2}})?\*?)\s+Statement',
                schedule,
            )
            events.extend({
                'event': 'Federal Reserve FOMC meeting',
                'date': f'{month} {days_text.rstrip("*")}, {year}',
                'impact': 'high',
                'source': self.name,
            } for month, days_text in meetings)
        # Keep a compact-date fallback for source mirrors and provider tests
        # that present dates in a single text token.
        if not events:
            dates = re.findall(rf'({self._MONTH_PATTERN}\s+\d{{1,2}}(?:[–-]\d{{1,2}})?,\s+\d{{4}})', plain_text)
            events = [
                {'event': 'Federal Reserve FOMC meeting', 'date': event_date, 'impact': 'high', 'source': self.name}
                for event_date in dates
            ]
        if not events:
            raise ProviderUnavailable('Federal Reserve calendar yielded no meeting dates')
        # Preserve the provider's published date range as text: it is safer
        # than guessing a timezone or an exact release timestamp from HTML.
        return events[:12]


class EmptyEconomicCalendarFallback:
    """Offline calendar fallback that transparently reports no live events."""

    name = 'empty_local_fallback'
    is_free = True

    def get_events(self, days: int = 14) -> List[Dict[str, Any]]:
        return []


class FinancialNewsSentimentAnalyzer:
    """Deterministic financial-news sentiment, replaceable by a model later."""

    positive_terms = ('beat', 'growth', 'upgrade', 'profit', 'bullish', 'surge', 'record', 'approval', 'raises guidance')
    negative_terms = ('miss', 'downgrade', 'loss', 'bearish', 'lawsuit', 'cut', 'decline', 'risk', 'probe')

    def analyze(self, item: Mapping[str, Any]) -> Dict[str, Any]:
        headline = str(item.get('headline') or item.get('title') or '')
        lower = headline.lower()
        positive = sum(term in lower for term in self.positive_terms)
        negative = sum(term in lower for term in self.negative_terms)
        score = _clamp((positive - negative) / 3.0, -1.0, 1.0)
        label = 'positive' if score > 0.1 else 'negative' if score < -0.1 else 'neutral'
        return {
            **dict(item),
            'sentiment_score': round(score, 3),
            'sentiment': label,
            'sentiment_confidence': round(min(1.0, (positive + negative) / 3.0), 3),
        }

    def summarize(self, items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        scored = [self.analyze(item) for item in items]
        score = statistics.fmean(item['sentiment_score'] for item in scored) if scored else 0.0
        return {
            'items': scored,
            'overall_score': round(score, 3),
            'overall_sentiment': 'positive' if score > 0.1 else 'negative' if score < -0.1 else 'neutral',
        }


def _indicators(bars: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    closes = [_number(bar.get('close'), math.nan) for bar in bars]
    closes = [close for close in closes if math.isfinite(close)]
    if not closes:
        return {'rsi': 50.0, 'trend_score': 0.0, 'volatility': 0.0}
    sma_5 = statistics.fmean(closes[-5:])
    sma_20 = statistics.fmean(closes[-20:])
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = statistics.fmean(gains) if gains else 0.0
    average_loss = statistics.fmean(losses) if losses else 0.0
    if average_loss == 0:
        rsi = 100.0 if average_gain else 50.0
    else:
        relative_strength = average_gain / average_loss
        rsi = 100.0 - 100.0 / (1.0 + relative_strength)
    returns = [changes[index] / closes[index] for index in range(len(changes)) if closes[index]]
    volatility = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    trend = _clamp((sma_5 / sma_20 - 1.0) * 20.0 if sma_20 else 0.0, -1.0, 1.0)
    return {
        'sma_5': round(sma_5, 4),
        'sma_20': round(sma_20, 4),
        'rsi': round(rsi, 2),
        'trend_score': round(trend, 4),
        'volatility': round(volatility, 5),
    }


class MarketIntelligenceService:
    """Composes provider fallbacks into dashboard and AI-ready market context."""

    def __init__(
        self,
        *,
        market_providers: Optional[Sequence[MarketDataProvider]] = None,
        news_providers: Optional[Sequence[NewsProvider]] = None,
        calendar_providers: Optional[Sequence[EconomicCalendarProvider]] = None,
        cache: Optional[TTLCache] = None,
    ) -> None:
        self.market_providers = list(market_providers or [StooqMarketDataProvider(), DeterministicMarketFallback()])
        self.news_providers = list(news_providers or [GoogleNewsRssProvider(), NeutralNewsFallback()])
        self.calendar_providers = list(calendar_providers or [FederalReserveCalendarProvider(), EmptyEconomicCalendarFallback()])
        self.cache = cache or TTLCache()
        self.sentiment = FinancialNewsSentimentAnalyzer()
        self.provider_status: Dict[str, Dict[str, Any]] = {}

    def _fallback(
        self,
        *, category: str,
        cache_key: str,
        providers: Sequence[Any],
        fetch: Callable[[Any], Any],
        ttl_seconds: int,
    ) -> Tuple[Any, str, bool]:
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached['value'], cached['provider'], True
        errors = []
        for provider in providers:
            try:
                value = fetch(provider)
                self.provider_status[provider.name] = {
                    'category': category,
                    'status': 'available',
                    'is_free': bool(provider.is_free),
                    'updated_at': _now(),
                }
                self.cache.set(cache_key, {'value': value, 'provider': provider.name}, ttl_seconds)
                return value, provider.name, False
            except Exception as error:
                errors.append(f'{provider.name}: {error}')
                self.provider_status[provider.name] = {
                    'category': category,
                    'status': 'unavailable',
                    'is_free': bool(provider.is_free),
                    'updated_at': _now(),
                    'message': str(error)[:200],
                }
        raise ProviderUnavailable('; '.join(errors) or f'No {category} provider is configured')

    def get_economic_calendar(self, days: int = 14) -> Dict[str, Any]:
        events, provider, cached = self._fallback(
            category='economic_calendar',
            cache_key=f'calendar:{max(1, min(days, 90))}',
            providers=self.calendar_providers,
            fetch=lambda item: item.get_events(days=max(1, min(days, 90))),
            ttl_seconds=60 * 60,
        )
        return {'events': events, 'provider': provider, 'cached': cached}

    def get_market_context(self, symbol: str) -> Dict[str, Any]:
        normalized = _symbol(symbol)
        context_cache_key = f'context:{normalized}'
        cached = self.cache.get(context_cache_key)
        if cached is not None:
            return {**cached, 'cached': True}

        bars, market_provider, market_cached = self._fallback(
            category='market_data',
            cache_key=f'market:{normalized}',
            providers=self.market_providers,
            fetch=lambda item: item.get_daily_bars(normalized),
            ttl_seconds=60,
        )
        bars = list(bars)[-60:]
        latest = bars[-1]
        indicators = _indicators(bars)
        headlines, news_provider, news_cached = self._fallback(
            category='news',
            cache_key=f'news:{normalized}',
            providers=self.news_providers,
            fetch=lambda item: item.get_headlines(normalized),
            ttl_seconds=5 * 60,
        )
        sentiment = self.sentiment.summarize(headlines)
        calendar = self.get_economic_calendar()
        high_impact_events = sum(event.get('impact') == 'high' for event in calendar['events'])
        economic_risk = _clamp(high_impact_events * 0.08, 0.0, 0.4)
        economic_signal = -economic_risk if high_impact_events else 0.0
        previous_close = _number(bars[-2].get('close'), _number(latest.get('close'))) if len(bars) > 1 else _number(latest.get('close'))
        close = _number(latest.get('close'))
        change_pct = ((close / previous_close) - 1.0) if previous_close else 0.0
        market_data = {
            'open': _number(latest.get('open'), close),
            'high': _number(latest.get('high'), close),
            'low': _number(latest.get('low'), close),
            'close': close,
            'volume': _number(latest.get('volume')),
            'volatility': indicators['volatility'],
            'price_history': [bar['close'] for bar in bars],
            'economic_signal': economic_signal,
            'economic_risk': economic_risk,
            'economic_events': calendar['events'],
        }
        provider_names = {'market_data': market_provider, 'news': news_provider, 'economic_calendar': calendar['provider']}
        is_fallback = any('fallback' in name for name in provider_names.values())
        health = {
            'status': 'degraded' if is_fallback else 'healthy',
            'market_data_provider': market_provider,
            'news_provider': news_provider,
            'economic_calendar_provider': calendar['provider'],
            'is_fallback': is_fallback,
            'cached_sources': {'market_data': market_cached, 'news': news_cached, 'economic_calendar': calendar['cached']},
            'updated_at': _now(),
        }
        context = {
            'symbol': normalized,
            'quote': {
                'symbol': normalized,
                'price': close,
                'change_pct': round(change_pct * 100, 2),
                'as_of': latest.get('date'),
                'provider': market_provider,
            },
            'chart_data': {'closes': market_data['price_history'], 'bars': bars},
            'market_data': market_data,
            'indicators': indicators,
            'news': sentiment['items'],
            'news_sentiment': {'score': sentiment['overall_score'], 'label': sentiment['overall_sentiment']},
            'economic_calendar': calendar,
            'market_health': health,
            'ai_context': {
                'symbol': normalized,
                'current_price': close,
                'market_data': market_data,
                'chart_data': {'closes': market_data['price_history']},
                'indicators': indicators,
                'news': sentiment['items'],
            },
            'cached': False,
        }
        self.cache.set(context_cache_key, context, 45)
        return context

    def scan(self, symbols: Sequence[str]) -> Dict[str, Any]:
        normalized_symbols = []
        for symbol in symbols[:50]:
            normalized = _symbol(symbol)
            if normalized not in normalized_symbols:
                normalized_symbols.append(normalized)
        results = []
        for symbol in normalized_symbols:
            try:
                context = self.get_market_context(symbol)
                trend = _number(context['indicators'].get('trend_score'))
                sentiment = _number(context['news_sentiment'].get('score'))
                economic_risk = _number(context['market_data'].get('economic_risk'))
                score = _clamp(50 + trend * 30 + sentiment * 20 - economic_risk * 20, 0, 100)
                results.append({
                    'symbol': symbol,
                    'price': context['quote']['price'],
                    'change_pct': context['quote']['change_pct'],
                    'trend_score': trend,
                    'news_sentiment': sentiment,
                    'economic_risk': economic_risk,
                    'scanner_score': round(score, 2),
                    'market_health': context['market_health']['status'],
                })
            except Exception as error:
                results.append({'symbol': symbol, 'error': str(error)})
        results.sort(key=lambda result: result.get('scanner_score', -1), reverse=True)
        return {'results': results, 'count': len(results), 'paper_only': True}

    def health(self) -> Dict[str, Any]:
        configured = [
            *({'name': provider.name, 'category': 'market_data', 'is_free': provider.is_free} for provider in self.market_providers),
            *({'name': provider.name, 'category': 'news', 'is_free': provider.is_free} for provider in self.news_providers),
            *({'name': provider.name, 'category': 'economic_calendar', 'is_free': provider.is_free} for provider in self.calendar_providers),
        ]
        provider_states = [{**provider, **self.provider_status.get(provider['name'], {'status': 'not_checked'})} for provider in configured]
        unavailable = [provider for provider in provider_states if provider['status'] == 'unavailable']
        checked = [provider for provider in provider_states if provider['status'] != 'not_checked']
        return {
            'status': 'degraded' if unavailable else 'healthy' if checked else 'unknown',
            'providers': provider_states,
            'cache': self.cache.metrics(),
            'paid_api_required': False,
            'paper_only': True,
        }
