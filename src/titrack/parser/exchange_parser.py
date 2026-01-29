"""Parser for exchange/auction house price messages."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional


class ExchangeMessageType(Enum):
    """Type of exchange message."""

    SEND_SEARCH = auto()  # Price search request
    RECV_SEARCH = auto()  # Price search response


@dataclass
class ExchangePriceRequest:
    """Parsed exchange price search request."""

    syn_id: int
    config_base_id: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExchangePriceResponse:
    """Parsed exchange price search response."""

    syn_id: int
    prices_fe: list[float]  # Unit prices in FE, sorted low to high
    timestamp: datetime = field(default_factory=datetime.now)


# Patterns for exchange messages
SEND_START_PATTERN = re.compile(
    r"----Socket SendMessage STT----XchgSearchPrice----SynId = (\d+)"
)
RECV_START_PATTERN = re.compile(
    r"----Socket RecvMessage STT----XchgSearchPrice----SynId = (\d+)"
)
MESSAGE_END_PATTERN = re.compile(r"----Socket (?:Send|Recv)Message End----")

# Pattern to extract refer (ConfigBaseId) from request
REFER_PATTERN = re.compile(r"\+refer \[(\d+)\]")

# Pattern to extract currency from response (can appear before or after prices)
# Old format: +prices+1+currency [100300]
# New format: |      | +currency [100300]  (at end of price list)
CURRENCY_PATTERN = re.compile(r"\+currency \[(\d+)\]")

# Match both "+unitPrices+N [price]" and continuation lines "+N [price]"
UNIT_PRICE_PATTERN = re.compile(r"\+(?:unitPrices\+)?\d+ \[([0-9.]+)\]")

# Pattern to detect start of a new price section (prices+N+unitPrices)
PRICES_SECTION_START = re.compile(r"\+prices\+\d+\+unitPrices")

# FE currency ConfigBaseId
FE_CURRENCY_ID = 100300


class ExchangeMessageParser:
    """
    Stateful parser for multi-line exchange messages.

    Exchange messages span multiple lines:
    1. Start marker with SynId
    2. Message body (tree structure)
    3. End marker

    This parser accumulates lines and emits parsed events.
    """

    def __init__(self) -> None:
        self._in_message = False
        self._message_type: Optional[ExchangeMessageType] = None
        self._syn_id: Optional[int] = None
        self._lines: list[str] = []

    def parse_line(self, line: str) -> Optional[ExchangePriceRequest | ExchangePriceResponse]:
        """
        Parse a single line, potentially returning a completed message.

        Args:
            line: Raw log line

        Returns:
            Parsed request/response if message is complete, None otherwise
        """
        # Check for start markers
        send_match = SEND_START_PATTERN.search(line)
        if send_match:
            self._start_message(ExchangeMessageType.SEND_SEARCH, int(send_match.group(1)))
            return None

        recv_match = RECV_START_PATTERN.search(line)
        if recv_match:
            self._start_message(ExchangeMessageType.RECV_SEARCH, int(recv_match.group(1)))
            return None

        # Check for end marker
        if MESSAGE_END_PATTERN.search(line):
            return self._finish_message()

        # Accumulate lines if in message
        if self._in_message:
            self._lines.append(line)

        return None

    def _start_message(self, msg_type: ExchangeMessageType, syn_id: int) -> None:
        """Start accumulating a new message."""
        self._in_message = True
        self._message_type = msg_type
        self._syn_id = syn_id
        self._lines = []

    def _finish_message(self) -> Optional[ExchangePriceRequest | ExchangePriceResponse]:
        """Finish and parse the accumulated message."""
        if not self._in_message:
            return None

        result = None
        content = "\n".join(self._lines)

        if self._message_type == ExchangeMessageType.SEND_SEARCH:
            result = self._parse_request(content)
        elif self._message_type == ExchangeMessageType.RECV_SEARCH:
            result = self._parse_response(content)

        # Reset state
        self._in_message = False
        self._message_type = None
        self._syn_id = None
        self._lines = []

        return result

    def _parse_request(self, content: str) -> Optional[ExchangePriceRequest]:
        """Parse a price search request."""
        refer_match = REFER_PATTERN.search(content)
        if not refer_match:
            return None

        config_base_id = int(refer_match.group(1))

        return ExchangePriceRequest(
            syn_id=self._syn_id,
            config_base_id=config_base_id,
        )

    def _parse_response(self, content: str) -> Optional[ExchangePriceResponse]:
        """Parse a price search response, extracting FE prices.

        Handles two formats:
        - Old: currency comes before prices (+prices+1+currency [100300] then +unitPrices)
        - New: currency comes after prices (+prices+1+unitPrices... then +currency [100300])
        """
        prices_fe = []
        lines = content.split("\n")

        # Track current section state
        current_section_prices: list[float] = []
        current_section_is_fe: Optional[bool] = None  # None = unknown yet

        for line in lines:
            # Check for start of new price section (new format: +prices+N+unitPrices)
            if PRICES_SECTION_START.search(line):
                # Finalize previous section if we had prices and knew the currency
                if current_section_prices and current_section_is_fe:
                    prices_fe.extend(current_section_prices)
                # Start new section
                current_section_prices = []
                current_section_is_fe = None

            # Check for currency marker
            currency_match = CURRENCY_PATTERN.search(line)
            if currency_match:
                currency_id = int(currency_match.group(1))
                is_fe = (currency_id == FE_CURRENCY_ID)

                if current_section_prices:
                    # New format: prices came first, now we know the currency
                    if is_fe:
                        prices_fe.extend(current_section_prices)
                    current_section_prices = []
                    current_section_is_fe = None
                else:
                    # Old format: currency comes first, prices will follow
                    current_section_is_fe = is_fe
                continue

            # Extract unit prices
            price_match = UNIT_PRICE_PATTERN.search(line)
            if price_match:
                price = float(price_match.group(1))
                if current_section_is_fe is True:
                    # Old format: we already know this is FE section
                    prices_fe.append(price)
                else:
                    # New format or unknown: collect prices, determine currency later
                    current_section_prices.append(price)

        if not prices_fe:
            return None

        return ExchangePriceResponse(
            syn_id=self._syn_id,
            prices_fe=prices_fe,
        )


def calculate_reference_price(prices: list[float], method: str = "percentile_10") -> float:
    """
    Calculate a reference price from a list of prices.

    Args:
        prices: List of unit prices, assumed sorted low to high
        method: Calculation method:
            - "lowest": Use lowest price
            - "percentile_10": Use 10th percentile (good balance)
            - "percentile_20": Use 20th percentile
            - "median": Use median price
            - "mean_low_20": Mean of lowest 20%

    Returns:
        Reference price in FE
    """
    if not prices:
        return 0.0

    n = len(prices)

    if method == "lowest":
        return prices[0]
    elif method == "percentile_10":
        idx = max(0, int(n * 0.10) - 1)
        return prices[idx]
    elif method == "percentile_20":
        idx = max(0, int(n * 0.20) - 1)
        return prices[idx]
    elif method == "median":
        if n % 2 == 0:
            return (prices[n // 2 - 1] + prices[n // 2]) / 2
        return prices[n // 2]
    elif method == "mean_low_20":
        count = max(1, int(n * 0.20))
        return sum(prices[:count]) / count
    else:
        # Default to 10th percentile
        idx = max(0, int(n * 0.10) - 1)
        return prices[idx]
