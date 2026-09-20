def test_update_transaction_ignores_receipt_id(app_with_db, test_data, unlinked, live_transaction):
    from src.database.repositories.transactions import TransactionRepository
    with app_with_db.app_context():
        TransactionRepository().update_transaction(live_transaction, receipt_id=unlinked)
    assert test_data.fetch_one(app_with_db, 'SELECT receipt_id FROM transactions WHERE id = ?',
                               (live_transaction,))['receipt_id'] is None

def test_bulk_update_ignores_receipt_id(app_with_db, test_data, unlinked, live_transaction):
    from src.database.repositories.transactions import TransactionRepository
    with app_with_db.app_context():
        TransactionRepository().bulk_update_transactions(   # adjust to actual name
            [live_transaction], receipt_id=unlinked
        )
    assert test_data.fetch_one(
        app_with_db, 'SELECT receipt_id FROM transactions WHERE id = ?',
        (live_transaction,),
    )['receipt_id'] is None

