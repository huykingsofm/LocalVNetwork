import struct

from hks_pylib.cryptography.ciphers.hkscipher import HKSCipher
from hks_pylib.cryptography.ciphers.cipherid import CipherID, hash_cls_name

from hks_pynetwork.packet import MIN_HEADER_SIZE, PacketEncoder, PacketDecoder

from hks_pynetwork.errors.secure_packet import CipherTypeMismatchError


class SecurePacketEncoder(PacketEncoder):
    def __init__(self, cipher: HKSCipher):
        self.cipher = cipher

    def encode(self, payload: bytes):
        payload = self.cipher.encrypt(payload)
        packet = super().encode(payload)

        # SECURE HEADER = TYPE_OF_CIPHER (2 bytes) + NUMBER_OF_PARAMS(1 byte)
        #                 + PARAM1_SIZE + PARAM1 + PARAM2_SIZE + PARAM2 + ...
        # TYPE_OF_CIPHER is the hash value of the cipher class

        secure_header = hash_cls_name(self.cipher)\
            + struct.pack(">B", self.cipher._number_of_params)

        for i in range(self.cipher._number_of_params):
            param = self.cipher.get_param(i)

            assert isinstance(param, bytes)

            param_size = len(param)
            param_struct = "B{}s".format(param_size)
            secure_header += struct.pack(param_struct, param_size, param)

        # Set new header size = old header size + secure header size
        old_header_size = struct.unpack(">H", packet[:2])[0]
        
        packet = packet[:old_header_size]\
            + secure_header\
            + packet[old_header_size:]
        
        new_header_size = old_header_size + len(secure_header)
        new_header_size = struct.pack(">H", new_header_size)

        # Return the packet with new header size
        return new_header_size + packet[2:]


class SecurePacketDecoder(PacketDecoder):
    def __init__(self, cipher: HKSCipher):
        self.cipher = cipher

    def decode(self, packet: bytes):
        packet_dict = super().decode(packet)

        # ORIGINAL HEADER = HEADER_SIZE (2 bytes) + PAYLOAD_SIZE (2 byte)

        # SECURE HEADER: TYPE_OF_CIPHER (2 bytes) + NUMBER_OF_PARAMS(1 byte)
        #                 + PARAM1_SIZE + PARAM1 + PARAM2_SIZE + PARAM2 + ...

        cipher_hashvalue = packet[MIN_HEADER_SIZE: MIN_HEADER_SIZE + 2]
        cipher_type = CipherID.hash2cls(cipher_hashvalue)

        if cipher_type is None:
            raise CipherTypeMismatchError("Cipher type is invalid "
            "(hash = {}).".format(cipher_hashvalue))

        if not isinstance(self.cipher, cipher_type):
            raise CipherTypeMismatchError("Cipher type mismatches "
            "(expected {}, but received {}).".format(
                type(self.cipher).__name__,
                cipher_type.__name__
            ))

        number_of_params = struct.unpack(
                ">B",
                packet[MIN_HEADER_SIZE + 2: MIN_HEADER_SIZE + 3]
            )[0]

        current_index = MIN_HEADER_SIZE + 3
        for i in range(number_of_params):
            param_size = struct.unpack(
                    ">B",
                    packet[current_index: current_index + 1]
                )[0]
            current_index += 1

            param = struct.unpack(
                    ">{}s".format(param_size),
                    packet[current_index: current_index + param_size]
                )[0]
            current_index += param_size

            self.cipher.set_param(i, param)

        self.cipher.reset(False)

        packet_dict["payload"] = self.cipher.decrypt(packet_dict["payload"])

        return packet_dict
