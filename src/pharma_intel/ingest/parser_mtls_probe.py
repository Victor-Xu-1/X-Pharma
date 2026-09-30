from __future__ import annotations

import argparse
import ipaddress
import json
import os
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pharma_intel.ingest.parser_client import ParserServiceClient

TOKEN = "parser-mtls-probe-token-0123456789abcdef"  # noqa: S105


@dataclass(frozen=True)
class Identity:
    certificate: Path
    private_key: Path


@dataclass(frozen=True)
class ProbeCertificates:
    server_ca: Path
    client_ca: Path
    server: Identity
    client: Identity
    rogue_client: Identity


def probe() -> dict[str, object]:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="pharma-parser-mtls-probe-") as temporary:
        root = Path(temporary)
        certificates = _create_certificates(root)
        port = _available_port()
        environment = _service_environment(root, certificates, port)
        with tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(  # noqa: S603
                [sys.executable, "-m", "pharma_intel.ingest.parser_service"],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                close_fds=True,
                start_new_session=True,
            )
            try:
                base_url = f"https://127.0.0.1:{port}"
                valid_context = _client_context(
                    certificates.server_ca,
                    certificates.client,
                )
                _wait_until_ready(process, stderr, base_url, valid_context)
                no_client_certificate_rejected = _tls_request_rejected(
                    base_url,
                    ssl.create_default_context(cafile=str(certificates.server_ca)),
                )
                rogue_client_rejected = _tls_request_rejected(
                    base_url,
                    _client_context(certificates.server_ca, certificates.rogue_client),
                )
                untrusted_server_rejected = _tls_request_rejected(
                    base_url,
                    _client_context(certificates.client_ca, certificates.client),
                )
                document = root / "mtls-evidence.md"
                document.write_text("EGFR mTLS parser evidence", encoding="utf-8")
                parsed = ParserServiceClient(
                    base_url,
                    TOKEN,
                    connect_timeout_seconds=2,
                    request_timeout_seconds=20,
                    max_file_bytes=1_048_576,
                    verify=valid_context,
                ).parse(document, 100_000)
                if not all(
                    (
                        no_client_certificate_rejected,
                        rogue_client_rejected,
                        untrusted_server_rejected,
                        parsed.text == "EGFR mTLS parser evidence",
                    )
                ):
                    raise RuntimeError("Parser mTLS acceptance controls did not pass")
            finally:
                _stop_process(process)
        return {
            "schema_version": 1,
            "status": "passed",
            "production_claim": False,
            "generated_at": datetime.now(UTC).isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "mutual_tls": True,
            "valid_client_parse": True,
            "no_client_certificate_rejected": no_client_certificate_rejected,
            "rogue_client_rejected": rogue_client_rejected,
            "untrusted_server_rejected": untrusted_server_rejected,
            "server_certificate_sha256": _certificate_fingerprint(certificates.server.certificate),
            "client_certificate_sha256": _certificate_fingerprint(certificates.client.certificate),
        }


def _create_certificates(root: Path) -> ProbeCertificates:
    server_ca_key, server_ca_certificate = _new_ca("Parser Probe Server CA")
    client_ca_key, client_ca_certificate = _new_ca("Parser Probe Client CA")
    rogue_ca_key, rogue_ca_certificate = _new_ca("Parser Probe Rogue CA")
    server_ca = root / "server-ca.crt"
    client_ca = root / "client-ca.crt"
    _write_certificate(server_ca, server_ca_certificate)
    _write_certificate(client_ca, client_ca_certificate)
    server = _new_identity(
        root,
        "server",
        server_ca_key,
        server_ca_certificate,
        ExtendedKeyUsageOID.SERVER_AUTH,
        server=True,
    )
    client = _new_identity(
        root,
        "client",
        client_ca_key,
        client_ca_certificate,
        ExtendedKeyUsageOID.CLIENT_AUTH,
    )
    rogue_client = _new_identity(
        root,
        "rogue-client",
        rogue_ca_key,
        rogue_ca_certificate,
        ExtendedKeyUsageOID.CLIENT_AUTH,
    )
    return ProbeCertificates(server_ca, client_ca, server, client, rogue_client)


