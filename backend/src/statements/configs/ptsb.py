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