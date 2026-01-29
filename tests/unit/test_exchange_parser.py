"""Tests for exchange price parser."""

import pytest

from titrack.parser.exchange_parser import (
    ExchangeMessageParser,
    ExchangePriceRequest,
    ExchangePriceResponse,
    calculate_reference_price,
)


class TestExchangeMessageParser:
    """Tests for multi-line exchange message parsing."""

    def test_parse_search_request(self):
        """Test parsing a price search request."""
        parser = ExchangeMessageParser()

        lines = [
            "[2026.01.26-19.35.20:148][572]GameLog: Display: [Game] ----Socket SendMessage STT----XchgSearchPrice----SynId = 23444",
            "[2026.01.26-19.35.20:148][572]GameLog: Display: [Game] ",
            "+filters+1+key [4]",
            "|       | +refer [5028]",
            "+typ3 [63]",
            "[2026.01.26-19.35.20:148][572]GameLog: Display: [Game] ----Socket SendMessage End----",
        ]

        result = None
        for line in lines:
            result = parser.parse_line(line)
            if result is not None:
                break

        assert result is not None
        assert isinstance(result, ExchangePriceRequest)
        assert result.syn_id == 23444
        assert result.config_base_id == 5028

    def test_parse_search_response_new_format(self):
        """Test parsing a price search response with new format (currency after prices)."""
        parser = ExchangeMessageParser()

        lines = [
            "[2026.01.28-09.58.21:887][818]GameLog: Display: [Game] ----Socket RecvMessage STT----XchgSearchPrice----SynId = 13366",
            "[2026.01.28-09.58.21:887][818]GameLog: Display: [Game] ",
            "+errCode",
            "+prices+1+unitPrices+1 [15.0]",
            "|      | |          +2 [15.5]",
            "|      | |          +3 [15.6]",
            "|      | +currency [100300]",
            "[2026.01.28-09.58.21:887][818]GameLog: Display: [Game] ----Socket RecvMessage End----",
        ]

        result = None
        for line in lines:
            result = parser.parse_line(line)
            if result is not None:
                break

        assert result is not None
        assert isinstance(result, ExchangePriceResponse)
        assert result.syn_id == 13366
        assert len(result.prices_fe) == 3
        assert result.prices_fe[0] == 15.0
        assert result.prices_fe[1] == 15.5
        assert result.prices_fe[2] == 15.6

    def test_parse_search_response_old_format(self):
        """Test parsing a price search response with old format (currency before prices)."""
        parser = ExchangeMessageParser()

        lines = [
            "[2026.01.26-19.35.20:391][607]GameLog: Display: [Game] ----Socket RecvMessage STT----XchgSearchPrice----SynId = 23444",
            "[2026.01.26-19.35.20:391][607]GameLog: Display: [Game] ",
            "+errCode",
            "+prices+1+currency [100300]",
            "|      | +unitPrices+1 [0.02]",
            "|      | |          +2 [0.021]",
            "|      | |          +3 [0.022]",
            "|      +2+currency [100200]",
            "|      | +unitPrices+1 [100.0]",
            "[2026.01.26-19.35.20:391][607]GameLog: Display: [Game] ----Socket RecvMessage End----",
        ]

        result = None
        for line in lines:
            result = parser.parse_line(line)
            if result is not None:
                break

        assert result is not None
        assert isinstance(result, ExchangePriceResponse)
        assert result.syn_id == 23444
        assert len(result.prices_fe) == 3
        assert result.prices_fe[0] == 0.02
        assert result.prices_fe[1] == 0.021
        assert result.prices_fe[2] == 0.022

    def test_ignores_non_fe_currency(self):
        """Test that only FE (100300) prices are captured."""
        parser = ExchangeMessageParser()

        # New format: prices first, then currency
        lines = [
            "----Socket RecvMessage STT----XchgSearchPrice----SynId = 100",
            "+errCode",
            "+prices+1+unitPrices+1 [100.0]",
            "|      | +currency [100200]",  # Not FE
            "----Socket RecvMessage End----",
        ]

        result = None
        for line in lines:
            result = parser.parse_line(line)
            if result is not None:
                break

        # Should return None because no FE prices found
        assert result is None

    def test_multiple_messages_sequentially(self):
        """Test parsing multiple messages in sequence."""
        parser = ExchangeMessageParser()

        # First request
        lines1 = [
            "----Socket SendMessage STT----XchgSearchPrice----SynId = 1",
            "+filters+1+key [4]",
            "|       | +refer [1001]",
            "----Socket SendMessage End----",
        ]

        result1 = None
        for line in lines1:
            result1 = parser.parse_line(line) or result1

        assert isinstance(result1, ExchangePriceRequest)
        assert result1.config_base_id == 1001

        # Second request
        lines2 = [
            "----Socket SendMessage STT----XchgSearchPrice----SynId = 2",
            "+filters+1+key [4]",
            "|       | +refer [2002]",
            "----Socket SendMessage End----",
        ]

        result2 = None
        for line in lines2:
            result2 = parser.parse_line(line) or result2

        assert isinstance(result2, ExchangePriceRequest)
        assert result2.config_base_id == 2002


class TestCalculateReferencePrice:
    """Tests for reference price calculation."""

    def test_lowest(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert calculate_reference_price(prices, "lowest") == 1.0

    def test_percentile_10(self):
        # 100 prices from 1 to 100
        prices = [float(i) for i in range(1, 101)]
        # 10th percentile of 100 items is index 9 (10th item)
        result = calculate_reference_price(prices, "percentile_10")
        assert result == 10.0

    def test_percentile_20(self):
        prices = [float(i) for i in range(1, 101)]
        result = calculate_reference_price(prices, "percentile_20")
        assert result == 20.0

    def test_median_odd(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert calculate_reference_price(prices, "median") == 3.0

    def test_median_even(self):
        prices = [1.0, 2.0, 3.0, 4.0]
        assert calculate_reference_price(prices, "median") == 2.5

    def test_mean_low_20(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        # Lowest 20% is first 2 items: (1+2)/2 = 1.5
        result = calculate_reference_price(prices, "mean_low_20")
        assert result == 1.5

    def test_empty_prices(self):
        assert calculate_reference_price([], "median") == 0.0

    def test_single_price(self):
        prices = [5.0]
        assert calculate_reference_price(prices, "percentile_10") == 5.0
        assert calculate_reference_price(prices, "median") == 5.0

    def test_realistic_exchange_prices(self):
        """Test with realistic exchange prices like the sample."""
        prices = [
            0.02002002002002,
            0.02002002002002,
            0.02049622437972,
            0.021021021021021,
            0.021021021021021,
            0.021021021021021,
            0.021021021021021,
            0.021021021021021,
            0.021021021021021,
            0.021021021021021,
        ]
        # 10th percentile of 10 items - index 0
        result = calculate_reference_price(prices, "percentile_10")
        assert result == pytest.approx(0.02002002002002)
