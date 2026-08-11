"""WhatsAppNotifier implementation for sending fund analysis updates."""

import datetime
from pathlib import Path
from typing import List, Tuple


class WhatsAppNotifier:
    """
    Handles generation of investment recommendation messages
    and persists them for potential WhatsApp integration.
    """

    def __init__(self, output_dir: str) -> None:
        """
        Initialize the notifier with the output directory.

        Args:
            output_dir: Directory where generated messages will be saved.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.message_file = self.output_dir / "whatsapp_message.txt"

    def generate_message(self, allocations: List[Tuple[str, int]]) -> str:
        """
        Generate a WhatsApp-ready investment recommendation message.

        The message is formatted with fund names, allocations,
        and summary statistics.

        Args:
            allocations: List of (fund_name, allocation) tuples.

        Returns:
            Formatted message string.
        """
        # Header
        lines = [
            "💡 Investment Recommendation",
            f"📅 {datetime.date.today().strftime('%d %B %Y')}",
            "",
            "🏆 Recommended Funds:",
            ""
        ]

        # Fund allocations sorted by allocation amount descending
        sorted_allocations = sorted(allocations, key=lambda x: x[1], reverse=True)
        for name, amount in sorted_allocations:
            lines.append(f"• {name}: {amount:,} LKR")

        # Totals and footers
        total_allocation = sum(amount for _, amount in allocations)
        lines.extend([
            "",
            f"💰 Total Monthly Allocation: {total_allocation:,} LKR",
            "",
            "📊 Growth Basis: Price Acceleration Phase",
            "📈 Pattern Validation: Price Growth Confirmed",
        ])

        return "\n".join(lines)

    def save_message(self, message: str) -> None:
        """
        Persist the generated message to a file.

        Args:
            message: The message string to write.
        """
        with self.message_file.open("w", encoding="utf-8") as f:
            f.write(message)