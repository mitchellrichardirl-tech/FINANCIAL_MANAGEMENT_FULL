from src.statements.base import (
    StatementConfig, DateConfig, AmountConfig
)

REVOLUT_CURRENT = StatementConfig(
    bank_name='Revolut',
    account_type='current',
    date_config=DateConfig(
        column='Started Date',
        format='%Y-%m-%d %H:%M:%S',
        dayfirst=False
    ),
    amount_config=AmountConfig(
        amount_column='Amount',
        signed_amount=True,
        currency_symbols=['€', '$', '£']
    ),
    description_column='Description',
    balance_column='Balance',
    exclude_patterns=[
        r'^Top-Up',
        r'^Balance migration'
    ]
)