from datetime import datetime

print(datetime(2023, 1, 13, 14, 6, 0, 0))
print(datetime.now())

date_str = '2023-03-01T00:00:00Z'
date_str = '2023-03-02 17:22'
date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
print(date_obj)

date_str = '2023-03-02'
date_obj = datetime.strptime(date_str, '%Y-%m-%d')
print(date_obj)