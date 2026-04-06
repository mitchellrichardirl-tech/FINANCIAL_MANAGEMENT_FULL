from src.statements.base import (
    StatementConfig, DateConfig, AmountConfig
)

PTSB_CURRENT = StatementConfig(
    bank_name='Permanent TSB',
    account_type='current',
    date_config=DateConfig(
        column='Date',
        format='%d/%m/%Y',
        dayfirst=True
    ),
    amount_config=AmountConfig(
        credit_column='Money In (€)',
        debit_column='Money Out (€)',
        currency_symbols=['€'],
        debit_is_negative=False  # We sum them, so debit should subtract
    ),
    description_column='Description',
    balance_column='Balance (€)',
    exclude_patterns=[
        r'^Opening Balance',
        r'^Closing Balance'
    ]
)

PTSB_CREDIT_CARD = StatementConfig(
    bank_name='Permanent TSB',
    account_type='credit_card',
    date_config=DateConfig(
        column='Transaction Date',
        format='%d %b %Y',
        dayfirst=True
    ),
    amount_config=AmountConfig(
        amount_column='Amount',
        signed_amount=True,
        currency_symbols=['€']
    ),
    description_column='Description',
    exclude_patterns=[
        r'^Payment - Thank You',
        r'^INTEREST CHARGE'
    ]
)

if __name__ == "__main__":
    import pytest

    def test_from_dict_tolerates_unknown_keys():
        data = PTSB_CURRENT.to_dict()
        data["some_future_field"] = "whatever"
        data["date_config"]["also_unknown"] = 42
        assert StatementConfig.from_dict(data) == PTSB_CURRENT

    def test_defaults_whitelist_rejects_amount():
        with pytest.raises(ValueError, match="not a permitted default"):
            StatementConfig(
                account_type='credit_card',
                bank_name='Permanent TSB',
                date_config=DateConfig(column='Transaction Date', format='%d %b %Y'),
                amount_config=AmountConfig(amount_column='Amount', signed_amount=True, currency_symbols=['€']),
                description_column='Description',
                defaults={"amount": 0}
            )

    def test_defaults_whitelist_type_checked():
        with pytest.raises(ValueError, match="must be bool"):
            StatementConfig(
                account_type='credit_card',
                bank_name='Permanent TSB',
                date_config=DateConfig(column='Transaction Date', format='%d %b %Y'),
                amount_config=AmountConfig(amount_column='Amount', signed_amount=True, currency_symbols=['€']),
                description_column='Description',
                defaults={"is_kids": "yes"}
            )
    test_defaults_whitelist_rejects_amount()
    test_defaults_whitelist_type_checked()
    test_from_dict_tolerates_unknown_keys()