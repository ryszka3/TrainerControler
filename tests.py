

data = (0x80, 0x01, 0x03)

result: str = None
if data[2] == 0x01:
    result = "Success"
elif data[2] == 0x02:
    result = "Not Supported"
elif data[2] == 0x03:
    result = "Invalid parameter"
elif data[2] == 0x04:
    result = "Operation failed"
elif data[2] == 0x05:
    result = "Control not permitted"



print("Control point responce: (", data[1], ") -> ", result)