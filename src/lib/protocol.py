import struct
import binascii
from dataclasses import dataclass


CONSTANTS = {

    "HEADER_SIZE": 8,
    "MAX_PKT_SIZE": 1024,
    "MAX_PAYLOAD": 1008,
    "DEFAULT_TIMEOUT": 1.0,
    "MAX_RETRIES": 10,
    "STOP_AND_WAIT": 1,
    "FLAG_I": 0b10000000,
    "FLAG_C": 0b01000000,
}

ERROR_CODES = {
    "OK": 0b0000,
    "BAD_PACKET": 0b0001,
    "FILE_NOT_FOUND": 0b0010,
    "STORAGE_FULL": 0b0011,
    "PERM_DENIED": 0b0100,
    "PROTO_MISMATCH": 0b0101,
    "CHECKSUM": 0b0110,
    "TIMEOUT_ABORT": 0b0111,
    "UNKNOWN": 0b1000,
}


def crc16(data: bytes) -> int:
    if not data:
        return 0x0000
    return binascii.crc_hqx(data, 0xFFFF)


@dataclass
class Packet:
    np:    int
    ack:   int
    flags: int
    win:   int
    crc:   int
    data:  bytes

    @staticmethod
    def build(np: int, ack: int, flags: int, win: int,
              data: bytes = b"") -> bytes:
        crc = crc16(data)
        return struct.pack("!HHBBH", np, ack, flags, win, crc) + data

    @staticmethod
    def parse(raw: bytes) -> "Packet":
        if len(raw) < CONSTANTS["HEADER_SIZE"]:
            raise ValueError("paquete demasiado corto")
        np, ack, flags, win, crc_recv = struct.unpack("!HHBBH", raw[:8])
        data = raw[8:]
        if crc16(data) != crc_recv:
            raise ValueError("CRC inválido")
        return Packet(np, ack, flags, win, crc_recv, data)