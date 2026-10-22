"""Lab 14 risk engine. Annual decimal inputs; standard library only."""
from math import isclose, isfinite, sqrt

SLEEVES = [
    ("Treasury bills", 0.035, 0.005),
    ("Treasury 10-year note", 0.043, 0.07),
    ("Investment-grade bond fund", 0.05, 0.06),
    ("Global equity index fund", 0.08, 0.16),
]
CORRELATION = [
    [1, 0.10, 0.05, 0],
    [0.10, 1, 0.80, -0.10],
    [0.05, 0.80, 1, 0.25],
    [0, -0.10, 0.25, 1],
]
OBJECTIVE = 0.065  # CPI estimate 2.5% + real-return objective 4%.
RESERVE_INDICES = (0, 1)


def validate_correlation(correlation, n):
    if len(correlation) != n or any(len(row) != n for row in correlation):
        raise ValueError("Correlation table must be square, one row per sleeve.")
    for i in range(n):
        for j in range(n):
            value = correlation[i][j]
            if not isfinite(value) or not -1 <= value <= 1:
                raise ValueError("Every correlation must be finite and between -1 and 1.")
            if not isclose(value, correlation[j][i], abs_tol=1e-12):
                raise ValueError("Correlation table must be symmetric.")
        if not isclose(correlation[i][i], 1, abs_tol=1e-12):
            raise ValueError("Diagonal correlations must equal 1.")


def covariance_matrix(sleeves, correlation):
    validate_correlation(correlation, len(sleeves))
    if any(not isfinite(s[2]) or s[2] <= 0 for s in sleeves):
        raise ValueError("Volatilities must be finite and positive.")
    return [[correlation[i][j] * sleeves[i][2] * sleeves[j][2]
             for j in range(len(sleeves))] for i in range(len(sleeves))]


def equal_weights(n):
    return [1 / n] * n


def inverse_volatility_weights(sleeves):
    inverse = [1 / sleeve[2] for sleeve in sleeves]
    return [value / sum(inverse) for value in inverse]


def expected_return(weights, sleeves):
    return sum(w * sleeve[1] for w, sleeve in zip(weights, sleeves))


def portfolio_variance(weights, covariance):
    # Both (i,j) and (j,i) appear: this includes twice each pair's covariance.
    return sum(weights[i] * weights[j] * covariance[i][j]
               for i in range(len(weights)) for j in range(len(weights)))


def portfolio_volatility(weights, covariance):
    variance = portfolio_variance(weights, covariance)
    if variance < -1e-12:
        raise ValueError("Inputs produce negative portfolio variance.")
    return sqrt(max(0, variance))


def reserve_weight(weights):
    return sum(weights[i] for i in RESERVE_INDICES)


def meets_objective(value, objective):
    return value >= objective


def baseline_weights(sleeves):
    return {"Benchmark": [0, 0, 0.4, 0.6],
            "Equal weight": equal_weights(len(sleeves)),
            "Inverse volatility": inverse_volatility_weights(sleeves)}


def main():
    covariance = covariance_matrix(SLEEVES, CORRELATION)
    print("Course training inputs; annual estimates, not market forecasts.")
    print("Order: bills / 10-year / IG bonds / equity")
    print(f"Objective: {OBJECTIVE:.2%} (CPI estimate 2.5% + 4%)")
    for name, weights in baseline_weights(SLEEVES).items():
        value = expected_return(weights, SLEEVES)
        print(f"\n{name}: " + " / ".join(f"{w * 100:.1f}" for w in weights))
        print(f"Return: {value:.2%}; volatility: {portfolio_volatility(weights, covariance):.2%}; "
              f"reserve-eligible: {reserve_weight(weights):.1%}; "
              f"meets objective: {'yes' if meets_objective(value, OBJECTIVE) else 'no'}")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(f"Input error: {error}")



def search_mix(sleeves, correlation, objective=OBJECTIVE,
               reserve_indices=RESERVE_INDICES, reserve_minimum=0.03):
    """Exhaust every fully invested long-only allocation in 5-point steps."""
    if not 3 <= len(sleeves) <= 6:
        raise ValueError("Use three to six assets.")
    if not isfinite(objective) or not 0 <= reserve_minimum <= 1:
        raise ValueError("Use a finite objective and reserve minimum from 0 to 1.")
    if any(not isfinite(s[1]) for s in sleeves):
        raise ValueError("Return estimates must be finite.")
    if any(i not in range(len(sleeves)) for i in reserve_indices):
        raise ValueError("Invalid reserve asset index.")
    covariance = covariance_matrix(sleeves, correlation)

    def allocations(remaining, count):
        if count == 1:
            yield [remaining / 20]
        else:
            for units in range(remaining + 1):
                for tail in allocations(remaining - units, count - 1):
                    yield [units / 20] + tail

    best = None
    for weights in allocations(20, len(sleeves)):
        value = expected_return(weights, sleeves)
        reserve = sum(weights[i] for i in set(reserve_indices))
        if value + 1e-12 < objective or reserve + 1e-12 < reserve_minimum:
            continue
        volatility = portfolio_volatility(weights, covariance)
        if best is None or volatility < best['volatility']:
            best = dict(weights=weights, return_estimate=value,
                        volatility=volatility, reserve=reserve)
    return best


def estimate_prices(csv_file, last_36=False):
    """Annual arithmetic estimates from complete monthly adjusted prices."""
    import pandas as pd
    prices = pd.read_csv(csv_file)
    if not 4 <= len(prices.columns) <= 7:
        raise ValueError("CSV needs a date column and three to six tickers.")
    dates = pd.to_datetime(prices.iloc[:, 0], errors='raise')
    months = dates.dt.to_period('M').astype('int64')
    if dates.isna().any() or not (months.diff().dropna() == 1).all():
        raise ValueError("Use consecutive months, oldest first, without duplicates.")
    values = prices.iloc[:, 1:].apply(pd.to_numeric, errors='raise')
    if values.isna().any().any() or not values.map(isfinite).all().all() or (values <= 0).any().any():
        raise ValueError("Prices must be complete, finite and positive.")
    returns = values.pct_change(fill_method=None).iloc[1:]
    if len(returns) < 60:
        raise ValueError("Provide at least 61 monthly prices for 60 monthly returns.")
    if last_36:
        returns = returns.tail(36)
    means, vols = returns.mean() * 12, returns.std(ddof=1) * sqrt(12)
    sleeves = [(ticker, float(means[ticker]), float(vols[ticker])) for ticker in returns.columns]
    correlation = returns.corr().values.tolist()
    covariance_matrix(sleeves, correlation)
    return sleeves, correlation
