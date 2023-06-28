from OpenSSL import crypto


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
        self.CA_NotAfter = 30*365*24*60*60
        self.CA_CertPath_pem = ""
        self.CA_PrivateKeyPath_pem = ""
        self.CA_PrivateKeyPath_der = ""

    def ca_make(self) -> None:
        # create key pair
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 4096)

        # create self-signed cert
        cert = crypto.X509()
        cert.get_subject().CN = self.CA_CommonName
        cert.get_subject().O = self.CA_Organization
        cert.get_subject().ST = self.CA_State
        cert.get_subject().L = self.CA_Locality
        cert.get_subject().C = self.CA_Country
        cert.set_serial_number(self.CA_SerialNumber)
        cert.gmtime_adj_notBefore(self.CA_NotBefore)
        cert.gmtime_adj_notAfter(self.CA_NotAfter)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.add_extensions([
            crypto.X509Extension(
                "basicConstraints".encode("ascii"), True, "CA:TRUE".encode("ascii")),
            crypto.X509Extension(
                "keyUsage".encode("ascii"), True, "cRLSign, keyCertSign".encode('ascii')),
            crypto.X509Extension(
                'subjectKeyIdentifier'.encode('ascii'), False, b"hash", subject=cert)
        ])
        cert.add_extensions([
            crypto.X509Extension(
                'authorityKeyIdentifier'.encode('ascii'), False, b"keyid:always", issuer=cert)
        ])
        # v3
        cert.set_version(2)
        # self signature
        cert.sign(key, 'sha256')

        # save cert
        open(self.CA_CertPath_pem, 'wb').write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        open(self.CA_PrivateKeyPath_pem, 'wb').write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, key, 'aes256', self.CA_PrivatePassKey.encode('ascii')))
        open(self.CA_PrivateKeyPath_der, 'wb').write(
            crypto.dump_certificate(crypto.FILETYPE_ASN1, cert))


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
        self.notAfter = 365*24*60*60
        self.certPath = ""
        self.privateKeyPath = ""
        self.pfxPath = ""

    def c_make(self):
        # create key pair
        f = open(self.CA_PrivateKeyPath, 'rb')
        ky = f.read()
        f.close()
        f = open(self.CA_CertPath, 'rb')
        ct = f.read()
        f.close()
        CAkey = crypto.load_privatekey(
            crypto.FILETYPE_PEM, ky, passphrase=self.CA_PrivatePassKey.encode('ascii'))
        CAcert = crypto.load_certificate(crypto.FILETYPE_PEM, ct)

        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 4096)
        # create self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = self.country
        cert.get_subject().CN = self.commonName
        cert.set_serial_number(self.serialNumber)
        cert.gmtime_adj_notBefore(self.notBefore)
        cert.gmtime_adj_notAfter(self.notAfter)
        cert.set_issuer(CAcert.get_subject())
        cert.set_pubkey(key)
        cert.add_extensions([
            crypto.X509Extension(
                "keyUsage".encode("ascii"), True, b"digitalSignature, keyEncipherment"),
            crypto.X509Extension(
                "basicConstraints".encode("ascii"), True, b"CA:FALSE"),
            crypto.X509Extension(
                "extendedKeyUsage".encode("ascii"), False, b"clientAuth, serverAuth"),
            crypto.X509Extension(
                'subjectAltName'.encode('ascii'),
                False,
                b"".join([
                    b"DNS:*.",
                    self.commonName.encode('ascii'),
                    b", DNS:",
                    self.commonName.encode('ascii')
                ])
            )
        ])
        # v3
        cert.set_version(2)
        cert.sign(CAkey, 'sha256')

        # save cert
        DC = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        open(self.certPath, 'wb').write(DC)

        # save private key
        DP = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
        open(self.privateKeyPath, 'wb').write(DP)

        p12 = crypto.PKCS12()
        p12.set_certificate(cert)
        p12.set_privatekey(key)
        p12_text = p12.export()
        open(self.pfxPath, "wb").write(p12_text)
