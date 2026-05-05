from __future__ import annotations

import ssl
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
    pkcs12,
)
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _build_x509_name(
    common_name: str,
    organization: str = "",
    state: str = "",
    locality: str = "",
    country: str = "",
) -> x509.Name:
    """空の C（国コード）は付与しない（2 文字でない C はスキップ）。"""
    attrs: list[x509.NameAttribute] = [
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ]
    v = (organization or "").strip()
    if v:
        attrs.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, v))
    v = (state or "").strip()
    if v:
        attrs.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, v))
    v = (locality or "").strip()
    if v:
        attrs.append(x509.NameAttribute(NameOID.LOCALITY_NAME, v))
    v = (country or "").strip()
    if len(v) == 2:
        attrs.append(x509.NameAttribute(NameOID.COUNTRY_NAME, v))
    return x509.Name(attrs)


def _positive_serial(n: int) -> int:
    """cryptography はシリアルに正の整数を要求する。0 のときは 1 とする（ダッシュボード既定の 0 でも発行できるように）。"""
    return n if n > 0 else 1


def _validity_window(not_before_sec: int, not_after_sec: int) -> tuple[datetime, datetime]:
    """従来の `gmtime_adj_notBefore` / `gmtime_adj_notAfter` に合わせ、いずれも「署名時点の UTC からの秒」。"""
    base = datetime.now(timezone.utc)
    return (
        base + timedelta(seconds=not_before_sec),
        base + timedelta(seconds=not_after_sec),
    )


class ServerTlsContext:
    """ディスク上の PEM から TLS サーバー用 `SSLContext` を構築する。"""

    @staticmethod
    def from_pem_files(cert_path: str, key_path: str) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        ctx.load_cert_chain(cert_path, key_path)
        return ctx


class CertificateAuthority:
    def __init__(self) -> None:
        self.CA_CommonName = ""
        self.CA_Organization = ""
        self.CA_State = ""
        self.CA_Locality = ""
        self.CA_Country = ""
        self.CA_PrivatePassKey = ""
        self.CA_SerialNumber = 0
        self.CA_NotBefore = 0
        self.CA_NotAfter = 30 * 365 * 24 * 60 * 60
        self.CA_CertPath_pem = ""
        self.CA_PrivateKeyPath_pem = ""
        self.CA_PrivateKeyPath_der = ""

    def ca_make(self) -> None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        ca_cn = (self.CA_CommonName or "n0va-local-ca").strip() or "n0va-local-ca"
        subject = _build_x509_name(
            ca_cn,
            self.CA_Organization,
            self.CA_State,
            self.CA_Locality,
            self.CA_Country,
        )
        nb, na = _validity_window(self.CA_NotBefore, self.CA_NotAfter)
        pubkey = key.public_key()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(pubkey)
            .serial_number(_positive_serial(int(self.CA_SerialNumber)))
            .not_valid_before(nb)
            .not_valid_after(na)
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False,
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
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(pubkey),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(pubkey),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        open(self.CA_CertPath_pem, "wb").write(cert.public_bytes(Encoding.PEM))
        pw = (self.CA_PrivatePassKey or "").strip()
        enc: serialization.KeySerializationEncryption
        if pw:
            enc = BestAvailableEncryption(pw.encode("utf-8"))
        else:
            enc = NoEncryption()
        key_pem = key.private_bytes(
            Encoding.PEM,
            PrivateFormat.TraditionalOpenSSL,
            enc,
        )
        open(self.CA_PrivateKeyPath_pem, "wb").write(key_pem)
        open(self.CA_PrivateKeyPath_der, "wb").write(cert.public_bytes(Encoding.DER))


class Certificate(CertificateAuthority):
    def __init__(self) -> None:
        super().__init__()
        self.commonName = ""
        self.organization = ""
        self.state = ""
        self.locality = ""
        self.country = ""
        self.privatePassKey = ""
        self.serialNumber = 0
        self.notBefore = 0
        self.notAfter = 365 * 24 * 60 * 60
        self.certPath = ""
        self.privateKeyPath = ""
        self.pfxPath = ""

    @staticmethod
    def _load_private_key_from_pem(pem: bytes, passphrase: str | None):
        """
        PEM 秘密鍵を読み込む。平文・空パス暗号化・パス付き暗号化を区別する。
        `passphrase` が非空のときはそれのみ試す。
        非対話用途: パスフレーズなしのときは暗号化 PEM で対話プロンプトを避けるため `password=b\"\"` を先に試す。
        """
        pw = (passphrase or "").strip()
        if pw:
            return load_pem_private_key(pem, password=pw.encode("utf-8"))
        try:
            return load_pem_private_key(pem, password=b"")
        except (TypeError, ValueError):
            pass
        return load_pem_private_key(pem, password=None)

    def c_make(self):
        with open(self.CA_PrivateKeyPath_pem, "rb") as f:
            ky = f.read()
        with open(self.CA_CertPath_pem, "rb") as f:
            ct = f.read()
        pp = (self.CA_PrivatePassKey or "").strip() or None
        ca_key = Certificate._load_private_key_from_pem(ky, pp)
        ca_cert = x509.load_pem_x509_certificate(ct)

        leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        cn = (self.commonName or "localhost").strip() or "localhost"
        subject = _build_x509_name(
            cn,
            self.organization,
            self.state,
            self.locality,
            self.country,
        )
        nb, na = _validity_window(self.notBefore, self.notAfter)
        leaf_pub = leaf_key.public_key()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(leaf_pub)
            .serial_number(_positive_serial(int(self.serialNumber)))
            .not_valid_before(nb)
            .not_valid_after(na)
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
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage(
                    [
                        ExtendedKeyUsageOID.CLIENT_AUTH,
                        ExtendedKeyUsageOID.SERVER_AUTH,
                    ]
                ),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName(f"*.{cn}"),
                        x509.DNSName(cn),
                    ]
                ),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )

        open(self.certPath, "wb").write(cert.public_bytes(Encoding.PEM))
        open(self.privateKeyPath, "wb").write(
            leaf_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
        )
        p12_data = pkcs12.serialize_key_and_certificates(
            name=b"n0va",
            key=leaf_key,
            cert=cert,
            cas=[ca_cert],
            encryption_algorithm=NoEncryption(),
        )
        open(self.pfxPath, "wb").write(p12_data)
