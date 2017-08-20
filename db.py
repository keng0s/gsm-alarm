import MySQLdb


class DB(object):
    _db_connection = None
    _db_cur = None

    def __init__(self, host, username, password, db):
        self._db_connection = MySQLdb.connect(host, username, password, db)
        self._db_connection.autocommit(True)
        self._db_cur = self._db_connection.cursor()

    def query(self, query, params):
        return self._db_cur.execute(query, params)

    def fetchall(self, query, params):
        self._db_cur.execute(query, params)
        return self._db_cur.fetchall()

    def __del__(self):
        self._db_connection.close()
