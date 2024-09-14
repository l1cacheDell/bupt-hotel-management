# 酒店管理
## 表单 1：rooms
- 字段名：room_id（主键）, order_id（外键）, 
- 字段类型：UUID（主键）, UUID（外键）
- 字段含义：房间唯一标识符，订单唯一标识符（外键关联orders表）

## 表单 2：customers
- 字段名：customer_id（主键）, name, order_id（外键）
- 字段类型：UUID（主键）, VARCHAR(100), UUID（外键）
- 字段含义：客人身份证号，客人姓名，订单唯一标识符（外键关联orders表）

## 表单 3：orders
- 字段名：order_id（主键）, start_timestamp, amount
- 字段类型：UUID（主键）, TIMESTAMP, FLOAT
- 字段含义：订单唯一标识符，订单生成时间戳, 消费总金额

## 表单 4：records
- 字段名：record_id（主键）, happen_timestamp, remark, order_id（外键）
- 字段类型：UUID（主键）, TIMESTAMP, TEXT, UUID（外键）
- 字段含义：消费记录唯一标识符，记录生成时间戳，备注，订单唯一标识符