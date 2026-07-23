import json
import os
from datetime import datetime
import csv
import io

try:
    from flask import Flask, abort, jsonify, render_template, request, send_from_directory
except ImportError as exc:
    raise ImportError(
        'Flask is required to run backEnd.py. Install it with: pip install Flask'
    ) from exc

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
    # No-op initialization: do NOT create databases or tables.
    # This function only verifies that a connection to the configured
    # existing database can be established. Tables must already exist.
    conn = get_db_connection()
    conn.close()

app = Flask(__name__, template_folder='templates')

# determine which template pages we will expose
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
EXCLUDED_TEMPLATES = set()
try:
    AVAILABLE_PAGES = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith('.html') and f not in EXCLUDED_TEMPLATES]
except Exception:
    AVAILABLE_PAGES = []

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(TEMPLATE_DIR, 'css'), filename)

@app.route('/img/<path:filename>')
def serve_img(filename):
    return send_from_directory(os.path.join(TEMPLATE_DIR, 'img'), filename)


def insert_accounting_entry(data):
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


def insert_sales_entry(data):
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

@app.route('/api/accounting', methods=['POST'])
def api_accounting(data=None):
    if data is None:
        data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    try:
        init_db()
        insert_accounting_entry(data)
    except Error as exc:
        app.logger.exception('Unable to save accounting entry: %s', exc)
        return jsonify({'error': 'Failed to save accounting entry'}), 500

    return jsonify({'status': 'success'}), 200


@app.route('/api/sales', methods=['POST'])
def api_sales(data=None):
    if data is None:
        data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    try:
        init_db()
        insert_sales_entry(data)
    except Error as exc:
        app.logger.exception('Unable to save sales entry: %s', exc)
        return jsonify({'error': 'Failed to save sales entry'}), 500

    return jsonify({'status': 'success'}), 200


@app.route('/', defaults={'page': 'index.html'})
@app.route('/<path:page>')
def render_page(page):
    # serve templates except excluded ones
    if page not in AVAILABLE_PAGES:
        abort(404)
    return render_template(page)


@app.route('/submit-entry', methods=['POST'])
def submit_entry():
    # Accept JSON or form submissions from the entry modal and route to the proper insert
    if request.is_json:
        data = request.get_json(silent=True)
    else:
        # allow form fields
        data = request.form.to_dict()

    kind = data.get('kind') or data.get('type') or request.args.get('kind')
    if not kind:
        return jsonify({'error': 'Missing kind/type parameter'}), 400

    if kind.lower() == 'accounting':
        return api_accounting(data=data)
    if kind.lower() == 'sales':
        return api_sales(data=data)

    return jsonify({'error': 'Unsupported kind'}), 400


@app.route('/import', methods=['POST'])
def import_file():
    # Accept a file upload (CSV) and import rows to MySQL for accounting or sales
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    kind = request.form.get('kind') or request.form.get('template') or request.args.get('kind')
    if not kind:
        return jsonify({'error': 'Missing kind parameter (accounting|sales)'}), 400

    table_map = {
        'accounting': 'accounting_entries',
        'sales': 'sales_entries',
    }
    table = table_map.get(kind.lower())
    if not table:
        return jsonify({'error': 'Unsupported kind for import'}), 400

    try:
        # parse CSV
        stream = io.TextIOWrapper(file.stream, encoding='utf-8')
        reader = csv.DictReader(stream)

        init_db()
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            for row in reader:
                # build dynamic insert based on CSV headers
                cols = []
                vals = []
                # always include timestamp
                cols.append('timestamp')
                vals.append(datetime.utcnow().isoformat() + 'Z')
                for k, v in row.items():
                    if k and v is not None and v != '':
                        cols.append(k)
                        vals.append(v)

                placeholders = ','.join(['%s'] * len(vals))
                cols_sql = ','.join(cols)
                sql = f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})"
                cursor.execute(sql, tuple(vals))
        finally:
            conn.close()
    except Error as exc:
        app.logger.exception('Import failed: %s', exc)
        return jsonify({'error': 'Import failed'}), 500
    except Exception as exc:
        app.logger.exception('Import parse failed: %s', exc)
        return jsonify({'error': 'Failed to parse/import file'}), 500

    return jsonify({'status': 'imported'}), 200

try:
    init_db()
except Exception as exc:
    app.logger.exception('MySQL initialization failed: %s', exc)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
