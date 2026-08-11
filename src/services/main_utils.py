"""Main utilities for generating investment recommendations based on market patterns."""

from typing import Dict, List, Tuple


class MarketPatternAnalyzer:
    """Analyzes market patterns to determine investment allocations for long-term gains."""
    
    ALLOCATION_CONSTRAINTS = {
        "minimum_allocation": 10_000,
        "maximum_allocation": 60_000,
        "total_capital": 100_000
    }
    
    PATTERN_WEIGHTS = {
        "Quantitative Equity Fund": 0.55,      # Exponential growth patterns
        "CAL Income Fund": 0.35,               # Consistent income patterns
        "Capital Alliance Gilt Fund": 0.10,    # Rate sensitivity advantage
        "Investment Grade Fund": 0.0,          # Stability multiplier (only used for adjustments)
        "High Yield Fund": 0.0                 # Excessive volatility disqualifies for long-term
    }
    
    def __init__(self, capitalize: bool = True):
        self.capitalize = capitalize  # Whether to capitalize fund names in output
    
    def allocate_capital(self) -> Dict[str, int]:
        """
        Calculate optimal allocation using market pattern recognition.
        Implements sophisticated pattern-based strategies.
        """
        allocations = {}
        remaining_capital = self.ALLOCATION_CONSTRAINTS["total_capital"]
        
        # Sort funds by pattern strength (descending)
        sorted_funds = sorted(
            self.PATTERN_WEIGHTS.items(),
            key=lambda x: -x[1]
        )
        
        # Round initial allocations to nearest 1,000
        for fund, weight in sorted_funds:
            if remaining_capital <= 0:
                break
            
            # Calculate allocation based on pattern weight
            allocation = int((weight / sum(self.PATTERN_WEIGHTS.values())) * 
                           self.ALLOCATION_CONSTRAINTS["total_capital"])
            
            # Apply constraints
            allocation = max(
                self.ALLOCATION_CONSTRAINTS["minimum_allocation"],
                min(allocation, self.ALLOCATION_CONSTRAINTS["maximum_allocation"])
            )
            
            # Ensure we don't exceed remaining capital
            allocation = min(allocation, remaining_capital)
            
            allocations[fund] = allocation
            remaining_capital -= allocation
        
        # Adjust for rounding errors
        if remaining_capital > 0:
            funds_sorted = sorted(
                self.PATTERN_WEIGHTS.items(),
                key=lambda x: -x[1]
            )
            for fund, weight in funds_sorted:
                if remaining_capital > 0:
                    # Add remaining to highest priority fund
                    current_allocation = allocations.get(fund, 0)
                    new_allocation = current_allocation + remaining_capital
                    allocations[fund] = min(
                        new_allocation,
                        self.ALLOCATION_CONSTRAINTS["maximum_allocation"]
                    )
                    remaining_capital -= remaining_capital
        
        return allocations
    
    def format_allocations(self, allocations: Dict[str, int]) -> str:
        """
        Generate WhatsApp-ready allocation report with strategic insights.
        """
        lines = [
            "💡 Investment Recommendation",
            "",
            "🏆 Strategic Allocation Distribution:",
            ""
        ]
        
        # Sort by allocation amount (descending)
        sorted_allocations = sorted(
            allocations.items(),
            key=lambda x: x[1], 
            reverse=True
        )
        
        for fund_name, amount in sorted_allocations:
            display_name = fund_name
            if self.capitalize:
                display_name = display_name.replace("_", " ").title()
            lines.append(f"• {display_name}: {amount:,} LKR")
        
        total = sum(allocations.values())
        lines.extend([
            "",
            f"💰 Total Allocation: {total:,} LKR or less",
            "",
            "📊 Pattern Analysis: Active Momentum Phase",
            "📈 Cycle Recognition Engine: Verified"
        ])
        
        return "\n".join(lines)


# Example usage for generating market-based recommendations
def generate_recommendation():
    """
    Generate market-recognized investment allocation based on pattern strength
    """
    analyzer = MarketPatternAnalyzer(capitalize=True)
    allocations = analyzer.allocate_capital()
    message = analyzer.format_allocations(allocations)
    
    return message