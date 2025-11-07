from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # distributor, shg, pharmacist
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DistributorInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    distributor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    distributor = db.relationship('User', backref='distributor_inventory')
    product = db.relationship('Product', backref='distributor_inventory')

class SHGInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shg_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    shg = db.relationship('User', backref='shg_inventory')
    product = db.relationship('Product', backref='shg_inventory')

class PharmacistInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pharmacist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    pharmacist = db.relationship('User', backref='pharmacist_inventory')
    product = db.relationship('Product', backref='pharmacist_inventory')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    distributor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    orderer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='placed')  # placed, delivered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivered_at = db.Column(db.DateTime)
    
    distributor = db.relationship('User', foreign_keys=[distributor_id], backref='orders_received')
    orderer = db.relationship('User', foreign_keys=[orderer_id], backref='orders_placed')
    product = db.relationship('Product', backref='orders')

# Initialize database
with app.app_context():
    db.create_all()

# Routes

# User Management
@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    if not data.get('username') or not data.get('password') or not data.get('user_type'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if data['user_type'] not in ['distributor', 'shg', 'pharmacist']:
        return jsonify({'error': 'Invalid user type'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    user = User(username=data['username'], user_type=data['user_type'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'user_type': user.user_type
    }), 201

@app.route('/api/users', methods=['GET'])
def get_users():
    user_type = request.args.get('type')
    query = User.query
    if user_type:
        query = query.filter_by(user_type=user_type)
    
    users = query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'user_type': u.user_type
    } for u in users])

# Product Management
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    if not data.get('name') or not data.get('unit_price'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    product = Product(
        name=data['name'],
        description=data.get('description', ''),
        unit_price=float(data['unit_price'])
    )
    db.session.add(product)
    db.session.commit()
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'unit_price': product.unit_price
    }), 201

@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'unit_price': p.unit_price
    } for p in products])

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'unit_price': product.unit_price
    })

# Distributor Inventory Management
@app.route('/api/distributor/inventory', methods=['POST'])
def set_distributor_inventory():
    data = request.json
    if not all(k in data for k in ['distributor_id', 'product_id', 'quantity']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    distributor = User.query.get_or_404(data['distributor_id'])
    if distributor.user_type != 'distributor':
        return jsonify({'error': 'User is not a distributor'}), 400
    
    Product.query.get_or_404(data['product_id'])
    
    inventory = DistributorInventory.query.filter_by(
        distributor_id=data['distributor_id'],
        product_id=data['product_id']
    ).first()
    
    if inventory:
        inventory.quantity = int(data['quantity'])
        inventory.updated_at = datetime.utcnow()
    else:
        inventory = DistributorInventory(
            distributor_id=data['distributor_id'],
            product_id=data['product_id'],
            quantity=int(data['quantity'])
        )
        db.session.add(inventory)
    
    db.session.commit()
    
    return jsonify({
        'id': inventory.id,
        'distributor_id': inventory.distributor_id,
        'product_id': inventory.product_id,
        'quantity': inventory.quantity
    })

@app.route('/api/distributor/<int:distributor_id>/inventory', methods=['GET'])
def get_distributor_inventory(distributor_id):
    distributor = User.query.get_or_404(distributor_id)
    if distributor.user_type != 'distributor':
        return jsonify({'error': 'User is not a distributor'}), 400
    
    inventory = DistributorInventory.query.filter_by(distributor_id=distributor_id).all()
    
    return jsonify([{
        'id': i.id,
        'product_id': i.product_id,
        'product_name': i.product.name,
        'unit_price': i.product.unit_price,
        'quantity': i.quantity,
        'updated_at': i.updated_at.isoformat()
    } for i in inventory])

# Order Management
@app.route('/api/orders', methods=['POST'])
def place_order():
    data = request.json
    if not all(k in data for k in ['distributor_id', 'orderer_id', 'product_id', 'quantity']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    distributor = User.query.get_or_404(data['distributor_id'])
    orderer = User.query.get_or_404(data['orderer_id'])
    
    if distributor.user_type != 'distributor':
        return jsonify({'error': 'Invalid distributor'}), 400
    
    if orderer.user_type not in ['shg', 'pharmacist']:
        return jsonify({'error': 'Orderer must be SHG or Pharmacist'}), 400
    
    # Check distributor inventory
    inventory = DistributorInventory.query.filter_by(
        distributor_id=data['distributor_id'],
        product_id=data['product_id']
    ).first()
    
    if not inventory or inventory.quantity < int(data['quantity']):
        return jsonify({'error': 'Insufficient inventory'}), 400
    
    order = Order(
        distributor_id=data['distributor_id'],
        orderer_id=data['orderer_id'],
        product_id=data['product_id'],
        quantity=int(data['quantity']),
        status='placed'
    )
    db.session.add(order)
    db.session.commit()
    
    return jsonify({
        'id': order.id,
        'distributor_id': order.distributor_id,
        'orderer_id': order.orderer_id,
        'product_id': order.product_id,
        'quantity': order.quantity,
        'status': order.status,
        'created_at': order.created_at.isoformat()
    }), 201

@app.route('/api/orders/<int:order_id>/deliver', methods=['PUT'])
def deliver_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.status == 'delivered':
        return jsonify({'error': 'Order already delivered'}), 400
    
    # Deduct from distributor inventory
    distributor_inv = DistributorInventory.query.filter_by(
        distributor_id=order.distributor_id,
        product_id=order.product_id
    ).first()
    
    if not distributor_inv or distributor_inv.quantity < order.quantity:
        return jsonify({'error': 'Insufficient distributor inventory'}), 400
    
    distributor_inv.quantity -= order.quantity
    
    # Add to orderer inventory
    orderer = User.query.get(order.orderer_id)
    
    if orderer.user_type == 'shg':
        orderer_inv = SHGInventory.query.filter_by(
            shg_id=order.orderer_id,
            product_id=order.product_id
        ).first()
        
        if orderer_inv:
            orderer_inv.quantity += order.quantity
        else:
            orderer_inv = SHGInventory(
                shg_id=order.orderer_id,
                product_id=order.product_id,
                quantity=order.quantity
            )
            db.session.add(orderer_inv)
    
    elif orderer.user_type == 'pharmacist':
        orderer_inv = PharmacistInventory.query.filter_by(
            pharmacist_id=order.orderer_id,
            product_id=order.product_id
        ).first()
        
        if orderer_inv:
            orderer_inv.quantity += order.quantity
        else:
            orderer_inv = PharmacistInventory(
                pharmacist_id=order.orderer_id,
                product_id=order.product_id,
                quantity=order.quantity
            )
            db.session.add(orderer_inv)
    
    order.status = 'delivered'
    order.delivered_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'id': order.id,
        'status': order.status,
        'delivered_at': order.delivered_at.isoformat()
    })

