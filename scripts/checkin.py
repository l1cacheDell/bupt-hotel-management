import requests

init_temp = [32, 28, 30, 29, 35]

for idx in range(5):
    room_number = idx + 101
    name = "test" + str(idx)
    idCard = "1234567"
    showDetails = "true"
    
    requests.post('http://localhost:4000/api/rooms/checkIn', json={
        'room_number': room_number,
        'name': name,
        'idCard': idCard,
        '_showDetails': showDetails
    })
    requests.post('http://localhost:4000/api/setTemperature_init', json={
        'room_number': room_number,
        'temperature': init_temp[idx]
    })