from extension import db
from datetime import datetime


class Rooms(db.Model):
    __tablename__ = 'rooms'
    room_id = db.Column(db.Integer, primary_key=True, nullable=False)
    order_id = db.Column(db.String(100), db.ForeignKey('orders.order_id'), nullable=False)

class Customers(db.Model):
    __tablename__ = 'customers'
    customer_id = db.Column(db.String(100), primary_key=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order_id = db.Column(db.String(100), db.ForeignKey('orders.order_id'), nullable=False)

class Orders(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.String(100), primary_key=True, nullable=False)
    start_timestamp = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.FLOAT, nullable=False)

class Records(db.Model):
    __tablename__ = 'records'
    record_id = db.Column(db.String(100), primary_key=True, nullable=False)
    happen_timestamp = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    remark = db.Column(db.TEXT)
    order_id = db.Column(db.String(100), db.ForeignKey('orders.order_id'), nullable=False)
