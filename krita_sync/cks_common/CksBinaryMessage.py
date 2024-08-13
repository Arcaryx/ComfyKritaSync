import json
import base64
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import List


class PayloadType(IntEnum):
    JSON = 0
    PNG = 1


class MessageType(IntEnum):
    SendImageKrita = 0
    GetImageKrita = 1
    DocumentSync = 2


def deserialize_ignore_missing_keys(cls, payload_dict: dict):
    kwargs = {k: v for k, v in payload_dict.items() if k in cls.__annotations__.keys()}
    return cls(**kwargs)


@dataclass
class CksJsonPayload:
    type: MessageType

    def serialize(self) -> str:
        try:
            result = json.dumps(self.__dict__)
        except Exception as e:
            print("Unable to serialize dict", e)
            raise ValueError(f"Unable to serialize dict: {self.__dict__}")
        return result

    @classmethod
    def deserialize(cls, payload_json: str) -> 'CksJsonPayload':
        payload_dict = json.loads(payload_json)
        payload_type = payload_dict.get('type', None)

        if payload_type is None:
            raise ValueError("Missing 'type' field in JSON payload.")

        try:
            payload_subclass = {
                MessageType.SendImageKrita: SendImageKritaJsonPayload,
                MessageType.GetImageKrita: GetImageKritaJsonPayload,
                MessageType.DocumentSync: DocumentSyncJsonPayload,
            }[payload_type]
        except KeyError:
            raise ValueError(f"Unsupported 'type' value: {payload_type}")

        return payload_subclass.deserialize(payload_dict)


@dataclass
class SendImageKritaJsonPayload(CksJsonPayload):
    krita_document: str
    krita_layer: str
    run_uuid: str

    def __init__(self, krita_document: str, krita_layer: str, run_uuid: str):
        super().__init__(MessageType.SendImageKrita)
        self.krita_document = krita_document
        self.krita_layer = krita_layer
        self.run_uuid = run_uuid

    @classmethod
    def deserialize(cls, payload_dict: dict) -> 'SendImageKritaJsonPayload':
        return deserialize_ignore_missing_keys(cls, payload_dict)


class GetImageKritaJsonPayload(CksJsonPayload):
    krita_document: str
    krita_layer: str
    filename_prefix: str

    def __init__(self, krita_document: str, krita_layer: str, filename_prefix: str) -> None:
        super().__init__(MessageType.GetImageKrita)
        self.krita_document = krita_document
        self.krita_layer = krita_layer
        self.filename_prefix = filename_prefix

    @classmethod
    def deserialize(cls, payload_dict: dict) -> 'GetImageKritaJsonPayload':
        return deserialize_ignore_missing_keys(cls, payload_dict)


class DocumentSyncJsonPayload(CksJsonPayload):
    document_list: [(str, str)]

    def __init__(self, document_list: [(str, str)]):
        super().__init__(MessageType.DocumentSync)
        self.document_list = document_list

    @classmethod
    def deserialize(cls, payload_dict: dict) -> 'DocumentSyncJsonPayload':
        return deserialize_ignore_missing_keys(cls, payload_dict)


class CksBinaryMessage:
    def __init__(self, json_payload: CksJsonPayload):
        self.json_payload: CksJsonPayload = json_payload
        self.payloads: [(PayloadType, bytes)] = []

    def add_payload(self, payload_type: PayloadType, content: bytes):
        """
        Adds a payload to the message. Supports PayloadType.PNG.
        """
        if payload_type == PayloadType.PNG:
            # content must be raw PNG bytes
            self.payloads.append((PayloadType.PNG, content))
        else:
            raise ValueError("Unsupported payload type")

    def encode_message(self):
        """
        Encodes the message to binary format.
        """
        message_parts = []

        # Always put the json payload first
        dumped_json = self.json_payload.serialize()
        encoded_json_content = dumped_json.encode('utf-8')

        header = f"{PayloadType.JSON.name}:{len(encoded_json_content)},"
        message_parts.append(header.encode('utf-8'))
        message_parts.append(encoded_json_content)

        for payload_type, content in self.payloads:
            if payload_type == PayloadType.PNG:
                encoded_content = base64.b64encode(content)
            else:
                raise ValueError("Unsupported payload type")

            header = f"{payload_type.name}:{len(encoded_content)},"
            message_parts.append(header.encode('utf-8'))
            message_parts.append(encoded_content)

        # TODO: I feel like this is needlessly copying the byte arrays more than necessary, could actually be a performance issue
        encoded_message = b''.join(message_parts)
        return encoded_message

    @classmethod
    def decode_message(cls, binary_data) -> 'CksBinaryMessage':
        """
        Decodes a binary message back to its original form.
        """
        idx = 0
        decoded_message: CksBinaryMessage | None = None

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
                if decoded_message is None:
                    decoded_content = CksJsonPayload.deserialize(content.decode('utf-8'))
                    decoded_message = cls(decoded_content)
                else:
                    raise ValueError("More than one JSON payload was present in the message")
            elif payload_type == PayloadType.PNG:
                if decoded_message is None:
                    raise ValueError("No JSON payload present before image payloads")
                else:
                    decoded_content = base64.b64decode(content)
                    decoded_message.payloads.append((payload_type, decoded_content))
            else:
                raise ValueError(f"Unsupported payload type: {payload_type}")

            idx = content_end

        if decoded_message is None:
            raise ValueError("Unable to decode message from binary data")

        return decoded_message
