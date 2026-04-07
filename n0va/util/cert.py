import ssl

from OpenSSL import crypto


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

    @staticmethod
    def _subject_set_field(name: crypto.X509Name, field: str, value: str) -> None:
        """空文字は付与しない（空の C は ASN.1 上問題になり `string too short` 等の原因になる）。"""
        v = (value or "").strip()
        if not v:
            return
        if field == "C" and len(v) != 2:
            return
        setattr(name, field, v)

    def ca_make(self) -> None:
        # create key pair
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 4096)

        # create self-signed cert
        cert = crypto.X509()
        subj = cert.get_subject()
        ca_cn = (self.CA_CommonName or "n0va-local-ca").strip() or "n0va-local-ca"
        subj.CN = ca_cn
        CertificateAuthority._subject_set_field(subj, "O", self.CA_Organization)
        CertificateAuthority._subject_set_field(subj, "ST", self.CA_State)
        CertificateAuthority._subject_set_field(subj, "L", self.CA_Locality)
        CertificateAuthority._subject_set_field(subj, "C", self.CA_Country)
        cert.set_serial_number(self.CA_SerialNumber)
        cert.gmtime_adj_notBefore(self.CA_NotBefore)
        cert.gmtime_adj_notAfter(self.CA_NotAfter)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.add_extensions(
            [
                crypto.X509Extension(
                    "basicConstraints".encode("ascii"), True, "CA:TRUE".encode("ascii")
                ),
                crypto.X509Extension(
                    "keyUsage".encode("ascii"),
                    True,
                    "cRLSign, keyCertSign".encode("ascii"),
                ),
                crypto.X509Extension(
                    "subjectKeyIdentifier".encode("ascii"), False, b"hash", subject=cert
                ),
            ]
        )
        cert.add_extensions(
            [
                crypto.X509Extension(
                    "authorityKeyIdentifier".encode("ascii"),
                    False,
                    b"keyid:always",
                    issuer=cert,
                )
            ]
        )
        # v3
        cert.set_version(2)
        # self signature
        cert.sign(key, "sha256")

        # save cert
        open(self.CA_CertPath_pem, "wb").write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        )
        pw = (self.CA_PrivatePassKey or "").strip()
        if pw:
            key_pem = crypto.dump_privatekey(
                crypto.FILETYPE_PEM,
                key,
                "aes256",
                pw.encode("utf-8"),
            )
        else:
            # 開発用: パスフレーズなしは平文 PEM（対話プロンプトを避ける）
            key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
        open(self.CA_PrivateKeyPath_pem, "wb").write(key_pem)
        open(self.CA_PrivateKeyPath_der, "wb").write(
            crypto.dump_certificate(crypto.FILETYPE_ASN1, cert)
        )


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
    def _load_private_key_from_pem(pem: bytes, passphrase: str | None) -> crypto.PKey:
        """
        PEM 秘密鍵を読み込む。平文・空パス暗号化・パス付き暗号化を区別する。
        `passphrase` が非空のときはそれのみ試す。
        非対話用途: パスフレーズなしのときは `passphrase=None` を先に使わず `b""` を試し、
        暗号化 PEM で OpenSSL が TTY にパスフレーズを聞きにいくのを避ける。
        """
        pw = (passphrase or "").strip()
        if pw:
            return crypto.load_privatekey(
                crypto.FILETYPE_PEM, pem, passphrase=pw.encode("utf-8")
            )
        try:
            return crypto.load_privatekey(crypto.FILETYPE_PEM, pem, passphrase=b"")
        except crypto.Error:
            pass
        return crypto.load_privatekey(crypto.FILETYPE_PEM, pem, passphrase=None)

    def c_make(self):
        f = open(self.CA_PrivateKeyPath_pem, "rb")
        ky = f.read()
        f.close()
        f = open(self.CA_CertPath_pem, "rb")
        ct = f.read()
        f.close()
        pp = (self.CA_PrivatePassKey or "").strip() or None
        CAkey = Certificate._load_private_key_from_pem(ky, pp)
        CAcert = crypto.load_certificate(crypto.FILETYPE_PEM, ct)

        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 4096)
        cert = crypto.X509()
        subj = cert.get_subject()
        cn = (self.commonName or "localhost").strip() or "localhost"
        subj.CN = cn
        CertificateAuthority._subject_set_field(subj, "O", self.organization)
        CertificateAuthority._subject_set_field(subj, "ST", self.state)
        CertificateAuthority._subject_set_field(subj, "L", self.locality)
        CertificateAuthority._subject_set_field(subj, "C", self.country)
        cert.set_serial_number(self.serialNumber)
        cert.gmtime_adj_notBefore(self.notBefore)
        cert.gmtime_adj_notAfter(self.notAfter)
        cert.set_issuer(CAcert.get_subject())
        cert.set_pubkey(key)
        cert.add_extensions(
            [
                crypto.X509Extension(
                    "keyUsage".encode("ascii"),
                    True,
                    b"digitalSignature, keyEncipherment",
                ),
                crypto.X509Extension(
                    "basicConstraints".encode("ascii"), True, b"CA:FALSE"
                ),
                crypto.X509Extension(
                    "extendedKeyUsage".encode("ascii"), False, b"clientAuth, serverAuth"
                ),
                crypto.X509Extension(
                    "subjectAltName".encode("ascii"),
                    False,
                    b"".join(
                        [
                            b"DNS:*.",
                            cn.encode("ascii"),
                            b", DNS:",
                            cn.encode("ascii"),
                        ]
                    ),
                ),
            ]
        )
        # v3
        cert.set_version(2)
        cert.sign(CAkey, "sha256")

        # save cert
        DC = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        open(self.certPath, "wb").write(DC)

        # save private key
        DP = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
        open(self.privateKeyPath, "wb").write(DP)

        p12 = crypto.PKCS12()
        p12.set_certificate(cert)
        p12.set_privatekey(key)
        p12_text = p12.export()
        open(self.pfxPath, "wb").write(p12_text)
