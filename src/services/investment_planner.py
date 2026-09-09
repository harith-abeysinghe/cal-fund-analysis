from typing import Dict, List


class InvestmentPlanner:
    def __init__(self, max_investment_lkr: int):
        self.max_investment_lkr = max_investment_lkr

    def get_top_funds(self, funds: List[Dict], count: int = 3) -> List[Dict]:
        sorted_funds = sorted(funds, key=lambda f: f.get('price_growth', 0), reverse=True)
        return sorted_funds[:count]

    def plan_investment(self, top_funds: List[Dict]) -> List[tuple[str, int]]:
        if not top_funds:
            return []

        total_return = sum(f['price_growth'] for f in top_funds)
        if total_return <= 0:
            # Equal allocation if all returns are non-positive
            per_fund = self.max_investment_lkr // len(top_funds)
            allocations = [(fund['name'], per_fund) for fund in top_funds]
            return allocations

        allocations = []
        for fund in top_funds:
            weight = fund['price_growth'] / total_return
            allocation = int(self.max_investment_lkr * weight)
            allocations.append((fund['name'], allocation))

        return allocations
