from pathlib import Path

from src.api.utils.file_handling import FileHandler

class TestResolveReceiptPath:

    def test_prefers_upload_folder_by_stored_filename(self, app_with_db, tmp_path):
        upload = Path(app_with_db.config['UPLOAD_FOLDER']); upload.mkdir(parents=True, exist_ok=True)
        (upload / 'r1.jpg').write_bytes(b'x')
        with app_with_db.app_context():
            fh = FileHandler.from_app_config()
            path = fh.resolve_receipt_path({'stored_filename': 'r1.jpg',
                                            'file_path': '/app/data/uploads/r1.jpg'})  # stale, non-existent
        assert path == upload / 'r1.jpg'

    def test_falls_back_to_legacy_file_path(self, app_with_db, tmp_path):
        legacy = tmp_path / 'elsewhere' / 'r2.jpg'; legacy.parent.mkdir(); legacy.write_bytes(b'x')
        with app_with_db.app_context():
            path = FileHandler.from_app_config().resolve_receipt_path(
                {'stored_filename': 'missing.jpg', 'file_path': str(legacy)})
        assert path == legacy

    def test_none_when_nowhere(self, app_with_db):
        with app_with_db.app_context():
            assert FileHandler.from_app_config().resolve_receipt_path(
                {'stored_filename': 'nope.jpg', 'file_path': '/nope/nope.jpg'}) is None

    def test_unsafe_stored_filename_not_used(self, app_with_db):
        with app_with_db.app_context():
            assert FileHandler.from_app_config().resolve_receipt_path(
                {'stored_filename': '../../etc/passwd', 'file_path': None}) is None