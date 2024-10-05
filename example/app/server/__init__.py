import n0va
import pathlib


class Service(n0va.Service):
    def __init__(self, host, port, root_path):
        super().__init__(host=host, port=port, root_path=root_path)
        # self.EnableSSL(
        #     domain_cert="domain.cert.pem",
        #     private_key="private.key.pem"
        # )


service = Service(
    host="127.0.0.1",
    port=80,
    root_path=pathlib.Path("./documents").resolve().as_posix(),
)
