import xmlrpc.client

putdata1 = bytearray(b'\x12\x34\x56\x78')
putdata2 = bytearray(b'\x9a\xbb\xde\xf0')

s = xmlrpc.client.ServerProxy('http://localhost:8000', use_builtin_types=True)

print("Value to be put: " + str(putdata1.hex()))
print(s.Put(putdata1))  
value1 = s.Get(0)  
bavalue1 = bytearray(value1)
print("Value received from server: " + str(bavalue1.hex()))

print("Value to be put: " + str(putdata2.hex()))
print(s.Put(putdata2))       
value2 = s.Get(0)     
print("Value received from server: " + str(value2.hex()))


