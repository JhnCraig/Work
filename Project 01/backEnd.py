import json
import os
from datetime import datetime

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:  # pragma: no cover - import fallback for environments without the package
    mysql = None
    Error = Exception


BASE_DIR = os.path.dirname(__file__)
CSS_DIR = os.path.join(BASE_DIR, 'css')
MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'cat_cafe')


def get_db_connection():
    if mysql is None:
        raise RuntimeError(
            'mysql-connector-python is required. Install it with: pip install mysql-connector-python'
        )

    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        autocommit=True,
    )


def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS orders (
                id INT PRIMARY KEY,
                timestamp VARCHAR(255) NOT NULL,
                cart JSON NOT NULL,
                customer JSON NULL,
                custom JSON NULL
            )
            '''
        )
        # Accounting entries table
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS accounting_entries (
                id INT PRIMARY KEY AUTO_INCREMENT,
                timestamp VARCHAR(255) NOT NULL,
                cv_no VARCHAR(255),
                entry_date DATE,
                payee VARCHAR(255),
                supplier_name VARCHAR(255),
                tin VARCHAR(255),
                address VARCHAR(1024),
                transaction_details TEXT,
                amount VARCHAR(255),
                vat_12 VARCHAR(255),
                net_of_vat VARCHAR(255),
                vat_exempt VARCHAR(255),
                non_vat VARCHAR(255),
                wtax VARCHAR(255),
                account_code VARCHAR(255),
                account_name VARCHAR(255),
                project VARCHAR(255),
                si_no VARCHAR(255),
                si_date DATE,
                remarks TEXT
            )
            '''
        )

        # Sales entries table
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS sales_entries (
                id INT PRIMARY KEY AUTO_INCREMENT,
                timestamp VARCHAR(255) NOT NULL,
                month VARCHAR(255),
                project_code VARCHAR(255),
                client_name VARCHAR(255),
                tin VARCHAR(255),
                po_no VARCHAR(255),
                address VARCHAR(1024),
                si_no VARCHAR(255),
                si_date DATE,
                transaction_details TEXT,
                po_amount VARCHAR(255),
                inv_amount VARCHAR(255),
                vat VARCHAR(255),
                net_of_vat VARCHAR(255),
                wtax_2 VARCHAR(255),
                net_amount VARCHAR(255),
                cash_in_bank VARCHAR(255),
                bank_date DATE,
                bank VARCHAR(255),
                description TEXT,
                remarks TEXT
            )
            '''
        )
    finally:
        conn.close()

app = Flask(__name__, template_folder='templates')

@app.route('/api/accounting', methods=['POST'])
def api_accounting():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    try:
        init_db()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO accounting_entries (
                    timestamp, cv_no, entry_date, payee, supplier_name, tin, address,
                    transaction_details, amount, vat_12, net_of_vat, vat_exempt, non_vat,
                    wtax, account_code, account_name, project, si_no, si_date, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''',
                (
                    datetime.utcnow().isoformat() + 'Z',
                    data.get('cv_no'),
                    data.get('date'),
                    data.get('payee'),
                    data.get('supplier_name'),
                    data.get('tin'),
                    data.get('address'),
                    data.get('transaction_details'),
                    data.get('amount'),
                    data.get('vat_12'),
                    data.get('net_of_vat'),
                    data.get('vat_exempt'),
                    data.get('non_vat'),
                    data.get('wtax'),
                    data.get('account_code'),
                    data.get('account_name'),
                    data.get('project'),
                    data.get('si_no'),
                    data.get('si_date'),
                    data.get('remarks'),
                ),
            )
        finally:
            conn.close()
    except Error as exc:
        app.logger.exception('Unable to save accounting entry: %s', exc)
        return jsonify({'error': 'Failed to save accounting entry'}), 500

    return jsonify({'status': 'success'}), 200


@app.route('/api/sales', methods=['POST'])
def api_sales():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    try:
        init_db()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO sales_entries (
                    timestamp, month, project_code, client_name, tin, po_no, address,
                    si_no, si_date, transaction_details, po_amount, inv_amount, vat,
                    net_of_vat, wtax_2, net_amount, cash_in_bank, bank_date, bank,
                    description, remarks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''',
                (
                    datetime.utcnow().isoformat() + 'Z',
                    data.get('month'),
                    data.get('project_code'),
                    data.get('client_name'),
                    data.get('tin'),
                    data.get('po_no'),
                    data.get('address'),
                    data.get('si_no'),
                    data.get('si_date'),
                    data.get('transaction_details'),
                    data.get('po_amount'),
                    data.get('inv_amount'),
                    data.get('vat'),
                    data.get('net_of_vat'),
                    data.get('wtax_2'),
                    data.get('net_amount'),
                    data.get('cash_in_bank'),
                    data.get('bank_date'),
                    data.get('bank'),
                    data.get('description'),
                    data.get('remarks'),
                ),
            )
        finally:
            conn.close()
    except Error as exc:
        app.logger.exception('Unable to save sales entry: %s', exc)
        return jsonify({'error': 'Failed to save sales entry'}), 500

    return jsonify({'status': 'success'}), 200

try:
    init_db()
except Exception as exc:
    app.logger.exception('MySQL initialization failed: %s', exc)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
