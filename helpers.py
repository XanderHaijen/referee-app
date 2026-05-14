def get_rate_for_game(wedstrijd, pricing_df, is_internal: bool):
    """Return the rate for a given game string using the pricing dataframe.

    pricing_df expected columns: ['division','internal_rate','external_rate']
    Matching is done by checking if a division string appears in the `wedstrijd` text.
    If no match, tries to use a row with division == 'DEFAULT', otherwise first row.
    """
    if pricing_df is None or pricing_df.empty:
        return 0.0

    wedstrijd_text = str(wedstrijd or "").lower()
    for _, row in pricing_df.iterrows():
        div = str(row.get('division', '')).strip().lower()
        if div and div != 'default' and div in wedstrijd_text:
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
