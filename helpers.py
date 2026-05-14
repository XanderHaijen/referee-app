def get_rate_for_game(divisie, pricing_df, is_internal: bool):
    """Return the rate for a given division using the pricing dataframe.

    pricing_df expected columns: ['division','internal_rate','external_rate']
    Matching is done by comparing the `divisie` value (exact, case-insensitive)
    to the `division` column in the pricing dataframe. If no exact match is
    found the function falls back to a row with division == 'DEFAULT', then
    to the first row.
    """
    if pricing_df is None or pricing_df.empty:
        return 0.0

    div_text = str(divisie or "").strip().lower()
    if div_text:
        match = pricing_df[pricing_df['division'].astype(str).str.lower() == div_text]
        if not match.empty:
            row = match.iloc[0]
            col = 'internal_rate' if is_internal else 'external_rate'
            try:
                return float(row.get(col, 0))
            except Exception:
                return 0.0

    # fallback to DEFAULT row
    default_row = pricing_df[pricing_df['division'].astype(str).str.lower() == 'default']
    if not default_row.empty:
        row = default_row.iloc[0]
        col = 'internal_rate' if is_internal else 'external_rate'
        try:
            return float(row.get(col, 0))
        except Exception:
            return 0.0

    # final fallback: first row
    try:
        row = pricing_df.iloc[0]
        col = 'internal_rate' if is_internal else 'external_rate'
        return float(row.get(col, 0))
    except Exception:
        return 0.0