def _new_ca(common_name: str) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return key, certificate


def _new_identity(
    root: Path,
    name: str,
    ca_key: rsa.RSAPrivateKey,
    ca_certificate: x509.Certificate,
    usage: x509.ObjectIdentifier,
    *,
    server: bool = False,
) -> Identity:
    key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_certificate.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.ExtendedKeyUsage([usage]), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )
    if server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
    certificate = builder.sign(ca_key, hashes.SHA256())
    identity = Identity(root / f"{name}.crt", root / f"{name}.key")
    _write_certificate(identity.certificate, certificate)
    identity.private_key.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    identity.private_key.chmod(0o600)
    return identity


def _write_certificate(path: Path, certificate: x509.Certificate) -> None:
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    path.chmod(0o600)


def _service_environment(root: Path, certificates: ProbeCertificates, port: int) -> dict[str, str]:
    return {
        "HOME": str(root),
        "LANG": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "PARSER_SERVICE_HOST": "127.0.0.1",
        "PARSER_SERVICE_PORT": str(port),
        "PARSER_SERVICE_TOKEN": TOKEN,
        "PARSER_SERVICE_MAX_FILE_BYTES": "1048576",
        "PARSER_SERVICE_MAX_TEXT_CHARS": "1000000",
        "PARSER_SERVICE_PARSER_TIMEOUT_SECONDS": "20",
        "PARSER_SERVICE_PARSER_CPU_SECONDS": "10",
        "PARSER_SERVICE_PARSER_MEMORY_BYTES": "1073741824",
        "PARSER_SERVICE_LIMIT_CONCURRENCY": "8",
        "PARSER_SERVICE_TLS_CERT_FILE": str(certificates.server.certificate),
        "PARSER_SERVICE_TLS_KEY_FILE": str(certificates.server.private_key),
        "PARSER_SERVICE_TLS_CLIENT_CA_FILE": str(certificates.client_ca),
    }


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _client_context(server_ca: Path, identity: Identity) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(server_ca))
    context.load_cert_chain(identity.certificate, identity.private_key)
    return context


def _wait_until_ready(
    process: subprocess.Popen[bytes],
    stderr: BinaryIO,
    base_url: str,
    context: ssl.SSLContext,
) -> None:
    deadline = time.monotonic() + 15
    last_error = "no connection attempt"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr.seek(0)
            detail = stderr.read(4096).decode(errors="replace")
            raise RuntimeError(f"Parser mTLS service exited before readiness: {detail}")
        try:
            with httpx.Client(verify=context, trust_env=False, timeout=1) as client:
                response = client.get(f"{base_url}/health/ready")
            if response.status_code == 200:
                return
        except httpx.TransportError as exc:
            last_error = repr(exc)
        time.sleep(0.1)
    stderr.seek(0)
    detail = stderr.read(4096).decode(errors="replace")
    raise RuntimeError(f"Parser mTLS service did not become ready ({last_error}): {detail}")


def _tls_request_rejected(base_url: str, context: ssl.SSLContext) -> bool:
    try:
        with httpx.Client(verify=context, trust_env=False, timeout=2) as client:
            client.get(f"{base_url}/health/ready")
    except httpx.TransportError:
        return True
    return False


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _certificate_fingerprint(path: Path) -> str:
    certificate = x509.load_pem_x509_certificate(path.read_bytes())
    return certificate.fingerprint(hashes.SHA256()).hex()


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise RuntimeError(f"Refusing to overwrite parser mTLS evidence: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = (json.dumps(probe(), indent=2, sort_keys=True) + "\n").encode()
    if args.output:
        _write_atomic(args.output, payload)
    print(payload.decode(), end="")


if __name__ == "__main__":
    run()
