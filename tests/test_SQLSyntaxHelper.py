import unittest
from src.SQLSyntaxHelper import MySQLSyntaxHelper, ETablesBM_DB, EJoin


class TestMySQLSyntaxHelper(unittest.TestCase):

    def test_select_query(self):
        columns = ['id_log', 'object', 'action']
        table = ETablesBM_DB.LOGS
        generated_query = MySQLSyntaxHelper.select(table, columns)
        self.assertIn("SELECT id_log, object, action FROM", generated_query)
        self.assertIn("logs", generated_query)

    def test_select_with_join(self):
        columns = ['logs.id_log', 'profiles.profile_name']
        table = ETablesBM_DB.LOGS
        join_condition = MySQLSyntaxHelper.join(
            ETablesBM_DB.PROFILES, 'profiles.id_profile = logs.fk_id_profile', EJoin.INNER
        )
        generated_query = MySQLSyntaxHelper.select(table, columns, join=join_condition)
        self.assertIn("SELECT logs.id_log, profiles.profile_name FROM", generated_query)
        self.assertIn("INNER JOIN", generated_query)
        self.assertIn("profiles.id_profile = logs.fk_id_profile", generated_query)

    def test_select_with_where(self):
        columns = ['id_log', 'object', 'action']
        table = ETablesBM_DB.LOGS
        where_sql, where_params = MySQLSyntaxHelper.where_params({'id_log': 1001})
        generated_query = MySQLSyntaxHelper.select(table, columns, where=where_sql)
        self.assertIn("WHERE", generated_query)
        self.assertIn("id_log", generated_query)
        self.assertIn("%s", generated_query)
        self.assertEqual(where_params, [1001])

    def test_insert_query(self):
        table = ETablesBM_DB.LOGS
        data = {'id_log': 1001, 'fk_id_profile': 5001, 'message_text': 'Hello'}
        query, params = MySQLSyntaxHelper.insert(table, data)
        self.assertIn("INSERT INTO", query)
        self.assertIn("id_log", query)
        self.assertIn("fk_id_profile", query)
        self.assertIn("message_text", query)
        self.assertIn("VALUES (%s, %s, %s)", query)
        self.assertEqual(params, [1001, 5001, 'Hello'])

    def test_select_servers_query(self):
        table = ETablesBM_DB.SERVERS
        columns = ['server_name', 'id_server']
        generated_query = MySQLSyntaxHelper.select(table, columns)
        self.assertIn("SELECT server_name, id_server FROM", generated_query)
        self.assertIn("servers", generated_query)


if __name__ == '__main__':
    unittest.main()
