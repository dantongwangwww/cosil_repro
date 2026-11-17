"""Bounded private Unix-socket protocol; no remote endpoints or credentials."""
import hashlib
import json
import socket
import time
from . import config as P

LIMIT = 1024 * 1024


def validate_row(row):
    allowed = {'model_input', 'input_version', 'input_sha256', 'issue', 'function', 'neighbors'}
    if not isinstance(row, dict) or set(row) != allowed or row['input_version'] != 'v6_issue8000_fn8192_neighbors16_8192tokens_v1':
        raise ValueError('Only a frozen public rendered input is accepted')
    if not isinstance(row['model_input'], str) or hashlib.sha256(row['model_input'].encode()).hexdigest() != row['input_sha256']:
        raise ValueError('Rendered input SHA mismatch')
    from code_v6.input_format import assert_v6_row
    assert_v6_row(row)
    return row


def receive(stream):
    line = stream.readline(LIMIT + 1)
    if len(line) > LIMIT or not line.endswith(b'\n'):
        raise ValueError('Incomplete or oversized RPC frame')
    return json.loads(line)


def request(operation, row=None, *, socket_path=None, timeout=180):
    body = {'operation': operation}
    if row is not None:
        body['row'] = validate_row({k: row[k] for k in ('model_input', 'input_version', 'input_sha256', 'issue', 'function', 'neighbors')})
    data = (json.dumps(body, ensure_ascii=False, allow_nan=False) + '\n').encode()
    if len(data) > LIMIT:
        raise ValueError('Oversized RPC request')
    began = time.perf_counter()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(socket_path or P.SOCKET))
        sock.sendall(data)
        with sock.makefile('rb') as stream:
            result = receive(stream)
    if not result.get('ok'):
        raise RuntimeError('Resident judge failed: ' + str(result.get('error')))
    return {**result['result'], 'rpc_seconds': time.perf_counter() - began}


class Client:
    def score(self, row):
        return request('score', row)
