# Dividend Strategy Analysis Tool 📈

Welcome! This tool is designed to be your "Financial Time Machine." It allows you to test different stock market strategies against real historical data from the last 10 years to see exactly how much money you would have made (or lost) if you had followed a specific set of rules.

## 🌐 View the Reports Online

You can view the interactive results and charts directly in your browser here:
👉 **[View Dividend Analysis Dashboards](https://clates.github.io/dividend-analysis/)**

---

## 👨‍🏫 How This Works (Simple Explanation)

Imagine you have **$100,000** and a set of rules, like: *"I want to buy a stock 5 days before it pays a dividend and sell it 5 days after."*

Instead of guessing if that's a good idea, this tool:
1. **Downloads Real History**: It grabs 10 years of daily prices and dividend payments for all 500+ companies in the S&P 500.
2. **Simulates Every Day**: It starts in 2016 and "plays through" every single day up to today. 
3. **Follows Your Rules**: If your rules say "Buy," it buys. If they say "Sell," it sells. It keeps track of your cash, your shares, and every dividend check you would have received.
4. **Shows the Results**: It creates a dashboard showing your account growth (the "Equity Curve") compared to just holding the S&P 500 or putting your money in a 5% CD.

---

## 🚀 How to Use This

Since you have an AI assistant, you don't need to write any code. You just need to tell the AI what you want to test.

### 1. View Current Results
If you just want to see the latest analysis, you can open the **Reports** folder and look for the `portfolio_dashboard.html` files. These are visual websites that show the charts and trade lists.

### 2. Changing the Rules
If you want to try a new idea (e.g., "What if I hold for 15 days instead of 5?"), ask your AI assistant:
> *"Hey, can you update the dividend strategy to buy 15 days before and sell 10 days after, then run the simulation again?"*

### 3. Adjusting the "Knobs"
In the file called `config.json`, there are a few settings you can change:
*   **initial_cash**: How much money you start with (default is $100,000).
*   **max_active_positions**: How many different stocks you are willing to hold at once (e.g., 20).
*   **commission**: How much the broker charges you per trade (set to 0 for free trading).

---

## 📊 Key Terms to Know

*   **Total Return**: The total percentage your money grew. (e.g., +400% means your $100k became $500k).
*   **Max Drawdown**: The "scariest moment." This is the biggest drop from a peak. If it says -30%, it means at one point your account value dipped 30% below its highest previous value.
*   **Ex-Dividend Date**: The "cutoff date." You must own the stock before this day to get the dividend.
*   **Benchmarks**: These are "Control Groups." We compare your strategy against the **S&P 500** to see if your rules actually beat the general market.

---

## 🛠 For the AI Assistant
To run a new simulation:
1. Update `config.json` or the strategy files in `strategies/`.
2. Run `python3 portfolio_engine.py` to generate a single report.
3. Run `python3 sweep_portfolio.py` to test hundreds of combinations at once.
4. The reports will appear in the `reports/` folder.
