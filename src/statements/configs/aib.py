from src.statements.base import (
    StatementConfig, DateConfig, AmountConfig
)

AIB_CURRENT = StatementConfig(
    bank_name='AIB',
    account_type='current',
    date_config=DateConfig(
        column='Date',
        format=None,  # Let pandas infer
        dayfirst=True
    ),
    amount_config=AmountConfig(
        credit_column='In',
        debit_column='Out',
        currency_symbols=['€', 'EUR'],
        debit_is_negative=True
    ),
    description_column='Description'
)