@app.route('/api/orders', methods=['GET'])
def get_orders():
    distributor_id = request.args.get('distributor_id')
    orderer_id = request.args.get('orderer_id')
    status = request.args.get('status')
    
    query = Order.query
    
    if distributor_id:
        query = query.filter_by(distributor_id=int(distributor_id))
    if orderer_id:
        query = query.filter_by(orderer_id=int(orderer_id))
    if status:
        query = query.filter_by(status=status)
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return jsonify([{
        'id': o.id,
        'distributor_id': o.distributor_id,
        'distributor_name': o.distributor.username,
        'orderer_id': o.orderer_id,
        'orderer_name': o.orderer.username,
        'orderer_type': o.orderer.user_type,
        'product_id': o.product_id,
        'product_name': o.product.name,
        'quantity': o.quantity,
        'status': o.status,
        'created_at': o.created_at.isoformat(),
        'delivered_at': o.delivered_at.isoformat() if o.delivered_at else None
    } for o in orders])

# SHG Inventory
@app.route('/api/shg/<int:shg_id>/inventory', methods=['GET'])
def get_shg_inventory(shg_id):
    shg = User.query.get_or_404(shg_id)
    if shg.user_type != 'shg':
        return jsonify({'error': 'User is not a SHG'}), 400
    
    inventory = SHGInventory.query.filter_by(shg_id=shg_id).all()
    
    return jsonify([{
        'id': i.id,
        'product_id': i.product_id,
        'product_name': i.product.name,
        'quantity': i.quantity,
        'updated_at': i.updated_at.isoformat()
    } for i in inventory])

# Pharmacist Inventory
@app.route('/api/pharmacist/<int:pharmacist_id>/inventory', methods=['GET'])
def get_pharmacist_inventory(pharmacist_id):
    pharmacist = User.query.get_or_404(pharmacist_id)
    if pharmacist.user_type != 'pharmacist':
        return jsonify({'error': 'User is not a pharmacist'}), 400
    
    inventory = PharmacistInventory.query.filter_by(pharmacist_id=pharmacist_id).all()
    
    return jsonify([{
        'id': i.id,
        'product_id': i.product_id,
        'product_name': i.product.name,
        'quantity': i.quantity,
        'updated_at': i.updated_at.isoformat()
    } for i in inventory])

# Health check
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
