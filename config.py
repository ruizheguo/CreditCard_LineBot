import pymysql

# LINE Bot credentials
CHANNEL_SECRET = '9447da13d9051f4773aa3f35244915d3'
CHANNEL_ACCESS_TOKEN = '2007797906'

# MySQL database configuration
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3307,
    'user': 'root',
    'password': 'RootPassword',
    'database': 'credit_card_bot',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
