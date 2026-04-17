
# (Borrar) Tener esta clase nos sirve para no repetir codigo en upload y download. Y porque se piden tranferir archivos binarios

import struct
#from .constants import HEADER_SIZE

class Packet:
    # Formato: Número Paquete (I=4B), ACK (I=4B), Flags/Unused (B=1B), DataLen (H=2B)
    FORMAT = "!IIBH" 

    def __init__(self, seq_num, ack_num, flags, data=b""):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.data = data

    def pack(self):
        header = struct.pack(self.FORMAT, self.seq_num, self.ack_num, self.flags, len(self.data))
        return header + self.data

    @classmethod
    def unpack(cls, raw_data):
        h_size = struct.calcsize(cls.FORMAT)
        header = raw_data[:h_size]
        data = raw_data[h_size:]
        seq, ack, flags, d_len = struct.unpack(cls.FORMAT, header)
        return cls(seq, ack, flags, data[:d_len])