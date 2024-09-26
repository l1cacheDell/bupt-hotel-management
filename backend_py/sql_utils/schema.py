from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(pk=True, auto_increment=True)
    name = fields.CharField(max_length=255)
    identity_card = fields.CharField(max_length=18)
    room_number = fields.ForeignKeyField('models.Room', related_name='users')
    check_in_time = fields.DatetimeField(auto_now_add=True)
    check_out_time = fields.DatetimeField(null=True)
    bill = fields.FloatField(null=True)

class Room(Model):
    room_number = fields.IntField(pk=True)
    status = fields.CharField(max_length=10)  # available, occupied
    speed = fields.CharField(max_length=10, null=True)  # high, medium, low, 允许为空
    temperature = fields.FloatField(null=True)  # 允许为空

class DetailedRecord(Model):
    id = fields.IntField(pk=True)
    user_name = fields.CharField(max_length=255)
    room_number = fields.IntField()
    operation_type = fields.CharField(max_length=10)  # high, medium, low
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField()
    amount = fields.FloatField()