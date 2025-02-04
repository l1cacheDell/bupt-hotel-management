import requests

for idx in range(5):
    room_number = idx + 101
    name = "test" + str(idx)
    idCard = "1234567"
    showDetails = "true"
    
    requests.post('http://101.42.20.174:4000/api/rooms/checkIn', json={
        'room_number': room_number,
        'name': name,
        'idCard': idCard,
        '_showDetails': showDetails
    })