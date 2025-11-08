from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # distributor, shg, pharmacist
    pincode = db.Column(db.String(10), nullable=False)
    mobile_number = db.Column(db.String(15), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
class StockRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    distributor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    
    # Request details
    name = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    quantity = db.Column(db.Integer)
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # pending, responded, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    
    # Relationships
    distributor = db.relationship(
        'User',
        foreign_keys=[distributor_id],
        backref=db.backref('stock_requests_received', lazy='dynamic')
    )
    requester = db.relationship(
        'User',
        foreign_keys=[requester_id],
        backref=db.backref('stock_requests_made', lazy='dynamic')
    )
    product = db.relationship('Product', backref='stock_requests')

    def __repr__(self):
        return f"<StockRequest id={self.id} status={self.status} distributor_id={self.distributor_id} requester_id={self.requester_id}>"

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
    status = db.Column(db.String(20), default='placed')  # placed, accepted, dispatched, delivered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accepted_at = db.Column(db.DateTime)
    dispatched_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)

    distributor = db.relationship('User', foreign_keys=[distributor_id], backref='orders_received')
    orderer = db.relationship('User', foreign_keys=[orderer_id], backref='orders_placed')
    product = db.relationship('Product', backref='orders')
# Initialize database
with app.app_context():
    db.create_all()

# Routes


@app.route('/api/requests', methods=['POST'])
def create_stock_request():
    data = request.json

    # Validate required fields
    required_fields = ['distributor_id', 'requester_id', 'name', 'pincode', 'mobile']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

    # Fetch users
    distributor = User.query.get_or_404(data['distributor_id'])
    requester = User.query.get_or_404(data['requester_id'])

    # Validate user types
    if distributor.user_type != 'distributor':
        return jsonify({'error': 'Invalid distributor'}), 400
    if requester.user_type not in ['shg', 'pharmacist']:
        return jsonify({'error': 'Requester must be SHG or Pharmacist'}), 400

    # Create the stock request
    request_entry = StockRequest(
        distributor_id=data['distributor_id'],
        requester_id=data['requester_id'],
        name=data['name'],
        pincode=data['pincode'],
        mobile=data['mobile'],
        status='pending'
    )

    db.session.add(request_entry)
    db.session.commit()

    return jsonify({
        'id': request_entry.id,
        'distributor_id': request_entry.distributor_id,
        'requester_id': request_entry.requester_id,
        'status': request_entry.status,
        'created_at': request_entry.created_at.isoformat()
    }), 201

@app.route('/api/distributor/<int:distributor_id>/requests', methods=['GET'])
def get_distributor_requests(distributor_id):
    distributor = User.query.get_or_404(distributor_id)
    if distributor.user_type != 'distributor':
        return jsonify({'error': 'User is not a distributor'}), 400
    
    requests = StockRequest.query.filter_by(distributor_id=distributor_id).order_by(StockRequest.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'requester_id': r.requester_id,
        'requester_name': r.requester.username,
        'requester_type': r.requester.user_type,
        'name': r.name,
        'pincode': r.pincode,
        'mobile': r.mobile,
        'status': r.status,
        'created_at': r.created_at.isoformat()
    } for r in requests])

@app.route('/api/requests/<int:request_id>/respond', methods=['POST'])
def respond_to_request(request_id):
    data = request.json
    if not all(k in data for k in ['product_id', 'quantity']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    request_entry = StockRequest.query.get_or_404(request_id)
    if request_entry.status != 'pending':
        return jsonify({'error': 'Request already responded to'}), 400
    
    product = Product.query.get_or_404(data['product_id'])
    distributor_id = request_entry.distributor_id
    requester_id = request_entry.requester_id
    quantity = int(data['quantity'])

    # Create an order
    order = Order(
        distributor_id=distributor_id,
        orderer_id=requester_id,
        product_id=product.id,
        quantity=quantity,
        status='placed'
    )
    db.session.add(order)

    # Update request status
    request_entry.status = 'responded'
    request_entry.responded_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        'request_id': request_entry.id,
        'status': request_entry.status,
        'responded_at': request_entry.responded_at.isoformat(),
        'order_id': order.id
    }), 200


# User Management
@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json

    # Validate required fields
    required_fields = ['username', 'password', 'user_type', 'pincode', 'mobile_number']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

    # Validate user type
    if data['user_type'] not in ['distributor', 'shg', 'pharmacist']:
        return jsonify({'error': 'Invalid user type'}), 400

    # Check for duplicate username
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400

    # Create new user
    user = User(
        username=data['username'],
        user_type=data['user_type'],
        pincode=data['pincode'],
        mobile_number=data['mobile_number']
    )
    user.set_password(data['password'])

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'id': user.id,
        'username': user.username,
        'user_type': user.user_type,
        'pincode': user.pincode,
        'mobile_number': user.mobile_number
    }), 201

# Update order status

@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    data = request.json
    new_status = data.get('status')
    
    valid_transitions = {
        'placed': 'accepted',
        'accepted': 'dispatched',
        'dispatched': 'delivered'
    }

    if new_status not in ['accepted', 'dispatched', 'delivered']:
        return jsonify({'error': 'Invalid status'}), 400

    order = Order.query.get_or_404(order_id)
    
    # Ensure the user updating is the correct distributor
    distributor_id = data.get('distributor_id')
    if order.distributor_id != distributor_id:
        return jsonify({'error': 'Unauthorized distributor'}), 403
    
    current_status = order.status
    expected_next = valid_transitions.get(current_status)

    if expected_next != new_status:
        return jsonify({
            'error': f'Invalid transition. You can only move from {current_status} → {expected_next}'
        }), 400
    
    # --- Handle each transition ---
    if new_status == 'accepted':
        order.status = 'accepted'
        order.accepted_at = datetime.utcnow()
    
    elif new_status == 'dispatched':
        order.status = 'dispatched'
        order.dispatched_at = datetime.utcnow()
    
    elif new_status == 'delivered':
        order.status = 'delivered'
        order.delivered_at = datetime.utcnow()

        # Deduct distributor inventory + add to SHG/Pharmacist
        distributor_inv = DistributorInventory.query.filter_by(
            distributor_id=order.distributor_id,
            product_id=order.product_id
        ).first()
        
        if not distributor_inv or distributor_inv.quantity < order.quantity:
            return jsonify({'error': 'Insufficient distributor inventory'}), 400
        
        distributor_inv.quantity -= order.quantity
        orderer = order.orderer

        if orderer.user_type == 'shg':
            inv = SHGInventory.query.filter_by(
                shg_id=order.orderer_id, product_id=order.product_id
            ).first()
            if inv: inv.quantity += order.quantity
            else:
                db.session.add(SHGInventory(
                    shg_id=order.orderer_id, product_id=order.product_id, quantity=order.quantity
                ))

        elif orderer.user_type == 'pharmacist':
            inv = PharmacistInventory.query.filter_by(
                pharmacist_id=order.orderer_id, product_id=order.product_id
            ).first()
            if inv: inv.quantity += order.quantity
            else:
                db.session.add(PharmacistInventory(
                    pharmacist_id=order.orderer_id, product_id=order.product_id, quantity=order.quantity
                ))

    db.session.commit()

    return jsonify({
        'id': order.id,
        'status': order.status,
        'accepted_at': order.accepted_at.isoformat() if order.accepted_at else None,
        'dispatched_at': order.dispatched_at.isoformat() if order.dispatched_at else None,
        'delivered_at': order.delivered_at.isoformat() if order.delivered_at else None
    }), 200


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
