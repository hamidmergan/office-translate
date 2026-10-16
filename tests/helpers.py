import zipfile


def read_part(path, name):
    with zipfile.ZipFile(path) as z:
        return z.read(name).decode("utf-8")


def replace_part(path, name, data):
    """Rewrite one part of a zip file, keeping all others."""
    with zipfile.ZipFile(path) as z:
        items = [(info, z.read(info)) for info in z.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, content in items:
            z.writestr(info, data if info.filename == name else content)
