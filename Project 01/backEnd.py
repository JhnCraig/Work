import json
import os
import sqlite3
from datetime import datetime

from flask import Flask, request, jsonify, render_template, abort, send_from_directory


BASE_DIR = os.path.dirname(__file__)
CSS_DIR = os.path.join(BASE_DIR, 'css')
ORDERS_FILE = os.path.join(BASE_DIR, 'order.json')
DB_FILE = os.path.join(BASE_DIR, 'orders.db')


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cart TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    ensure_db_columns()


def ensure_db_columns():
    conn = sqlite3.connect(DB_FILE)
    existing_columns = {row[1] for row in conn.execute('PRAGMA table_info(orders)')}
    if 'customer' not in existing_columns:
        conn.execute('ALTER TABLE orders ADD COLUMN customer TEXT')
    if 'custom' not in existing_columns:
        conn.execute('ALTER TABLE orders ADD COLUMN custom TEXT')
    conn.commit()
    conn.close()


def load_legacy_orders(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def should_include_size(item):
    image_name = (item.get('image') or '').lower().split('/')[-1]
    name = (item.get('name') or '').lower()
    return not (image_name.startswith('necklace') or 'necklace' in name or image_name.startswith('earring') or 'earring' in name)


def load_orders():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT id, timestamp, cart, customer, custom FROM orders ORDER BY id ASC'
    ).fetchall()
    conn.close()

    orders = []
    for row in rows:
        order = {
            'id': row['id'],
            'timestamp': row['timestamp'],
            'cart': json.loads(row['cart']) if row['cart'] else []
        }
        if row['customer']:
            order['customer'] = json.loads(row['customer'])
        if row['custom']:
            order['custom'] = json.loads(row['custom'])
        orders.append(order)

    return orders


def save_orders(orders, filename):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=4, ensure_ascii=False)

    init_db()
    conn = sqlite3.connect(DB_FILE)
    conn.execute('DELETE FROM orders')

    for order in orders:
        conn.execute(
            'INSERT INTO orders (id, timestamp, cart, customer, custom) VALUES (?, ?, ?, ?, ?)',
            (
                order.get('id'),
                order.get('timestamp'),
                json.dumps(order.get('cart', []), ensure_ascii=False),
                json.dumps(order.get('customer', None), ensure_ascii=False) if 'customer' in order else None,
                json.dumps(order.get('custom', None), ensure_ascii=False) if 'custom' in order else None
            )
        )

    conn.commit()
    conn.close()


def migrate_legacy_orders():
    legacy_orders = load_legacy_orders(ORDERS_FILE)
    if not legacy_orders:
        return

    init_db()
    conn = sqlite3.connect(DB_FILE)
    existing_count = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    if existing_count > 0:
        conn.close()
        return

    for order in legacy_orders:
        conn.execute(
            'INSERT INTO orders (id, timestamp, cart, customer, custom) VALUES (?, ?, ?, ?, ?)',
            (
                order.get('id'),
                order.get('timestamp'),
                json.dumps(order.get('cart', []), ensure_ascii=False),
                json.dumps(order.get('customer', None), ensure_ascii=False) if 'customer' in order else None,
                json.dumps(order.get('custom', None), ensure_ascii=False) if 'custom' in order else None
            )
        )

    conn.commit()
    conn.close()


migrate_legacy_orders()
orders = load_orders()

app = Flask(__name__, template_folder='templates')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/orders', methods=['GET'])
def list_orders():
    return jsonify(load_orders())


@app.route('/<path:page>')
def render_page(page):
    # Prevent directory traversal
    if '..' in page or page.startswith('/'):
        abort(404)

    # Try exact file in templates
    templates_dir = os.path.join(BASE_DIR, 'templates')
    candidate = os.path.join(templates_dir, page)
    if os.path.exists(candidate) and os.path.isfile(candidate):
        return render_template(page)

    # Try with .html appended
    if not page.endswith('.html'):
        candidate_html = candidate + '.html'
        if os.path.exists(candidate_html) and os.path.isfile(candidate_html):
            return render_template(page + '.html')

    # Case-insensitive fallback: find a template file that matches ignoring case
    try:
        for fname in os.listdir(templates_dir):
            if fname.lower() == page.lower() or fname.lower() == (page + '.html').lower():
                return render_template(fname)
    except OSError:
        pass

    abort(404)


@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(CSS_DIR, filename)


@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'js'), filename)


@app.route('/images/<path:filename>')
def template_images(filename):
    images_dir = os.path.join(BASE_DIR, 'templates', 'images')
    return send_from_directory(images_dir, filename)


# Additional cart routes to support different cart link variants
@app.route('/cart')
def cart_short():
    return render_template('addToCart.html')


@app.route('/addtocart.html')
def addtocart_lower():
    return render_template('addToCart.html')


@app.route('/addToCart')
def addtocart_noext():
    return render_template('addToCart.html')


@app.route('/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    cart = data.get('cart')
    if not cart:
        return jsonify({'error': 'Cart is empty'}), 400

    normalized_cart = []
    for item in cart:
        normalized_item = {
            'name': item.get('name'),
            'image': item.get('image'),
            'price': item.get('price'),
            'quantity': item.get('quantity', 1)
        }
        if should_include_size(item) and item.get('size'):
            normalized_item['size'] = item.get('size')
        normalized_cart.append(normalized_item)

    customer = data.get('customer') or {}
    new_order = {
        'id': len(orders) + 1,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'cart': normalized_cart,
        'customer': {
            'name': customer.get('name'),
            'email': customer.get('email'),
            'phone': customer.get('phone'),
            'address': customer.get('address'),
            'payment': customer.get('payment') or data.get('paymentMethod')
        }
    }

    orders.append(new_order)
    save_orders(orders, ORDERS_FILE)

    return jsonify({'status': 'success', 'order': new_order}), 200


@app.route('/custom-order', methods=['POST'])
def custom_order():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    cart = data.get('cart')
    if not cart:
        return jsonify({'error': 'Cart is empty'}), 400

    custom = data.get('custom', {})

    normalized_cart = []
    for item in cart:
        normalized_item = {
            'name': item.get('name'),
            'image': item.get('image'),
            'price': item.get('price'),
            'quantity': item.get('quantity', 1)
        }
        if should_include_size(item) and item.get('size'):
            normalized_item['size'] = item.get('size')
        normalized_cart.append(normalized_item)

    new_order = {
        'id': len(orders) + 1,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'cart': normalized_cart,
        'custom': {
            'name': custom.get('name'),
            'email': custom.get('email'),
            'description': custom.get('description'),
            'delivery_option': custom.get('deliveryOption'),
            'date': custom.get('date'),
            'time': custom.get('time')
        }
    }

    orders.append(new_order)
    save_orders(orders, ORDERS_FILE)

    return jsonify({'status': 'success', 'order': new_order}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
