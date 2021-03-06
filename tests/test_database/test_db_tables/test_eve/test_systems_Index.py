from tests.test_database.test_db_tables.test_eve import AbstractIndexApiUpdating
from database.db_tables.eve import tb_systems


class TestSystemsIndex(AbstractIndexApiUpdating.AbstractIndexApiUpdating):
    @property
    def index_id_file_name(self):
        return "systems.txt"

    @property
    def table_row(self):
        return tb_systems
