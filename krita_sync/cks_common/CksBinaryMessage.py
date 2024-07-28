import json
import base64
from enum import Enum, auto


class PayloadType(Enum):
    JSON = auto()
    PNG = auto()


class CksBinaryMessage:
    def __init__(self):
        self.payloads = []

    def add_payload(self, payload_type, content):
        """
        Adds a payload to the message. Supports 'json' and 'png'.
        """
        if payload_type == 'json':
            encoded_content = json.dumps(content).encode('utf-8')
            self.payloads.append((PayloadType.JSON, encoded_content))
        elif payload_type == 'png':
            # content must be raw PNG bytes
            encoded_content = base64.b64encode(content)
            self.payloads.append((PayloadType.PNG, encoded_content))
        else:
            raise ValueError("Unsupported payload type")

    def encode_message(self):
        """
        Encodes the message to binary format.
        """
        message_parts = []
        for payload_type, content in self.payloads:
            header = f"{payload_type.name}:{len(content)},"
            message_parts.append(header.encode('utf-8'))
            message_parts.append(content)

        encoded_message = b''.join(message_parts)
        return encoded_message

    @classmethod
    def decode_message(cls, binary_data):
        """
        Decodes a binary message back to its original form.
        """
        idx = 0
        decoded_message = cls()

        if isinstance(binary_data, (bytes, bytearray)):
            binary_data = memoryview(binary_data)

        while idx < len(binary_data):
            # Find the next header
            header_end = binary_data[idx:].tobytes().find(b':')
            type_str = binary_data[idx:idx + header_end].tobytes().decode('utf-8')
            payload_type = PayloadType[type_str]

            content_length_start = idx + header_end + 1
            content_length_end = binary_data[content_length_start:].tobytes().find(b',')
            if content_length_end == -1:
                content_length_end = len(binary_data) - content_length_start

            content_length = int(binary_data[content_length_start:content_length_start + content_length_end].tobytes())

            content_start = content_length_start + content_length_end + 1
            content_end = content_start + content_length
            content = binary_data[content_start:content_end].tobytes()

            if payload_type == PayloadType.JSON:
                decoded_content = json.loads(content.decode('utf-8'))
            elif payload_type == PayloadType.PNG:
                decoded_content = base64.b64decode(content)
            else:
                raise ValueError(f"Unsupported payload type: {payload_type}")

            decoded_message.payloads.append((payload_type, decoded_content))
            idx = content_end

        return decoded_message
