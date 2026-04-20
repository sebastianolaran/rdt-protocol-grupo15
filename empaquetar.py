import struct

HEADER_FORMAT = "!HHBBH"

MASCARA_ERR = 0x0F

OK = 0x00
FILE_ERROR = 0x01
PATH_ERROR = 0x02
PERMISSION_DENIED = 0x03
DISK_FULL = 0x04
PROTO_MISMATCH = 0x05
CONN_LIMIT = 0x06
TIMEOUT_ABORT = 0x07
BAD_PACKET = 0x08

MASK_INIT     = 0x80  # 1000 0000 (Bit 7)
MASK_CLOSE    = 0x40  # 0100 0000 (Bit 6)
MASK_DOWNLOAD = 0x20  # 0010 0000 (Bit 5)
MASK_UPLOAD   = 0x10  # 0001 0000 (Bit 4)

MAX_DATA_SIZE = 1008
MAX_PACKET_SIZE = 1024

def get_error(flags_byte):
    return flags_byte & MASCARA_ERR

def is_init(flags_byte):
    return (flags_byte & MASK_INIT) != 0

def is_close(flags_byte):
    return (flags_byte & MASK_CLOSE) != 0

def is_upload(flags_byte):
    return (flags_byte & MASK_UPLOAD) != 0

def is_download(flags_byte):
    return (flags_byte & MASK_DOWNLOAD) != 0

def unpack_header(packet):
    """Convierte los primeros 8 bytes en variables de Python."""
    header_raw = packet[:8]
    # !HHBBH: NP(2), ACK(2), Flags/Err(1), Unused(1), DataLen(2)
    return struct.unpack(HEADER_FORMAT, header_raw)

def build_control_byte(init=False, close=False, download=False, upload=False, error=OK):
    
    control = 0
    if init:     control |= MASK_INIT     # [cite: 169]
    if close:    control |= MASK_CLOSE    # [cite: 170]
    if download: control |= MASK_DOWNLOAD # [cite: 171]
    if upload:   control |= MASK_UPLOAD   # [cite: 172, 173]
    
    control |= (error & MASCARA_ERR)
    
    return control

# Nota: control_Byte es la "suma" de I, C, D, U y cual sea el error
def create_packet(np, ack, control_byte, data):
    header = struct.pack(HEADER_FORMAT, np, ack, control_byte, 0, len(data))
    return header + data