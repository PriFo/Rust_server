import unittest
from typing import List
from SQLSyntaxHelper import MySQLSyntaxHelper, ETablesBM_DB, EJoin

class TestMySQLSyntaxHelper(unittest.TestCase):

    def test_select_query(self):
        columns = ['id_log', 'object', 'action']
        table = ETablesBM_DB.LOGS_SQL
        expected_query = f"SELECT id_log, object, action FROM {table}"
        generated_query = MySQLSyntaxHelper.select(table, columns)
        self.assertEqual(generated_query, expected_query)

    def test_select_with_join(self):
        columns = ['logs.id_log', 'profiles.profile_name']
        table = ETablesBM_DB.LOGS
        join_condition = MySQLSyntaxHelper.join(ETablesBM_DB.PROFILES, 'profiles.id_profile = logs.fk_id_profile', EJoin.INNER)
        expected_query = f"SELECT logs.id_log, profiles.profile_name FROM {table} INNER JOIN {ETablesBM_DB.PROFILES} ON profiles.id_profile = logs.fk_id_profile"
        generated_query = MySQLSyntaxHelper.select(table, columns, join=join_condition)
        self.assertEqual(generated_query, expected_query)

    def test_select_with_where(self):
        columns = ['id_log', 'object', 'action']
        table = ETablesBM_DB.LOGS_SQL
        where_condition = MySQLSyntaxHelper.where('id_log', '1001', '=')
        expected_query = f"SELECT id_log, object, action FROM {table} WHERE id_log = 1001"
        generated_query = MySQLSyntaxHelper.select(table, columns, where=where_condition)
        self.assertEqual(generated_query, expected_query)

    def test_insert_query(self):
        table = ETablesBM_DB.LOGS
        columns = ['id_log', 'fk_id_profile', 'message_to_bot']
        values = ['1001', '5001', 'Hello from bot']
        expected_query = f"INSERT INTO {table} (id_log, fk_id_profile, message_to_bot) VALUES ('1001', '5001', 'Hello from bot')"
        generated_query = MySQLSyntaxHelper.insert(table, columns, values)
        self.assertEqual(generated_query, expected_query)

    def test_select_servers_query(self):
        table = ETablesBM_DB.SERVERS
        columns = ['server_name', 'id_server']
        expected_query = f'SELECT server_name, id_server FROM servers'
        generated_query = MySQLSyntaxHelper.select(table, columns)
        self.assertEqual(generated_query, expected_query)

if __name__ == '__main__':
    unittest.main()