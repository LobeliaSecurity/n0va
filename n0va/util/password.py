import secrets
import string


def safariStyleRandomPassword():
    R = "".join(
        [
            *[
                secrets.choice(f"{string.ascii_letters}{string.digits}")
                for x in range(6)
            ],
            "-",
            *[
                secrets.choice(f"{string.ascii_letters}{string.digits}")
                for x in range(6)
            ],
            "-",
            *[
                secrets.choice(f"{string.ascii_letters}{string.digits}")
                for x in range(6)
            ],
        ]
    )
    return R


def firefoxStyleRandomPassword():
    R = "".join(
        [secrets.choice(f"{string.ascii_letters}{string.digits}") for x in range(15)],
    )
    return R
